# BlackCart

Full spec: [`spec.MD`](./spec.MD). This README covers what's actually built so far and how to run it.

## Status

**Phase 0 (Foundations) + start of Phase 1 (Data & Catalogue)**, per the spec's roadmap (§29). Running
**natively on Windows** — no Docker/Redis/Celery/Elasticsearch yet (see "What's deferred" below).

Built so far:
- FastAPI backend: `Settings`, structured logging, standard error envelope + response envelope
  middleware, request-ID propagation, `/healthz` and `/readyz`, Alembic migrations.
- Catalogue schema (brands, categories, products, variants, images, attributes) with the materialised
  category path from spec §8.3, and public read endpoints (`/products`, `/products/{slug}`,
  `/categories`, `/brands`) with filtering, brand facets, and cursor-free pagination.
- **Real data**: the actual Kaggle Flipkart Fashion Products dataset (30,000 raw records) is
  downloaded and ingested via `backend/scripts/ingest_flipkart.py` — a condensed version of the
  clean → normalise → enrich → load pipeline from spec §7. 8,136 real products loaded after
  quarantining 1,627 malformed rows and deduping ~20K near-identical listings (rejection/dedup
  reasoning in spec §7.3/§7.5). Real Flipkart CDN product photos, titles, brands, prices, and
  descriptions; variant stock/sizes/ratings-count are synthesized per-pid (deterministically seeded)
  since the source dataset has none — this is explicitly what spec §7.3 prescribes for that gap.
  A lighter synthetic-only seed (`scripts/seed.py`) still exists as a fallback.
- React 19 + Vite + TypeScript + Tailwind v4 frontend styled with the exact black/monochrome design
  tokens from spec §18: Home, category listing (PLP) with filters/sort/facets, and product detail (PDP)
  with colour/size selection.

### About the source data

This dataset (see the Kaggle page) is heavily skewed towards menswear (~93% of titles/attributes
resolve to "Men") and has real, spec-anticipated dirtiness: ~325 brand names are truncated at the
source (e.g. "REEB", "Pu", "ECKO Unl" — not a bug introduced here, verified against the raw JSON),
~2,068 records have no brand at all (mapped to "Unbranded"), and some Flipkart CDN image URLs from
this 2021 crawl may be dead. Category taxonomy was hand-mapped from the observed
`(category, sub_category)` pairs into a gender (top) × leaf structure — see `CATEGORY_MAP` in the
ingestion script.

## Running it

