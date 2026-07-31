"""One-time migration of backend/media/* (75k+ product image files, local-disk-only today) to
whichever remote StorageBackend STORAGE_BACKEND selects (r2 or vercel_blob) — a serverless function
has no persistent local disk, so the existing LocalStorageBackend can't work once this app is
deployed to Vercel. (Originally built against Vercel Blob; switched to Cloudflare R2 after Blob's
Hobby-tier 2,000-operations/month cap turned out to be nowhere near this project's file count —
see done.MD for the full story. Kept provider-agnostic via get_storage_backend() so it works
against whichever backend is actually configured.)

Resumable by design: every successful upload is appended to a checkpoint file immediately, so an
interrupted run (rate limit, network blip, Ctrl-C) can just be re-run and picks up where it left
off rather than re-uploading everything. Reuses the real StorageBackend.save() (via a thread pool
for concurrency, since that method is synchronous) rather than re-implementing either provider's
upload contract here — one tested code path, not two.

Fixed worker-pool of N tasks pulling from a shared queue, each attempt bounded by a hard timeout —
not "create all 73k tasks up front". This project's media/ lives under a OneDrive-synced folder,
where a file can be a cloud-only placeholder that hangs for a long time on first read; an earlier
version read files directly in the coroutine (froze the whole event loop on one slow file) and
then, even after moving the read onto a worker thread, had no timeout at all — a single truly-stuck
read could tie up that thread forever with nothing to notice or route around it. Every attempt here
is wrapped in asyncio.wait_for, so a hung file is abandoned and retried rather than stalling a
worker indefinitely.

Run: python scripts/migrate_media_to_storage.py
Then: python scripts/update_media_urls_after_migration.py <new_public_base_url>
"""

import asyncio
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import get_settings  # noqa: E402
from app.core.storage import MEDIA_ROOT, StorageBackend, get_storage_backend  # noqa: E402

CHECKPOINT_PATH = Path(__file__).resolve().parent / ".media_migration_checkpoint.txt"
WORKER_COUNT = 12
MAX_ATTEMPTS = 4
ATTEMPT_TIMEOUT_SECONDS = 45
PROGRESS_EVERY = 250


def _load_checkpoint() -> set[str]:
    if not CHECKPOINT_PATH.exists():
        return set()
    return set(CHECKPOINT_PATH.read_text(encoding="utf-8").splitlines())


def _list_relative_paths() -> list[str]:
    return sorted(str(p.relative_to(MEDIA_ROOT)).replace("\\", "/") for p in MEDIA_ROOT.rglob("*") if p.is_file())


def _read_and_upload(backend: StorageBackend, relative_path: str) -> str:
    """Runs entirely on a worker thread (via asyncio.to_thread below) — reading and uploading
    together on the same thread means a slow read only ties up that one thread's turn, not the
    whole event loop."""
    data = (MEDIA_ROOT / relative_path).read_bytes()
    return backend.save(relative_path, data)


async def _upload_one(backend: StorageBackend, relative_path: str) -> tuple[str | None, str | None]:
    last_error = None
    for attempt in range(MAX_ATTEMPTS):
        try:
            url = await asyncio.wait_for(
                asyncio.to_thread(_read_and_upload, backend, relative_path), timeout=ATTEMPT_TIMEOUT_SECONDS
            )
            return url, None
        except TimeoutError:
            last_error = f"timed out after {ATTEMPT_TIMEOUT_SECONDS}s"
        except Exception as exc:  # noqa: BLE001 — genuinely want to retry on anything, then report
            last_error = str(exc)
        await asyncio.sleep(1.5 * (attempt + 1))
    return None, last_error


class _Progress:
    def __init__(self, total: int):
        self.total = total
        self.completed = 0
        self.failures: list[tuple[str, str]] = []
        self.sample_url: str | None = None
        self.started = time.monotonic()
        self.checkpoint_file = open(CHECKPOINT_PATH, "a", encoding="utf-8")  # noqa: SIM115 — held for the whole run

    def record_success(self, relative_path: str, url: str) -> None:
        self.checkpoint_file.write(relative_path + "\n")
        self.checkpoint_file.flush()
        self.completed += 1
        self.sample_url = self.sample_url or url
        if self.completed % PROGRESS_EVERY == 0:
            elapsed = time.monotonic() - self.started
            rate = self.completed / elapsed if elapsed else 0
            done_total = self.completed + len(self.failures)
            print(f"  {done_total}/{self.total} processed, {self.completed} uploaded ({rate:.1f}/s)...", flush=True)

    def record_failure(self, relative_path: str, error: str) -> None:
        self.failures.append((relative_path, error))
        print(f"  FAILED: {relative_path} -> {error}", flush=True)

    def close(self) -> None:
        self.checkpoint_file.close()


async def _worker(queue: asyncio.Queue, backend: StorageBackend, progress: _Progress) -> None:
    while True:
        relative_path = await queue.get()
        if relative_path is None:
            queue.task_done()
            return
        url, error = await _upload_one(backend, relative_path)
        if url is not None:
            progress.record_success(relative_path, url)
        else:
            progress.record_failure(relative_path, error or "unknown error")
        queue.task_done()


async def main() -> None:
    settings = get_settings()
    if settings.storage_backend == "local":
        print("STORAGE_BACKEND is 'local' — nothing to migrate to.")
        sys.exit(1)

    backend = get_storage_backend()
    all_paths = _list_relative_paths()
    done = _load_checkpoint()
    todo = [p for p in all_paths if p not in done]
    print(
        f"Backend: {settings.storage_backend}. {len(all_paths)} total files, "
        f"{len(done)} already migrated, {len(todo)} remaining.",
        flush=True,
    )
    if not todo:
        print("Nothing to do.")
        return

    queue: asyncio.Queue = asyncio.Queue()
    for p in todo:
        queue.put_nowait(p)
    for _ in range(WORKER_COUNT):
        queue.put_nowait(None)  # one sentinel per worker so each exits once the real work is drained

    progress = _Progress(total=len(todo))
    workers = [asyncio.create_task(_worker(queue, backend, progress)) for _ in range(WORKER_COUNT)]
    try:
        await asyncio.gather(*workers)
    finally:
        progress.close()

    elapsed = time.monotonic() - progress.started
    print(f"\nDone in {elapsed:.0f}s. {progress.completed} uploaded this run, {len(progress.failures)} failed.")
    if progress.sample_url:
        print(f"Sample URL: {progress.sample_url}")
    if progress.failures:
        print(f"\n{len(progress.failures)} failures (re-run this script to retry them):")
        for relative_path, error in progress.failures[:20]:
            print(f"  {relative_path}: {error}")


if __name__ == "__main__":
    asyncio.run(main())
