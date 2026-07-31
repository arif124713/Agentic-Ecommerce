"""Object storage, abstracted the same way as PaymentProvider/MailBackend (spec §12.1/§5.3's
`StorageBackend` interface) so a real MinIO/S3 backend is a config + adapter change. A local
filesystem backend (native-Windows dev, no MinIO — see done.MD stack deviations) and a Vercel Blob
backend (for the Vercel deployment — serverless functions have no persistent local disk) both
implement it; `STORAGE_BACKEND` picks which one `get_storage_backend()` returns."""

from __future__ import annotations

import mimetypes
from pathlib import Path
from typing import Protocol

import httpx

from app.core.config import get_settings

MEDIA_ROOT = Path(__file__).resolve().parents[2] / "media"

# Reverse-engineered from @vercel/blob's own source (no public raw-REST doc exists — Blob is
# meant to be used via the SDK — so this was verified against packages/blob/src/{api,
# put-helpers}.ts on GitHub rather than guessed): PUT to this endpoint with the pathname as a
# query param, a bearer token, and an explicit API version header.
_BLOB_API_URL = "https://vercel.com/api/blob"
_BLOB_API_VERSION = "12"


class StorageBackend(Protocol):
    def save(self, relative_path: str, data: bytes) -> str:
        """Persists `data` at `relative_path` and returns its publicly-fetchable URL."""
        ...


class LocalStorageBackend:
    """Writes under backend/media/, served back out via main.py's `/media` static mount."""

    def save(self, relative_path: str, data: bytes) -> str:
        dest = MEDIA_ROOT / relative_path
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
        return f"{get_settings().backend_base_url}/media/{relative_path}"


class VercelBlobStorageBackend:
    """No persistent local disk on a Vercel serverless function, so product images live in Vercel
    Blob instead. `add_random_suffix=0`/`allow_overwrite=1` keep `relative_path` as the literal
    Blob pathname (matching what LocalStorageBackend uses as a path), so every blob for this store
    shares one fixed URL prefix — re-running the ingestion pipeline overwrites in place rather than
    accumulating orphaned duplicates under randomised names."""

    def __init__(self) -> None:
        token = get_settings().blob_read_write_token
        if not token:
            raise RuntimeError("BLOB_READ_WRITE_TOKEN must be set to use the vercel_blob storage backend.")
        self._token = token

    def save(self, relative_path: str, data: bytes) -> str:
        content_type, _ = mimetypes.guess_type(relative_path)
        response = httpx.put(
            _BLOB_API_URL,
            params={"pathname": relative_path},
            headers={
                "authorization": f"Bearer {self._token}",
                "x-api-version": _BLOB_API_VERSION,
                "x-vercel-blob-access": "public",
                "x-content-type": content_type or "application/octet-stream",
                "x-add-random-suffix": "0",
                "x-allow-overwrite": "1",
            },
            content=data,
            timeout=60.0,
        )
        response.raise_for_status()
        return response.json()["url"]


def get_storage_backend() -> StorageBackend:
    if get_settings().storage_backend == "vercel_blob":
        return VercelBlobStorageBackend()
    return LocalStorageBackend()
