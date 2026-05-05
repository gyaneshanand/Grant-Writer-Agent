"""
LLM-based org profile extractor for Layer 3.
Reads the L2 corpus from disk cache, enriches with /about and /mission pages if needed.
"""
import json
from typing import Optional

from agents.grant_writer_v2.core.http import fetch
from agents.grant_writer_v2.core.llm import chat
from agents.grant_writer_v2.core.logger import get_logger
from agents.grant_writer_v2.layer3_org_extraction.prompts import (
    EXTRACTOR_SYSTEM, EXTRACTOR_USER, PROMPT_VERSION,
)
from agents.grant_writer_v2.schemas.common import ContactInfo, FoundationInput
from agents.grant_writer_v2.schemas.org_profile import OrgProfile

logger = get_logger("layer3.extractor")

MAX_CONTENT_CHARS = 40_000
# Extra paths to try if corpus is thin
# Paths to try for org profile enrichment, in priority order.
# Homepage is always tried first; about/mission paths follow.
ENRICHMENT_PATHS = [
    "",             # homepage (base_url itself)
    "/about",
    "/about-us",
    "/mission",
    "/who-we-are",
    "/overview",
    "/our-story",
    "/history",
]


def _strip_html(html: str) -> str:
    import re
    s = re.sub(r'<(script|style)[^>]*>.*?</(script|style)>', ' ', html, flags=re.DOTALL | re.IGNORECASE)
    s = re.sub(r'<[^>]+>', ' ', s)
    return re.sub(r'\s+', ' ', s).strip()


def _build_content(corpus: list[dict], base_url: str) -> tuple[str, list[str]]:
    """Build stripped text content from corpus entries. Returns (content, source_pages)."""
    parts = []
    source_pages = []
    total = 0
    for page in corpus:
        url = page.get("url", "")
        raw = page.get("text", "")
        text = _strip_html(raw)[:8000]
        chunk = f"--- {url} ---\n{text}\n"
        if total + len(chunk) > MAX_CONTENT_CHARS:
            break
        parts.append(chunk)
        source_pages.append(url)
        total += len(chunk)
    return "\n".join(parts), source_pages


async def _enrich_corpus(base_url: str, visited_urls: set[str]) -> list[dict]:
    """
    Fetch homepage + common about/mission paths not already in the L2 corpus.
    Returns up to 3 additional pages so L3 has enough org profile content even
    for single-page sites where L2 only crawled grant-specific pages.
    """
    extra = []
    base = base_url.rstrip("/")
    for path in ENRICHMENT_PATHS:
        if len(extra) >= 3:
            break
        url = base + path if path else base + "/"
        if url in visited_urls:
            continue
        result = await fetch(url)
        if not result.get("error") and result.get("text"):
            logger.info(f"[L3] enriched corpus with {url} ({len(result['text'])} chars)")
            extra.append({"url": url, "text": result["text"], "source": "layer3_enrich"})
            visited_urls.add(url)
    return extra


async def extract(
    corpus: list[dict],
    foundation: FoundationInput,
    base_url: str,
    run_id: str,
    budget_usd: float = 0.20,
) -> Optional[OrgProfile]:
    """Extract OrgProfile from corpus. Returns None on hard failure."""
    visited = {p.get("url", "") for p in corpus}

    # Always enrich — homepage + about pages may not have been crawled by L2
    # (L2 focuses on grant pages; L3 needs org identity/mission content).
    extra = await _enrich_corpus(base_url, visited)
    corpus = corpus + extra

    content, source_pages = _build_content(corpus, base_url)
    if not content.strip():
        return None

    user_msg = EXTRACTOR_USER.format(
        org_name=foundation.org_name,
        ein=foundation.ein,
        page_count=len(source_pages),
        content=content,
    )

    try:
        resp = await chat(
            "layer3_extractor",
            messages=[
                {"role": "system", "content": EXTRACTOR_SYSTEM},
                {"role": "user", "content": user_msg},
            ],
            ein=foundation.ein,
            layer="layer3",
            run_id=run_id,
            budget_usd=budget_usd,
            max_tokens=2000,
            temperature=0.0,
            response_format={"type": "json_object"},
        )
        raw = json.loads(resp.choices[0].message.content or "{}")
    except Exception as e:
        logger.warning(f"[L3] extractor LLM failed for {foundation.ein}: {e}")
        return None

    contact = ContactInfo(
        email=raw.get("email") or "",
        phone=raw.get("phone") or "",
        address=raw.get("address") or "",
        contact_person=raw.get("contact_name"),
        contact_title=raw.get("contact_title"),
        address_city=raw.get("city"),
        address_state=raw.get("state"),
        address_zip=raw.get("zip"),
    )

    dba = raw.get("dba_name")
    geo = raw.get("geography_served")

    return OrgProfile(
        ein=foundation.ein,
        org_name=foundation.org_name,
        legal_name=raw.get("legal_name") or foundation.org_name,
        dba_names=[dba] if dba else [],
        mission=raw.get("mission_statement") or "",
        about=raw.get("about_text") or "",
        founded_year=raw.get("year_established"),
        foundation_type=raw.get("foundation_type") or "unknown",
        focus_areas=raw.get("focus_areas") or [],
        geography_served_detail=geo or "",
        annual_giving_usd=raw.get("annual_giving_usd"),
        total_assets_usd=raw.get("total_assets_usd"),
        contact=contact,
        source_pages=source_pages,
        extraction_model=resp.model or "unknown",
        extraction_prompt_version=PROMPT_VERSION,
    )
