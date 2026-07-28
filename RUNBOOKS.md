# BlackCart — Operational Runbooks

Spec §29's Phase 6 deliverable list names runbooks explicitly. These are not generic "check the
logs" boilerplate — each one below is a failure mode this project actually hit, diagnosed, and
fixed at least once (usually more), recorded in [`done.MD`](./done.MD) as it happened. The point of
writing them down here is so the *next* time one of these symptoms shows up, it takes a lookup
instead of a re-derivation.

Each entry: **Symptom** (what you'll actually observe) → **Diagnosis** (how to confirm it's this,
not something else) → **Fix** → **Why this keeps coming back** (the actual root cause class, so you
recognize it under a different symptom next time).

---

## 1. A backend code change doesn't seem to take effect

**Symptom**: you edit a `.py` file, the behavior you expected doesn't show up, no error anywhere.

**Diagnosis**: check whether `uvicorn --reload` actually restarted —
`netstat -ano | grep :8000` (or whichever port), confirm the PID, and check its start time against
your edit time. On this Windows setup, WatchFiles has been observed to catch roughly 1 reload event
out of every 4 consecutive edits, silently continuing to serve the old process the rest of the time
— no warning, no error, it just doesn't reload.

**Fix**: kill the PID from `netstat`, start uvicorn fresh. Don't trust the reloader for anything
you're about to make a judgment call based on.

**Why this keeps coming back**: this is a platform-specific (Windows) WatchFiles reliability gap,
not a bug in this project's code — it will keep happening until either WatchFiles fixes it upstream
or this project moves to a container-based dev setup with a different file-watch backend.

---

## 2. Alembic `downgrade` fails partway, leaving the DB in a half-migrated state

**Symptom**: `alembic downgrade -1` (or `base`) errors with something like
`Cannot drop index ... needed in a foreign key constraint`, and `alembic_version` may now disagree
with what tables actually exist.

**Diagnosis**: look at the failing migration's `downgrade()` — this has happened **four separate
times** across four different migrations (auth, commerce, inventory/refunds, discovery/search), same
root cause every time: MySQL refuses to drop an index that's still backing a live FK constraint, but
autogenerate happily writes an explicit `drop_index(...)` for it before the corresponding
`drop_table(...)` — which would remove that index for free, safely, as part of dropping the table.

**Fix**: remove the explicit `drop_index()` calls for indexes on FK columns from `downgrade()`;
`drop_table()` already handles it. If you've already hit the error, restore the DB to a known-clean
state (drop and recreate from `alembic upgrade head` on a fresh schema, or restore from a backup —
see runbook 6) rather than trying to hand-patch a half-migrated schema.

**Why this keeps coming back**: autogenerate does this by default every time a new table has an FK
whose target column also has an index; check every new migration's `downgrade()` for this pattern
*before* running the full up→down→up cycle, don't wait for it to fail.

---

## 3. A row lock is held correctly, but two concurrent requests still see stale data / a lost update

**Symptom**: two things that should be mutually exclusive under a `SELECT ... FOR UPDATE` both
"succeed" using the same pre-lock values — an oversold variant, a stock adjustment that silently
reverts, a cart that doesn't show an item you just added.

**Diagnosis**: this is **not** a locking bug — the lock is real and does block the second
transaction for exactly as long as expected. The bug is one level up: the ORM object was already
loaded into the session's identity map *before* the lock was acquired (e.g. via an earlier eager-load
in the same request), and SQLAlchemy's default behavior is to leave an already-loaded object's
attributes alone on a subsequent `SELECT` unless told otherwise — so the code reads the *stale,
pre-lock* Python object instead of the freshly-locked, freshly-committed row. This exact class of
bug has been caught three times: cart-stale-after-mutation, inventory-adjustment-silently-reverted,
and (the most serious) the 50-concurrent-checkout stock lock that let all 50 succeed against
`stock=10`.

**Fix**: add `.execution_options(populate_existing=True)` to the query that re-reads the row after
acquiring the lock. Watch for the follow-on effect: `populate_existing` refreshes the *whole* object,
which can expire relationships you'd already eager-loaded and weren't expecting to need again —
add back a `selectinload(...)` for anything read immediately afterward, or you'll trade a stale-data
bug for a `MissingGreenlet` crash.

**Why this keeps coming back**: any code path that (a) loads an object, (b) later takes a lock on
that same row in the same session, and (c) re-reads it expecting fresh data is vulnerable by
default — this is SQLAlchemy's ordinary identity-map behavior working exactly as documented, just
counter-intuitive under a lock. Grep for `FOR UPDATE`/`with_for_update` and check every one has
`populate_existing=True` on the read that follows it.

