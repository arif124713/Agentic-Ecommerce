"""Object storage, abstracted the same way as PaymentProvider/MailBackend (spec §12.1/§5.3's
`StorageBackend` interface) so a real MinIO/S3 backend is a config + adapter change. Only a local
filesystem backend exists today — no MinIO in this native-Windows dev setup (see done.MD stack
deviations)."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from app.core.config import get_settings

MEDIA_ROOT = Path(__file__).resolve().parents[2] / "media"


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


def get_storage_backend() -> StorageBackend:
    return LocalStorageBackend()
