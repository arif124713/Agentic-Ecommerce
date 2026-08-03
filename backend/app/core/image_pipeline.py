"""Real download -> validate -> resize -> transcode -> blurhash pipeline (spec §7.2's "media"
ingestion stage). Two things spec §7.2/§5.2 name are deliberately not attempted here:

- **AVIF**: Pillow needs the separate `pillow-avif-plugin` codec, and nothing downstream would
  consume a third image format yet (the frontend only ever picks between `url`/`url_webp`) — not
  worth the extra dependency for a format nothing reads.
- **Multiple responsive sizes**: `product_images` has exactly one `url`/`url_webp` pair per row
  (spec §8.3's actual schema), and no frontend code ever requests a smaller variant of an image —
  generating extra on-disk sizes nothing links to would be dead weight, not a feature.

What IS real: every image is actually downloaded, decode-validated (not just HEAD-checked), resized
to a sane display cap, transcoded to both a universal JPEG fallback and a smaller WebP, and given a
real blurhash computed from its own pixels — then self-hosted via `StorageBackend` instead of
hotlinking the source CDN forever.
"""

from __future__ import annotations

import io
from dataclasses import dataclass

import blurhash
import httpx
import numpy as np
from PIL import Image, UnidentifiedImageError

from app.core.storage import StorageBackend

DISPLAY_MAX_DIM = 832  # matches the existing thumbnail-upgrade target already used at ingest time
BLURHASH_SAMPLE_DIM = 32
BLURHASH_COMPONENTS_X = 4
BLURHASH_COMPONENTS_Y = 3
JPEG_QUALITY = 85
WEBP_QUALITY = 82


@dataclass
class ProcessedImage:
    url: str
    url_webp: str
    blurhash: str
    width: int
    height: int


async def _fetch_bytes(client: httpx.AsyncClient, url: str) -> bytes | None:
    try:
        resp = await client.get(url, timeout=15.0, follow_redirects=True)
        resp.raise_for_status()
        return resp.content
    except (httpx.HTTPError, httpx.TimeoutException):
        return None


def _resize(img: Image.Image, max_dim: int) -> Image.Image:
    if max(img.size) <= max_dim:
        return img
    ratio = max_dim / max(img.size)
    new_size = (max(1, round(img.width * ratio)), max(1, round(img.height * ratio)))
    return img.resize(new_size, Image.Resampling.LANCZOS)


def _compute_blurhash(img: Image.Image) -> str:
    small = img.resize((BLURHASH_SAMPLE_DIM, BLURHASH_SAMPLE_DIM), Image.Resampling.LANCZOS)
    arr = np.array(small)
    return blurhash.encode(arr, components_x=BLURHASH_COMPONENTS_X, components_y=BLURHASH_COMPONENTS_Y)


async def process_image(
    client: httpx.AsyncClient, storage: StorageBackend, *, source_url: str, dest_key: str
) -> ProcessedImage | None:
    """Downloads `source_url`, validates it decodes as a real image, resizes it, computes a
    blurhash, and saves a JPEG + WebP pair under `dest_key` via `storage`. Never raises — a bad
    or dead source URL just means that one image is skipped, not that the whole run aborts."""
    raw = await _fetch_bytes(client, source_url)
    if raw is None:
        return None

    try:
        probe = Image.open(io.BytesIO(raw))
        probe.verify()  # cheap corruption check; verify() invalidates the handle, so reopen
        img = Image.open(io.BytesIO(raw)).convert("RGB")
    except (UnidentifiedImageError, OSError, ValueError):
        return None

    img = _resize(img, DISPLAY_MAX_DIM)
    image_hash = _compute_blurhash(img)

    jpeg_buf = io.BytesIO()
    img.save(jpeg_buf, format="JPEG", quality=JPEG_QUALITY)
    webp_buf = io.BytesIO()
    img.save(webp_buf, format="WEBP", quality=WEBP_QUALITY)

    url = storage.save(f"{dest_key}.jpg", jpeg_buf.getvalue())
    url_webp = storage.save(f"{dest_key}.webp", webp_buf.getvalue())

    return ProcessedImage(url=url, url_webp=url_webp, blurhash=image_hash, width=img.width, height=img.height)