---

## 4. CI fails on a fresh checkout with `ModuleNotFoundError` for a module that "exists" locally

**Symptom**: the app runs fine on your machine, but a fresh clone / CI checkout fails at import time
for a file you're sure you wrote.

**Diagnosis**: `git status` — if the file shows as untracked (`??`) rather than tracked, it was
never actually committed; it only "exists" on the machine that wrote it. This happened for real:
`core/storage.py` and `core/image_pipeline.py` were written and verified live in one session, sat
untracked for an entire subsequent session, and only surfaced when this repo's CI workflow ran on a
real GitHub Actions runner for the first time.

**Fix**: `git add` the missing file(s), verify with a genuinely clean environment before trusting
it's fixed — a fresh venv + `pip install -r requirements.txt` (or equivalent), not just re-running
your existing one, since your existing environment already has the file installed/cached and won't
reproduce the bug.

**Why this keeps coming back**: `git status` showing untracked files is easy to mentally file under
"I'll commit that later" indefinitely, especially mid-session when everything already works locally.
Treat any untracked file that the app actually imports as a blocker, not a todo.

---

## 5. A newly-added CI gate (linter, scanner) fails immediately on push, seemingly on itself

**Symptom**: you add a new CI check, test it locally, it passes — then the real CI run fails on the
exact same check, on a finding your local test didn't produce.

**Diagnosis**: check whether the tool's actual CI invocation matches what you tested locally. Real
example: a local `gitleaks detect --source .` dry run (full git history) came back clean after
adding a `.gitleaksignore` entry for one finding — but `gitleaks/gitleaks-action@v2` actually runs
`gitleaks detect --log-opts=-1` on a push event, scanning **only the new commit's diff**, not full
history. The done.MD paragraph describing the first finding reproduced its exact flagged shape
closely enough to trip the same rule again, in a different file, one commit later — something a
full-history local test wouldn't have caught either, since that finding didn't exist yet.

**Fix**: fetch the real job log (via the GitHub API if you have push access — a token already
cached by your git credential manager will work read-only) and read the *actual* command the action
ran, then reproduce that exact invocation locally before assuming a fix worked.

**Why this keeps coming back**: every scanning/linting GitHub Action has its own default scope
(some commits, some diff, some whole repo) that's easy to assume matches your local ad-hoc test
command — it usually doesn't exactly. Verify the real invocation once per tool, not once per fix.

---

## 6. Need to actually recover from data loss (or verify a backup is real)

**Symptom**: you need to prove a backup can actually be restored, or you actually need to restore
one.

**Diagnosis / Fix**: `python backend/scripts/backup_restore.py drill` — backs up the real database,
restores it into a disposable `<db>_restore_drill` database, compares row counts across the
financial-record and core-catalogue tables, then drops the drill database. Run this periodically,
not just once — a backup script that "exits 0" is not the same as a backup that's provably
restorable (see done.MD §20: the very first version of this script produced a plain-text file merely
*named* `.gz`, because `subprocess`'s `stdout=` redirects at the OS file-descriptor level and
silently bypassed Python's gzip compression entirely — `mysqldump` exited 0 the whole time).

For an actual restore (not a drill): `python backend/scripts/backup_restore.py restore --file
<path> --target-db <name>`.

**Why this keeps coming back**: any tool whose failure mode is "silently does less than it looks
like" (wrong compression, wrong file object, wrong scope) will pass a shallow check and fail a real
one — the drill's row-count comparison is the actual test; the exit code alone is not.

---

## 7. Two local dev servers collide on the same default port

**Symptom**: `uvicorn ... --port 8000` fails with `[WinError 10048] only one usage of each socket
address is normally permitted`, or requests silently go to the wrong application entirely.

**Diagnosis**: `netstat -ano | grep :8000` for the PID, then
`Get-CimInstance Win32_Process -Filter "ProcessId=<pid>"` (PowerShell) to see the **full command
line** — matching by process name alone (`python.exe`) is not enough on a machine that runs more
than one Python project; this exact ambiguity happened for real (an unrelated project's own uvicorn
server was already bound to :8000).

**Fix**: run your own server on a free port instead of fighting over the default one
(`--port 8010`, `--port 8020`, whatever's free); if you need the frontend's Vite proxy to reach it,
temporarily edit `vite.config.ts`'s proxy target and revert it afterward rather than leaving a
stale target checked in.

**Why this keeps coming back**: this machine runs multiple unrelated projects that all default to
the same conventional ports (3000, 5173, 8000) — there's no fix for this beyond checking before
assuming a port is yours.
