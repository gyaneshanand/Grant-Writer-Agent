"""
Per-program LLM extractor for Layer 4.
Takes one VALID GrantProgramVerdict + corpus → GrantProgramRecord.
"""
import json
from datetime import datetime
from typing import Optional

from agents.grant_writer_v2.core.llm import chat
from agents.grant_writer_v2.core.logger import get_logger
from agents.grant_writer_v2.layer4_grant_writer.prompts import (
    PER_PROGRAM_SYSTEM, PER_PROGRAM_USER, PROMPT_VERSION,
)
from agents.grant_writer_v2.schemas.common import ContactInfo, DeadlineSlot
from agents.grant_writer_v2.schemas.grant_program import GrantProgramRecord, GrantProgramVerdict

logger = get_logger("layer4.per_program")

MAX_PAGE_CONTENT_CHARS = 15_000


def _strip_html(html: str) -> str:
    import re
    s = re.sub(r'<(script|style)[^>]*>.*?</(script|style)>', ' ', html, flags=re.DOTALL | re.IGNORECASE)
    s = re.sub(r'<[^>]+>', ' ', s)
    return re.sub(r'\s+', ' ', s).strip()


def _find_page(evidence_url: str, corpus: list[dict]) -> str:
    """Return stripped readable text for the evidence URL, falling back to first 2 corpus pages."""
    for page in corpus:
        if page.get("url", "") == evidence_url:
            return _strip_html(page.get("text", ""))[:MAX_PAGE_CONTENT_CHARS]
    # Fallback: concatenate first 2 pages stripped
    parts = []
    for page in corpus[:3]:
        url = page.get("url", "")
        text = _strip_html(page.get("text", ""))[:5000]
        parts.append(f"--- {url} ---\n{text}")
    return "\n\n".join(parts)


async def extract_program(
    verdict: GrantProgramVerdict,
    corpus: list[dict],
    org_name: str,
    ein: str,
    run_id: str,
    budget_usd: float,
) -> Optional[GrantProgramRecord]:
    evidence_url = verdict.program_url or (verdict.source_pages[0] if verdict.source_pages else "")
    page_content = _find_page(evidence_url, corpus)

    user_msg = PER_PROGRAM_USER.format(
        org_name=org_name,
        program_name=verdict.program_name,
        evidence_url=evidence_url,
        page_content=page_content,
    )

    try:
        resp = await chat(
            "layer4_per_program",
            messages=[
                {"role": "system", "content": PER_PROGRAM_SYSTEM},
                {"role": "user", "content": user_msg},
            ],
            ein=ein,
            layer="layer4",
            run_id=run_id,
            budget_usd=budget_usd,
            max_tokens=3000,
            temperature=0.0,
            response_format={"type": "json_object"},
        )
        raw = json.loads(resp.choices[0].message.content or "{}")
    except Exception as e:
        logger.warning(f"[L4] per_program extraction failed for {verdict.program_name}: {e}")
        return None

    contact = ContactInfo(
        email=raw.get("contact_email") or "",
        phone=raw.get("contact_phone") or "",
        contact_person=raw.get("contact_name"),
    )

    deadlines_raw = raw.get("deadlines") or []
    deadlines = []
    for d in deadlines_raw:
        if isinstance(d, dict):
            deadlines.append(DeadlineSlot(
                cycle_label=d.get("cycle_label", ""),
                deadline_iso=d.get("deadline_iso"),
                deadline_type=d.get("deadline_type", "full_proposal"),
                is_recurring=d.get("is_recurring", False),
                raw_text=d.get("raw_text", ""),
            ))

    record = GrantProgramRecord(
        program_id=verdict.program_id,
        ein=ein,
        program_name=verdict.program_name,
        program_url=evidence_url or None,
        verdict=verdict.verdict,
        verdict_confidence=verdict.verdict_confidence,
        rules=verdict.rules,

        funding_priorities=raw.get("funding_priorities") or "",
        types_of_grant=raw.get("types_of_grant") or "",
        grant_amount_freeform=raw.get("grant_amount_freeform") or "",
        grant_amount_min_usd=raw.get("grant_amount_min_usd"),
        grant_amount_max_usd=raw.get("grant_amount_max_usd"),
        grant_amount_typical_usd=raw.get("grant_amount_typical_usd"),

        eligibility_criteria=raw.get("eligibility_criteria") or "",
        eligible_applicants_freeform=raw.get("eligible_applicants_freeform") or "",
        eligible_applicant_types=raw.get("eligible_applicant_types") or [],
        eligible_locations_freeform=raw.get("eligible_locations_freeform") or "",
        eligible_geographies=raw.get("eligible_geographies") or [],
        eligible_focus_areas=raw.get("eligible_focus_areas") or [],
        excluded_uses=raw.get("excluded_uses") or [],

        proposal_deadline_freeform=raw.get("proposal_deadline_freeform") or "",
        deadlines=deadlines,
        deadline_type=raw.get("deadline_type") or "not_specified",
        next_deadline_iso=raw.get("next_deadline_iso"),
        is_currently_open=raw.get("is_currently_open"),
        loi_required=raw.get("loi_required"),

        application_method=raw.get("application_method") or [],
        application_portal_url=raw.get("application_portal_url"),
        application_email=raw.get("application_email"),
        application_steps=raw.get("application_steps") or [],
        required_documents=raw.get("required_documents") or [],
        review_timeline_weeks=raw.get("review_timeline_weeks"),

        is_invitation_only=raw.get("is_invitation_only") or False,
        accepts_unsolicited=raw.get("accepts_unsolicited") if raw.get("accepts_unsolicited") is not None else True,
        is_recurring=raw.get("is_recurring") or False,
        is_currently_active=raw.get("is_currently_active") if raw.get("is_currently_active") is not None else True,
        recurrence=raw.get("recurrence") or "Not specified",

        contact_info=contact,

        source_pages=raw.get("source_pages") or (verdict.source_pages or []),
        evidence_quotes=raw.get("evidence_quotes") or {},
        extraction_method="llm",
        extraction_model=resp.model or "unknown",
        extraction_timestamp=datetime.utcnow(),
    )
    record.completeness_score = record.compute_completeness()
    return record
