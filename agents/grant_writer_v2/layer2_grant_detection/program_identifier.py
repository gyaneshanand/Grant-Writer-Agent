"""
Node: given the crawled corpus, identify distinct grant programs via LLM.
"""
import json
import re

from agents.grant_writer_v2.core.llm import chat
from agents.grant_writer_v2.core.logger import get_logger
from agents.grant_writer_v2.layer2_grant_detection.prompts import (
    PROGRAM_IDENTIFIER_SYSTEM,
    PROGRAM_IDENTIFIER_USER,
    PROMPT_VERSION,
)

logger = get_logger("layer2.program_identifier")

MAX_CORPUS_CHARS = 40_000


def _strip_html(html: str) -> str:
    html = re.sub(r'<(script|style)[^>]*>.*?</(script|style)>', ' ', html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r'<[^>]+>', ' ', html)
    return re.sub(r'\s+', ' ', html).strip()


def _build_corpus_text(corpus: list[dict]) -> str:
    parts = []
    total = 0
    for page in corpus:
        url = page.get("url", "")
        raw = page.get("text", "")
        content_type = page.get("content_type", "")
        text = raw if "pdf" in content_type else _strip_html(raw)
        chunk = f"--- {url} ---\n{text[:8000]}\n"
        if total + len(chunk) > MAX_CORPUS_CHARS:
            break
        parts.append(chunk)
        total += len(chunk)
    logger.info(f"[L2] program_identifier corpus: {len(corpus)} pages, {total} chars")
    return "\n".join(parts)


async def identify_programs(
    corpus: list[dict],
    org_name: str,
    ein: str,
    run_id: str,
    budget_usd: float,
) -> list[dict]:
    """
    Returns list of dicts: [{program_name, evidence_url, evidence_quote}, ...]
    Returns [] on LLM failure.
    """
    logger.info(f"[L2] identify_programs called: {len(corpus)} pages in corpus")
    for i, page in enumerate(corpus):
        url = page.get("url", "")
        text_len = len(page.get("text", ""))
        logger.info(f"[L2]   corpus[{i}]: {url} ({text_len} chars)")

    corpus_text = _build_corpus_text(corpus)
    logger.info(f"[L2] corpus_text length: {len(corpus_text)} chars, empty={not corpus_text.strip()}")
    if not corpus_text.strip():
        logger.warning(f"[L2] corpus_text is empty — returning []")
        return []

    user_msg = PROGRAM_IDENTIFIER_USER.format(
        org_name=org_name,
        ein=ein,
        corpus_text=corpus_text,
    )
    logger.info(f"[L2] calling LLM for program identification (budget_usd={budget_usd:.4f})")
    try:
        resp = await chat(
            "layer2_program_identifier",
            messages=[
                {"role": "system", "content": PROGRAM_IDENTIFIER_SYSTEM},
                {"role": "user", "content": user_msg},
            ],
            ein=ein,
            layer="layer2",
            run_id=run_id,
            budget_usd=budget_usd,
            max_tokens=2000,
            temperature=0.0,
            response_format={"type": "json_object"},
        )
        raw = resp.choices[0].message.content or "[]"
        logger.info(f"[L2] program_identifier LLM raw response: {raw[:500]}")
        # Response may be {"programs": [...]} or just [...]
        data = json.loads(raw)
        if isinstance(data, list):
            logger.info(f"[L2] identified {len(data)} programs (list response)")
            return data
        if isinstance(data, dict):
            # LLM returned a wrapper object with a list
            for key in ("programs", "grant_programs", "results"):
                if isinstance(data.get(key), list):
                    logger.info(f"[L2] identified {len(data[key])} programs (dict['{key}'] response)")
                    return data[key]
            # LLM returned a single program object directly
            if "program_name" in data:
                logger.info("[L2] identified 1 program (single-object response)")
                return [data]
        logger.warning(f"[L2] unexpected JSON shape: {type(data)}, keys={list(data.keys()) if isinstance(data, dict) else 'N/A'}")
        return []
    except Exception as e:
        logger.warning(f"[L2] program_identifier failed for {ein}: {e}", exc_info=True)
        return []
