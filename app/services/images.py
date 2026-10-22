"""Image proxy: Telegram file_id -> resized WebP bytes, cached on local disk.

Why: Telegram stores product photos for us (free, survives redeploys). The Mini App can't
download them directly because that needs the bot token. The cache is only a cache — losing
it on redeploy just means a one-time re-fetch.
"""
import asyncio
import hashlib
import io
import logging
import os
import time
from pathlib import Path
from typing import Optional

import httpx
from PIL import Image, ImageOps

from app.config import get_settings

log = logging.getLogger(__name__)

ALLOWED_WIDTHS = (320, 640, 1024)
_locks: dict[str, asyncio.Lock] = {}


class ImageNotFound(Exception):
    pass


def _cache_path(file_id: str, width: int) -> Path:
    s = get_settings()
    key = hashlib.sha256(f"{file_id}:{width}".encode()).hexdigest()
    return Path(s.IMAGE_CACHE_DIR) / key[:2] / f"{key}.webp"


async def _download_original(file_id: str) -> bytes:
    s = get_settings()
    base = f"https://api.telegram.org/bot{s.BOT_TOKEN}"
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{base}/getFile", params={"file_id": file_id})
        if r.status_code != 200 or not r.json().get("ok"):
            raise ImageNotFound(file_id)
        path = r.json()["result"]["file_path"]
        f = await client.get(f"https://api.telegram.org/file/bot{s.BOT_TOKEN}/{path}")
        if f.status_code != 200:
            raise ImageNotFound(file_id)
        return f.content


def _resize_to_webp(data: bytes, width: int) -> bytes:
    img = Image.open(io.BytesIO(data))
    img = ImageOps.exif_transpose(img).convert("RGB")
    if img.width > width:
        img.thumbnail((width, width * 4), Image.LANCZOS)
    out = io.BytesIO()
    img.save(out, "WEBP", quality=78, method=4)
    return out.getvalue()


def _evict_if_needed() -> None:
    """Simple LRU by mtime; runs after a write. Cheap enough for a few thousand files."""
    s = get_settings()
    root = Path(s.IMAGE_CACHE_DIR)
    limit = s.IMAGE_CACHE_MAX_MB * 1024 * 1024
    files = [(p.stat().st_mtime, p.stat().st_size, p) for p in root.rglob("*.webp")]
    total = sum(sz for _, sz, _ in files)
    if total <= limit:
        return
    for _, sz, p in sorted(files):
        try:
            p.unlink()
            total -= sz
        except OSError:
            pass
        if total <= limit * 0.8:
            break


async def get_image(file_id: str, width: int = 640) -> bytes:
    """Returns WebP bytes. Raises ImageNotFound if Telegram no longer knows the file."""
    width = width if width in ALLOWED_WIDTHS else 640
    path = _cache_path(file_id, width)
    if path.exists():
        os.utime(path, None)  # touch for LRU
        return path.read_bytes()

    lock = _locks.setdefault(f"{file_id}:{width}", asyncio.Lock())
    async with lock:
        if path.exists():
            return path.read_bytes()
        original = await _download_original(file_id)
        data = await asyncio.to_thread(_resize_to_webp, original, width)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(f".{int(time.time() * 1000)}.tmp")
        tmp.write_bytes(data)
        tmp.replace(path)
        await asyncio.to_thread(_evict_if_needed)
        return data


def image_url(file_id: Optional[str], width: int = 320) -> Optional[str]:
    if not file_id:
        return None
    return f"{get_settings().PUBLIC_URL}/api/img/{file_id}?w={width}"
