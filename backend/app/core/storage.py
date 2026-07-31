"""Object storage, abstracted the same way as PaymentProvider/MailBackend (spec §12.1/§5.3's
`StorageBackend` interface) so a real MinIO/S3 backend is a config + adapter change. A local
filesystem backend (native-Windows dev, no MinIO — see done.MD stack deviations), a Vercel Blob
backend, and a Cloudflare R2 backend (the one actually used for the Vercel deployment — Blob's
Hobby-tier 2,000-operations/month cap turned out to be nowhere near this project's 75k+ media
files, see done.MD) all implement it; `STORAGE_BACKEND` picks which one `get_storage_backend()`
returns."""

from __future__ import annotations

import mimetypes
from pathlib import Path
from typing import Protocol

import boto3
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


class CloudflareR2StorageBackend:
    """S3-compatible object storage — R2's API is a subset of S3's, so this is a plain boto3 S3
    client pointed at R2's account-scoped endpoint rather than a bespoke HTTP client, unlike
    VercelBlobStorageBackend above (Blob has no S3-compatible API to reuse a library against).
    R2 has no fixed, derivable public URL the way a Blob store does — the bucket's public-read
    prefix (an r2.dev subdomain or a custom domain) is a separate, required setting."""

    def __init__(self) -> None:
        settings = get_settings()
        missing = [
            name
            for name, value in (
                ("R2_ACCOUNT_ID", settings.r2_account_id),
                ("R2_ACCESS_KEY_ID", settings.r2_access_key_id),
                ("R2_SECRET_ACCESS_KEY", settings.r2_secret_access_key),
                ("R2_BUCKET_NAME", settings.r2_bucket_name),
                ("R2_PUBLIC_BASE_URL", settings.r2_public_base_url),
            )
            if not value
        ]
        if missing:
            raise RuntimeError(f"Missing settings for the r2 storage backend: {', '.join(missing)}")

        self._bucket = settings.r2_bucket_name
        self._public_base_url = settings.r2_public_base_url.rstrip("/")
        self._client = boto3.client(
            "s3",
            endpoint_url=f"https://{settings.r2_account_id}.r2.cloudflarestorage.com",
            aws_access_key_id=settings.r2_access_key_id,
            aws_secret_access_key=settings.r2_secret_access_key,
            region_name="auto",
        )

    def save(self, relative_path: str, data: bytes) -> str:
        content_type, _ = mimetypes.guess_type(relative_path)
        self._client.put_object(
            Bucket=self._bucket,
            Key=relative_path,
            Body=data,
            ContentType=content_type or "application/octet-stream",
        )
        return f"{self._public_base_url}/{relative_path}"


def get_storage_backend() -> StorageBackend:
    backend = get_settings().storage_backend
    if backend == "vercel_blob":
        return VercelBlobStorageBackend()
    if backend == "r2":
        return CloudflareR2StorageBackend()
    return LocalStorageBackend()
