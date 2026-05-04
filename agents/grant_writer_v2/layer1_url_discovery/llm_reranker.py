"""
LLM reranker for Layer 1. Only invoked when deterministic verifier confidence
falls in the gray band (0.35–0.65).
"""
import json
from typing import Optional

from agents.grant_writer_v2.core.llm import chat
from agents.grant_writer_v2.core.logger import get_logger
from agents.grant_writer_v2.layer1_url_discovery.prompts import (
    RERANKER_SYSTEM_V1, RERANKER_USER_V1, PROMPT_VERSION,
)
from agents.grant_writer_v2.schemas.common import CandidateRecord, FoundationInput

logger = get_logger("layer1.reranker")

GRAY_BAND_LOW = 0.35
GRAY_BAND_HIGH = 0.65


def needs_rerank(best_confidence: float) -> bool:
    return GRAY_BAND_LOW <= best_confidence <= GRAY_BAND_HIGH


async def rerank(
    candidates: list[CandidateRecord],
    foundation: FoundationInput,
    *,
    ein: str = "",
) -> tuple[Optional[int], str, str]:
    """
    Ask LLM to pick the best candidate index.
    Returns (selected_index or None, reasoning, model_used).
    selected_index is into the `candidates` list.
    """
    candidate_lines = "\n".join(
        f"  [{i}] {c.url}  |  {c.title[:80]}" for i, c in enumerate(candidates)
    )
    city_line = f"City: {foundation.city}" if foundation.city else ""
    user_msg = RERANKER_USER_V1.format(
        org_name=foundation.org_name,
        state=foundation.state,
        city_line=city_line,
        candidates=candidate_lines,
    )
    try:
        resp = await chat(
            "layer1_reranker",
            messages=[
                {"role": "system", "content": RERANKER_SYSTEM_V1},
                {"role": "user", "content": user_msg},
            ],
            ein=ein,
            layer="layer1",
            max_tokens=200,
            temperature=0.0,
            response_format={"type": "json_object"},
        )
        raw = resp.choices[0].message.content or "{}"
        data = json.loads(raw)
        idx = data.get("index", -1)
        reasoning = data.get("reasoning", "")
        model = resp.model or "unknown"
        if idx == -1 or idx >= len(candidates):
            return None, reasoning, model
        return idx, reasoning, model
    except Exception as e:
        logger.warning(f"LLM reranker failed for {ein}: {e}")
        return None, str(e), "error"