**Backend** (from `backend/`, using the existing `myenv` venv at the repo root):
```
../myenv/Scripts/python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

**Frontend** (from `frontend/`):
```
npm run dev
```
Vite proxies `/api/v1/*` to `http://127.0.0.1:8000` (see `vite.config.ts`), so just open
`http://localhost:5173`.

**Database**: uses your local MySQL 8 install (`blackcart` database, credentials from `.env` /
`mysql_password`). Migrations: `alembic upgrade head` from `backend/`. Real data:
`python scripts/ingest_flipkart.py` from `backend/` (re-running truncates and reloads the catalogue
tables; takes ~5s). Raw dataset lives in `data/raw/` (gitignored — see below), quarantine reports in
`data/quarantine/`.

## Ingestion CLI & media pipeline

`backend/scripts/ingest_flipkart.py --stage {fetch,profile,load,media,verify}` (spec §7.2), condensed
from 9 stages to 5 real, independently-runnable ones — see the module docstring for exactly why
`clean`/`normalise`/`enrich` stay merged into `load` and why there's no `index` stage (no
Elasticsearch in this stack).

- `fetch` — downloads the dataset from Kaggle (idempotent; skips if `data/raw/...json` exists).
- `profile` — data-quality report over the raw dataset (null rates, cardinality, duplicate keys)
  before any cleaning happens.
- `load` — the existing clean → normalise → enrich → load pass into the catalogue tables.
- `media` — real image pipeline: downloads every product image, validates it decodes, resizes it,
  transcodes to WebP + a JPEG fallback, computes a blurhash, and self-hosts the result via
  `StorageBackend` (`core/storage.py` — local filesystem today, `backend/media/`, served at
  `/media/*`; a real MinIO/S3 backend is a config + adapter swap). Chunked with incremental
  commits (`--limit N` to test on a subset), so an interrupted run only loses its current
  in-flight chunk, not the whole thing — safe to just re-invoke.
- `verify` — row counts, orphan checks, price sanity, and a local-media-reachability sample;
  exits non-zero on any integrity failure.

Not attempted: AVIF (needs a separate Pillow codec plugin nothing downstream would consume yet)
and multiple responsive image sizes (`product_images` only has one `url`/`url_webp` pair per spec
§8.3's actual schema, and no frontend code requests a smaller variant) — see done.MD for the full
writeup, including a real CORP-header bug this pipeline's first live verification pass caught
(images 200'd but silently failed to render until `Cross-Origin-Resource-Policy` was scoped to
allow `/media/*` cross-origin).

## What's deferred

The full spec assumes Docker Compose orchestrating MySQL, Redis, Elasticsearch, MinIO, and Celery.
Docker isn't installed on this machine, so for now:
- **Redis** — rate limiting now runs on real Upstash Redis in production (`RATE_LIMIT_BACKEND=redis`,
  via `vercel integration add upstash/upstash-kv`; REST-based, no persistent connection needed on
  Vercel's serverless functions). Local dev/tests still default to the original in-process counter
  (`RATE_LIMIT_BACKEND=memory`) so neither needs a live Redis. Sessions-as-cache is not implemented.
- **Celery** — not wired up; conflicts with the Vercel deployment target anyway. Background work
  (async payment webhook, delivery simulation) runs via real signature-verified HTTP endpoints
  instead, not a task queue.
- **Elasticsearch** — Vercel's Marketplace has no plain-ES product, so Algolia fills that role in
  production (`SEARCH_BACKEND=algolia`, via `vercel integration add algolia/application`) for the
  q-given default-sort search path; MySQL `LIKE` matching with a broadened fallback (done.MD §11)
  is still what plain category browsing and local dev/tests use. See done.MD §29 for the full
  writeup, including a real Algolia typo-tolerance false positive it caught and fixed.
- Brand fuzzy-merge (rapidfuzz) is built — see done.MD §26.
- **Support tickets, CMS/banners** — not started.

## Secrets

`.env` (git-ignored) holds `mysql_password` and `kaggle_api_key` — both real secrets. `data/raw/`
(the downloaded dataset) is also git-ignored since it's regeneratable and large. Neither should ever
be committed.

## Continuous Integration

`.github/workflows/ci.yml` runs on every push/PR to `main` (and can be triggered manually via
`workflow_dispatch`):

- **secrets** job — `gitleaks` full-history secret scan. False positives are handled via
  `.gitleaksignore` with a documented fingerprint + justification, never a blanket disable — see
  done.MD §18 for a real one it caught (and a second, self-inflicted one from done.MD's own prose).
- **backend** job — spins up a real MySQL 8 service container, then runs `ruff`, `pytest`
  (with coverage) against a fresh `blackcart_test` database, `pip-audit` against
  `requirements-dev.txt` (runtime deps plus the dev/tooling/ingestion-only ones — 0 known
  vulnerabilities is the gate, per spec §2.3), and a full
  `alembic upgrade head → downgrade base → upgrade head → check` cycle against a second, separate
  empty database (`blackcart_ci`) — this is a genuine from-scratch migration test, which is what
  actually caught and fixed three latent migration-ordering bugs while this workflow was being built
  (see done.MD §15 — the baseline migration only used to create one table out of seven). `mypy` is a
  hard gate too now — see done.MD for the writeup of the 46 pre-existing errors it caught and fixed.
- **frontend** job — `npm ci`, `npm audit --audit-level=high`, `tsc -b`, `oxlint`, `vitest run`,
  `vite build`.

### Branch protection (do this in GitHub's UI — not something this repo/CI config can set for you)

Once this repo has a GitHub remote:

1. **Settings → Branches → Add branch protection rule**, pattern `main`.
2. Enable **"Require a pull request before merging"**.
3. Enable **"Require status checks to pass before merging"**, then search for and select all three:
   `Secret scan (gitleaks)`, `Backend (ruff · mypy · pytest+coverage · alembic)`, and
   `Frontend (tsc · oxlint · vitest · build)` — they only appear in that search list after the
   workflow has run at least once on the repo, so push once first, then come back and add the rule.
4. Optionally enable **"Require branches to be up to date before merging"** so a stale PR must
   rebase/merge `main` before the checks are trusted.
5. Consider **"Do not allow bypassing the above settings"** to apply the rule to admins too.

## Load testing & backup/restore

- `k6 run -e BASE_URL=http://127.0.0.1:PORT backend/scripts/loadtest.js` against a locally-running
  backend. Verifies spec §23's API latency budget (reads p95 < 200ms, writes p95 < 500ms) — see
  done.MD §19 for real measured numbers.
- `python backend/scripts/backup_restore.py drill` — a real, actually-run backup/restore drill
  against local MySQL (spec §26). See done.MD §20.

See [`RUNBOOKS.md`](./RUNBOOKS.md) for real incidents this project has hit (stale-reload, migration
FK/index ordering, the stock-lock stale-read bug class, CI checkout gaps, scanner false positives,
port collisions) with symptom → diagnosis → fix for each.

## Known gaps to close next

- Initial JS bundle is ~191 KB gzipped (Vite's own build warning flags it as a single chunk over
  500 KB before gzip) — no route-level code splitting yet.
- No Playwright E2E suite yet. Load testing and dependency/secret scanning now exist (see above and
  Continuous Integration) but aren't wired into CI as a recurring, unattended job — load testing
  needs a running server + seeded data, not a fit for a per-push CI gate; dependency/secret scanning
  already runs on every push (see Continuous Integration above).

## Directory layout

Matches spec §27. See `backend/app` and `frontend/src` for the code; `docs/` is scaffolded for ADRs.
