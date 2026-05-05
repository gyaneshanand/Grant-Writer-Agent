"""
LLM SEO metadata generator for Layer 5.
"""
import json
from typing import Optional

from agents.grant_writer_v2.core.llm import chat
from agents.grant_writer_v2.core.logger import get_logger
from agents.grant_writer_v2.layer5_metadata_seo.prompts import SEO_SYSTEM, SEO_USER, PROMPT_VERSION

logger = get_logger("layer5.seo_generator")


async def generate_seo(
    program_name: str,
    org_name: str,
    focus_areas: list[str],
    grant_amount: str,
    deadline: str,
    eligibility_summary: str,
    ein: str,
    run_id: str,
    consolidated_description: str = "",
    budget_usd: float = 0.05,
) -> dict[str, str]:
    """
    Returns dict with 6 SEO fields including opportunity_teaser (~500 words).
    Primary input is the consolidated_description from L4; structured fields supplement it.
    Falls back to minimal values on failure.
    """
    user_msg = SEO_USER.format(
        focus_areas=", ".join(focus_areas[:5]) or "General",
        grant_amount=grant_amount or "Not specified",
        deadline=deadline or "Not specified",
        eligibility_summary=eligibility_summary[:400] if eligibility_summary else "Not specified",
        consolidated_description=consolidated_description[:6000] if consolidated_description else "Not specified",
    )
    try:
        resp = await chat(
            "layer5_seo",
            messages=[
                {"role": "system", "content": SEO_SYSTEM},
                {"role": "user", "content": user_msg},
            ],
            ein=ein,
            layer="layer5",
            run_id=run_id,
            budget_usd=budget_usd,
            max_tokens=1200,  # ~500-word teaser + 5 short fields
            temperature=0.2,
            response_format={"type": "json_object"},
        )
        return json.loads(resp.choices[0].message.content or "{}")
    except Exception as e:
        logger.warning(f"[L5] seo_generator failed for {program_name}: {e}")
        return {
            "opportunity_title": program_name[:70],
            "h1_tag": program_name[:60],
            "meta_title": program_name[:60],
            "meta_description": f"Grant opportunity for {', '.join(focus_areas[:2]) or 'nonprofits'}.",
            "opportunity_teaser": "",
            "opportunity_title_for_subscriber": f"Grant Opportunity: {program_name[:130]}",
        }
