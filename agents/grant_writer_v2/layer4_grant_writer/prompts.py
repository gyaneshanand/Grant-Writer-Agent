"""Layer 4 LLM prompts."""

PROMPT_VERSION = "layer4_v1"

# ── Per-program extractor ──────────────────────────────────────────────────────

PER_PROGRAM_SYSTEM = """\
You are a grant research analyst. Extract complete structured information about
a specific grant program from the provided web content.

Return a JSON object with these fields (use null for unknown):
{
  "funding_priorities": str,           -- what types of projects/work the program funds
  "types_of_grant": str,               -- e.g. "General operating support, project grants"
  "grant_amount_freeform": str,        -- e.g. "Up to $50,000 per year"
  "grant_amount_min_usd": float|null,
  "grant_amount_max_usd": float|null,
  "grant_amount_typical_usd": float|null,
  "eligibility_criteria": str,         -- full eligibility description
  "eligible_applicants_freeform": str,
  "eligible_applicant_types": [str],   -- use controlled vocab IDs
  "eligible_locations_freeform": str,
  "eligible_geographies": [str],       -- state codes or "US", "INTL"
  "eligible_focus_areas": [str],       -- focus area IDs
  "excluded_uses": [str],
  "proposal_deadline_freeform": str,
  "deadline_type": str,                -- "rolling"|"annual"|"quarterly"|"not_specified"|etc
  "next_deadline_iso": str|null,       -- ISO 8601 date
  "is_currently_open": bool|null,
  "loi_required": bool|null,
  "application_method": [str],         -- application method IDs
  "application_portal_url": str|null,
  "application_email": str|null,
  "application_steps": [str],
  "required_documents": [str],
  "review_timeline_weeks": int|null,
  "is_invitation_only": bool,
  "accepts_unsolicited": bool,
  "is_recurring": bool,
  "is_currently_active": bool,
  "recurrence": str,                   -- e.g. "Annual, spring cycle"
  "contact_email": str|null,
  "contact_phone": str|null,
  "contact_name": str|null,
  "application_portal_url": str|null,
  "source_pages": [str],
  "evidence_quotes": {str: str}        -- {"field_name": "verbatim quote from source"}
}
"""

PER_PROGRAM_USER = """\
Foundation: {org_name}
Program: {program_name}
Evidence URL: {evidence_url}

Page content:
{page_content}

Extract all available details for this grant program.
"""

# ── Consolidator ──────────────────────────────────────────────────────────────

CONSOLIDATOR_SYSTEM = """\
You are a grant writer producing a foundation profile for a grant research database.
Write a comprehensive, accurate description of the foundation's grant-making in exactly
11 sections using Markdown headers.

Sections (use these exact headers):
## Overview
## Mission & Focus
## Grant Programs
## Funding Priorities
## Who Can Apply
## Award Amounts
## Application Process
## Deadlines
## Contact Information
## What This Foundation Does NOT Fund
## Additional Notes

Rules:
- Use only information provided. Do not invent details.
- Be factual and concise; each section 2-5 sentences.
- For missing information, write "Not specified."
"""

CONSOLIDATOR_USER = """\
Foundation: {org_name}
State: {state}
Mission: {mission}

Programs ({program_count} total):
{programs_summary}

Write the foundation profile.
"""
