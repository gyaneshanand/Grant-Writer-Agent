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
# Combined cap when concatenating multiple pages — bigger than single-page so the
# extractor can see evidence_url + apply/eligibility/deadlines pages together.
MAX_MULTIPAGE_CONTENT_CHARS = 30_000

# Path keywords that indicate the page likely contains program-specific extractable detail.
# Mirrors the rule evaluator's filter so L4 sees the same corpus depth as L2's rule eval.
_PROGRAM_PAGE_KEYWORDS = (
    "apply", "how-to-apply", "application", "applications",
    "grant", "grants", "funding", "fund",
    "eligib", "guidelines", "process",
    "program", "programs", "rfp", "loi",
    "deadline", "deadlines", "timeline",
    "scholarship", "scholarships",
    "criteria", "requirements",
)


def _strip_html(html: str) -> str:
    import re
    s = re.sub(r'<(script|style)[^>]*>.*?</(script|style)>', ' ', html, flags=re.DOTALL | re.IGNORECASE)
    s = re.sub(r'<[^>]+>', ' ', s)
    return re.sub(r'\s+', ' ', s).strip()


def _build_page_content(evidence_url: str, corpus: list[dict]) -> str:
    """
    Build page content for the LLM by concatenating:
      1. The evidence_url page (most relevant — where the program was identified)
      2. Every other crawled page whose URL path matches a program-detail keyword
         (apply / eligibility / deadlines / guidelines / etc.)
      3. Fallback: if no matches, use the first 3 corpus pages

    L2 already crawled these pages — this just makes sure L4 sees them all instead
    of only the evidence_url. Avoids re-fetching while giving the per-program
    extractor enough context to populate fields like deadlines, application_steps,
    eligibility_criteria, etc.
    """
    if not corpus:
        return ""

    from urllib.parse import urlparse

    seen_urls: set[str] = set()
    sections: list[str] = []
    remaining = MAX_MULTIPAGE_CONTENT_CHARS

    def _add(page: dict, budget: int) -> int:
        url = page.get("url", "")
        if not url or url in seen_urls or budget <= 0:
            return budget
        text = _strip_html(page.get("text", ""))
        if not text:
            return budget
        chunk = text[:budget]
        sections.append(f"--- PAGE: {url} ---\n{chunk}")
        seen_urls.add(url)
        return budget - len(chunk)

    # 1. evidence_url first (most relevant)
    if evidence_url:
        for p in corpus:
            if p.get("url") == evidence_url:
                remaining = _add(p, remaining)
                break

    # 2. other pages whose path looks program-relevant
    for p in corpus:
        url = p.get("url", "")
        if url in seen_urls or not url:
            continue
        path_lower = urlparse(url).path.lower()
        if any(kw in path_lower for kw in _PROGRAM_PAGE_KEYWORDS):
            remaining = _add(p, remaining)
            if remaining <= 0:
                break

    # 3. fallback — first 3 corpus pages if nothing matched
    if not sections:
        for p in corpus[:3]:
            remaining = _add(p, remaining)
            if remaining <= 0:
                break

    return "\n\n".join(sections)


# Keep the old name as a thin wrapper for any external callers.
def _find_page(evidence_url: str, corpus: list[dict]) -> str:
    return _build_page_content(evidence_url, corpus)


async def extract_program(
    verdict: GrantProgramVerdict,
    corpus: list[dict],
    org_name: str,
    ein: str,
    run_id: str,
    budget_usd: float,
) -> Optional[GrantProgramRecord]:
    evidence_url = verdict.program_url or (verdict.source_pages[0] if verdict.source_pages else "")
    page_content = _build_page_content(evidence_url, corpus)

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
