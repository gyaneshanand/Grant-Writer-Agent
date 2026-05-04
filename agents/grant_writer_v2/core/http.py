"""
Async HTTP client with retry logic and on-disk content cache.
Used by Layer 1 (SerpAPI) and Layer 2 (page fetching).
"""
import asyncio
import hashlib
import json
import os
from pathlib import Path
from typing import Optional

import httpx

from agents.grant_writer_v2.config import v2_settings
from agents.grant_writer_v2.core.logger import get_logger

logger = get_logger("http")

_CACHE_DIR = Path(v2_settings.CACHE_DIR)
_CACHE_DIR.mkdir(parents=True, exist_ok=True)

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


def _cache_path(key: str) -> Path:
    return _CACHE_DIR / f"{key}.json"


def _cache_get(key: str) -> Optional[dict]:
    p = _cache_path(key)
    if p.exists():
        try:
            return json.loads(p.read_text())
        except Exception:
            pass
    return None


def _cache_set(key: str, data: dict) -> None:
    try:
        _cache_path(key).write_text(json.dumps(data))
    except Exception as e:
        logger.warning(f"Cache write failed for {key}: {e}")


def url_cache_key(url: str) -> str:
    return hashlib.sha256(url.encode()).hexdigest()[:32]


async def fetch(
    url: str,
    *,
    use_cache: bool = True,
    timeout: Optional[int] = None,
    headers: Optional[dict] = None,
) -> dict:
    """
    Fetch a URL. Returns dict with keys:
      url, status_code, content_type, text, bytes_fetched, from_cache, error
    """
    key = url_cache_key(url)
    if use_cache:
        cached = _cache_get(key)
        if cached:
            cached["from_cache"] = True
            return cached

    result = {
        "url": url,
        "status_code": 0,
        "content_type": "",
        "text": "",
        "bytes_fetched": 0,
        "from_cache": False,
        "error": None,
    }

    _timeout = timeout or v2_settings.HTTP_TIMEOUT_SECONDS
    _headers = {**_HEADERS, **(headers or {})}

    for attempt in range(v2_settings.HTTP_MAX_RETRIES):
        try:
            async with httpx.AsyncClient(follow_redirects=True, timeout=_timeout) as client:
                resp = await client.get(url, headers=_headers)
                content = resp.content
                result["status_code"] = resp.status_code
                result["content_type"] = resp.headers.get("content-type", "")
                result["bytes_fetched"] = len(content)

                # Decode text for HTML; keep raw bytes ref for PDFs
                if "text" in result["content_type"] or "html" in result["content_type"]:
                    result["text"] = content.decode("utf-8", errors="replace")
                elif "pdf" in result["content_type"]:
                    # Store base64 for PDF bytes so it can be cached as JSON
                    import base64
                    result["text"] = ""
                    result["pdf_b64"] = base64.b64encode(content).decode()
                else:
                    result["text"] = content.decode("utf-8", errors="replace")

                if use_cache and resp.status_code == 200:
                    _cache_set(key, result)
                return result

        except httpx.TimeoutException:
            result["error"] = "timeout"
            if attempt < v2_settings.HTTP_MAX_RETRIES - 1:
                await asyncio.sleep(2 ** attempt)
        except Exception as e:
            result["error"] = str(e)
            break

    return result


async def fetch_json(url: str, *, params: dict | None = None, headers: dict | None = None) -> dict:
    """Fetch a JSON endpoint (no caching — used for SerpAPI calls)."""
    _timeout = v2_settings.HTTP_TIMEOUT_SECONDS
    _headers = {**_HEADERS, **(headers or {})}
    async with httpx.AsyncClient(follow_redirects=True, timeout=_timeout) as client:
        resp = await client.get(url, params=params, headers=_headers)
        resp.raise_for_status()
        return resp.json()
