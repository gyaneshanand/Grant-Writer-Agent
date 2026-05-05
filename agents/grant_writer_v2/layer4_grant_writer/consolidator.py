"""
Foundation-level consolidator for Layer 4.
Writes an 11-section Markdown description from all programs + org profile.
"""
from agents.grant_writer_v2.core.llm import chat
from agents.grant_writer_v2.core.logger import get_logger
from agents.grant_writer_v2.layer4_grant_writer.prompts import (
    CONSOLIDATOR_SYSTEM, CONSOLIDATOR_USER, PROMPT_VERSION,
)
from agents.grant_writer_v2.schemas.grant_program import GrantProgramRecord

logger = get_logger("layer4.consolidator")


def _programs_summary(programs: list[GrantProgramRecord]) -> str:
    lines = []
    for p in programs:
        lines.append(
            f"- {p.program_name}: {p.grant_amount_freeform or 'amount unknown'}. "
            f"Focus: {', '.join(p.eligible_focus_areas[:3]) or 'not specified'}. "
            f"Deadline: {p.proposal_deadline_freeform or 'not specified'}."
        )
    return "\n".join(lines)


async def consolidate(
    programs: list[GrantProgramRecord],
    org_name: str,
    state: str,
    mission: str,
    ein: str,
    run_id: str,
    budget_usd: float = 0.10,
) -> str:
    """Returns the 11-section Markdown description, or a minimal fallback."""
    programs_summary = _programs_summary(programs)
    user_msg = CONSOLIDATOR_USER.format(
        org_name=org_name,
        state=state,
        mission=mission or "Not specified",
        program_count=len(programs),
        programs_summary=programs_summary or "No programs identified.",
    )
    try:
        resp = await chat(
            "layer4_consolidator",
            messages=[
                {"role": "system", "content": CONSOLIDATOR_SYSTEM},
                {"role": "user", "content": user_msg},
            ],
            ein=ein,
            layer="layer4",
            run_id=run_id,
            budget_usd=budget_usd,
            max_tokens=2000,
            temperature=0.1,
        )
        return resp.choices[0].message.content or ""
    except Exception as e:
        logger.warning(f"[L4] consolidator failed for {ein}: {e}")
        return f"## Overview\n{org_name} — grant program details available in individual program records."
