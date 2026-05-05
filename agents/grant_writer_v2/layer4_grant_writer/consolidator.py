"""
Foundation-level consolidator for Layer 4.
Writes a ~500-word, 11-section Markdown description matching The Grant Portal format.
"""
import json
from typing import Optional

from agents.grant_writer_v2.core.llm import chat
from agents.grant_writer_v2.core.logger import get_logger
from agents.grant_writer_v2.layer4_grant_writer.prompts import (
    CONSOLIDATOR_SYSTEM, CONSOLIDATOR_USER, PROMPT_VERSION,
)
from agents.grant_writer_v2.schemas.grant_program import GrantProgramRecord

logger = get_logger("layer4.consolidator")


def _programs_summary(programs: list[GrantProgramRecord]) -> str:
    """Build a rich summary of each program for the consolidator prompt."""
    lines = []
    for p in programs:
        parts = [f"Program: {p.program_name}"]
        if p.funding_priorities:
            parts.append(f"  Funding priorities: {p.funding_priorities}")
        if p.types_of_grant:
            parts.append(f"  Types of grant: {p.types_of_grant}")
        if p.grant_amount_freeform:
            parts.append(f"  Amount: {p.grant_amount_freeform}")
        elif p.grant_amount_min_usd or p.grant_amount_max_usd:
            lo = f"${p.grant_amount_min_usd:,.0f}" if p.grant_amount_min_usd else "?"
            hi = f"${p.grant_amount_max_usd:,.0f}" if p.grant_amount_max_usd else "?"
            parts.append(f"  Amount: {lo} – {hi}")
        if p.eligibility_criteria:
            parts.append(f"  Eligibility: {p.eligibility_criteria}")
        if p.eligible_applicants_freeform:
            parts.append(f"  Eligible applicants: {p.eligible_applicants_freeform}")
        if p.eligible_locations_freeform:
            parts.append(f"  Locations: {p.eligible_locations_freeform}")
        elif p.eligible_geographies:
            parts.append(f"  Geographies: {', '.join(p.eligible_geographies)}")
        if p.proposal_deadline_freeform:
            parts.append(f"  Deadline: {p.proposal_deadline_freeform}")
        if p.deadline_type and p.deadline_type != "not_specified":
            parts.append(f"  Deadline type: {p.deadline_type}")
        if p.is_currently_open is not None:
            parts.append(f"  Currently open: {p.is_currently_open}")
        if p.loi_required is not None:
            parts.append(f"  LOI required: {p.loi_required}")
        if p.application_steps:
            parts.append(f"  Application steps: {'; '.join(p.application_steps[:3])}")
        if p.application_portal_url:
            parts.append(f"  Application URL: {p.application_portal_url}")
        if p.is_recurring is not None:
            parts.append(f"  Recurring: {p.is_recurring}")
        if p.recurrence:
            parts.append(f"  Recurrence: {p.recurrence}")
        if p.contact_info and (p.contact_info.email or p.contact_info.phone):
            parts.append(f"  Contact email: {p.contact_info.email or 'not specified'}")
            parts.append(f"  Contact phone: {p.contact_info.phone or 'not specified'}")
        if p.source_pages:
            parts.append(f"  Source URL: {p.source_pages[0]}")
        lines.append("\n".join(parts))
    return "\n\n".join(lines)


async def consolidate(
    programs: list[GrantProgramRecord],
    org_name: str,
    state: str,
    mission: str,
    ein: str,
    run_id: str,
    budget_usd: float = 0.10,
    about: str = "",
    geography_served: str = "",
    focus_areas: Optional[list] = None,
    foundation_type: str = "",
    contact: Optional[dict] = None,
) -> str:
    """Returns the ~500-word 11-section Markdown description, or a minimal fallback."""
    programs_summary = _programs_summary(programs)

    contact_str = "Not specified"
    if contact:
        parts = []
        if contact.get("contact_person"):
            parts.append(f"{contact['contact_person']}" + (f", {contact['contact_title']}" if contact.get("contact_title") else ""))
        if contact.get("email"):
            parts.append(f"Email: {contact['email']}")
        if contact.get("phone"):
            parts.append(f"Phone: {contact['phone']}")
        if contact.get("address"):
            addr = contact["address"]
            city = contact.get("address_city", "")
            state_c = contact.get("address_state", "")
            zip_c = contact.get("address_zip", "")
            full_addr = " ".join(filter(None, [addr, city, state_c, zip_c]))
            if full_addr.strip():
                parts.append(f"Address: {full_addr}")
        contact_str = "\n".join(parts) if parts else "Not specified"

    user_msg = CONSOLIDATOR_USER.format(
        org_name=org_name,
        state=state,
        mission=mission or "Not specified",
        about=about or "Not specified",
        geography_served=geography_served or "Not specified",
        focus_areas=", ".join(focus_areas) if focus_areas else "Not specified",
        foundation_type=foundation_type or "Not specified",
        contact=contact_str,
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
            max_tokens=2500,
            temperature=0.1,
        )
        return resp.choices[0].message.content or ""
    except Exception as e:
        logger.warning(f"[L4] consolidator failed for {ein}: {e}")
        return f"### 🏢 Organization Name\n{org_name}\n\n### 📖 Background Information\nGrant program details available in individual program records."
