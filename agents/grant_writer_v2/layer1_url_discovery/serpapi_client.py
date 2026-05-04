"""SerpAPI client for Layer 1 URL discovery."""
import hashlib
from typing import Any

from agents.grant_writer_v2.config import v2_settings
from agents.grant_writer_v2.core.http import fetch_json
from agents.grant_writer_v2.core.logger import get_logger

logger = get_logger("layer1.serpapi")

SERPAPI_BASE = "https://serpapi.com/search"


def build_query(org_name: str, state: str, city: str | None = None) -> str:
    """Construct a SerpAPI search query to find the foundation's official website."""
    location = f"{city}, {state}" if city else state
    return f'"{org_name}" foundation official site {location}'


def build_fallback_query(org_name: str, state: str) -> str:
    """Broader fallback query — no quotes, no city, drops 'foundation' suffix noise."""
    # Strip common suffixes so "AHEPA Rochester Foundation" → "AHEPA Rochester"
    import re
    name = re.sub(r'\b(foundation|fund|trust|group|inc|corp|organization)\b', '', org_name, flags=re.IGNORECASE).strip()
    return f"{name} official website {state}"


async def search(query: str) -> dict[str, Any]:
    """
    Execute a SerpAPI Google search and return the raw JSON.
    Raises on HTTP error.
    """
    params = {
        "q": query,
        "api_key": v2_settings.SERPAPI_API_KEY,
        "num": 10,
        "hl": "en",
        "gl": "us",
    }
    logger.info(f"SerpAPI query: {query}")
    return await fetch_json(SERPAPI_BASE, params=params)


def cache_key(query: str) -> str:
    return hashlib.sha256(query.encode()).hexdigest()[:32]
