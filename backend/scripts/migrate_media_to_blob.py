"""One-time migration of backend/media/* (75k+ product image files, local-disk-only today) to
Vercel Blob — a serverless function has no persistent local disk, so the existing
LocalStorageBackend can't work once this app is deployed to Vercel.

Resumable by design: every successful upload is appended to a checkpoint file immediately, so an
interrupted run (rate limit, network blip, Ctrl-C) can just be re-run and picks up where it left
off rather than re-uploading everything. Reuses VercelBlobStorageBackend.save() directly (via a
thread pool for concurrency, since that method is synchronous) rather than re-implementing the
Blob API contract here — one tested code path, not two.

Run: python scripts/migrate_media_to_blob.py
Then: python scripts/update_media_urls_after_migration.py  (rewrites DB rows to the new URLs)
"""

import asyncio
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import get_settings  # noqa: E402
from app.core.storage import MEDIA_ROOT, VercelBlobStorageBackend  # noqa: E402

CHECKPOINT_PATH = Path(__file__).resolve().parent / ".blob_migration_checkpoint.txt"
# Comfortably under Vercel Blob's Hobby-plan rate limit (1500 Advanced Operations/min = 25/s) —
# real per-request latency means actual throughput stays well under the ceiling even so.
CONCURRENCY = 10
MAX_ATTEMPTS = 4


def _load_checkpoint() -> set[str]:
    if not CHECKPOINT_PATH.exists():
        return set()
    return set(CHECKPOINT_PATH.read_text(encoding="utf-8").splitlines())


def _list_relative_paths() -> list[str]:
    return sorted(str(p.relative_to(MEDIA_ROOT)).replace("\\", "/") for p in MEDIA_ROOT.rglob("*") if p.is_file())


def _read_and_upload(backend: VercelBlobStorageBackend, relative_path: str) -> str:
    """Runs entirely on a worker thread (via asyncio.to_thread below) — the file read used to
    happen directly in the coroutine, which blocks the *whole* single-threaded event loop for its
    duration. Fast for a normal local file, but this project's media/ lives under a OneDrive-synced
    folder, where some files can be cloud-only placeholders that take real time to hydrate on
    first read — one such file froze every other concurrent upload until it finished. Reading and
    uploading together on the same thread means a slow read only stalls that one thread, not the
    other nine."""
    data = (MEDIA_ROOT / relative_path).read_bytes()
    return backend.save(relative_path, data)


async def _upload_one(
    backend: VercelBlobStorageBackend, semaphore: asyncio.Semaphore, relative_path: str
) -> tuple[str, str | None, str | None]:
    async with semaphore:
        last_error = None
        for attempt in range(MAX_ATTEMPTS):
            try:
                url = await asyncio.to_thread(_read_and_upload, backend, relative_path)
                return relative_path, url, None
            except Exception as exc:  # noqa: BLE001 — genuinely want to retry on anything, then report
                last_error = str(exc)
                await asyncio.sleep(1.5 * (attempt + 1))
        return relative_path, None, last_error


async def main() -> None:
    settings = get_settings()
    if not settings.blob_read_write_token:
        print("BLOB_READ_WRITE_TOKEN is not set — nothing to do.")
        sys.exit(1)

    backend = VercelBlobStorageBackend()
    all_paths = _list_relative_paths()
    done = _load_checkpoint()
    todo = [p for p in all_paths if p not in done]
    print(f"{len(all_paths)} total files, {len(done)} already migrated, {len(todo)} remaining.")
    if not todo:
        print("Nothing to do.")
        return

    semaphore = asyncio.Semaphore(CONCURRENCY)
    checkpoint_file = open(CHECKPOINT_PATH, "a", encoding="utf-8")  # noqa: SIM115 — held open for the whole run
    completed = 0
    failures: list[tuple[str, str]] = []
    sample_url = None
    started = time.monotonic()

    try:
        tasks = [asyncio.create_task(_upload_one(backend, semaphore, p)) for p in todo]
        for coro in asyncio.as_completed(tasks):
            relative_path, url, error = await coro
            if url is not None:
                checkpoint_file.write(relative_path + "\n")
                checkpoint_file.flush()
                completed += 1
                sample_url = sample_url or url
                if completed % 1000 == 0:
                    elapsed = time.monotonic() - started
                    rate = completed / elapsed if elapsed else 0
                    print(f"  {completed}/{len(todo)} uploaded ({rate:.1f}/s)...")
            else:
                failures.append((relative_path, error or "unknown error"))
                print(f"  FAILED: {relative_path} -> {error}")
    finally:
        checkpoint_file.close()

    elapsed = time.monotonic() - started
    print(f"\nDone in {elapsed:.0f}s. {completed} uploaded this run, {len(failures)} failed.")
    if sample_url:
        print(f"Sample blob URL: {sample_url}")
    if failures:
        print(f"\n{len(failures)} failures (re-run this script to retry them):")
        for relative_path, error in failures[:20]:
            print(f"  {relative_path}: {error}")


if __name__ == "__main__":
    asyncio.run(main())
