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
You are an expert grant writer creating a professional grant opportunity description
for The Grant Portal — an online grant directory.

You will be given data from one or more grant programs from a foundation. Your task
is to write ONE SINGLE consolidated ~500-word description that synthesizes all active
grant information into a comprehensive funding opportunity profile.

📝 FORMATTING REQUIREMENTS:
- Use ### (h3) for all section headers, with an emoji icon before the title
- Use bullet points for lists
- NO horizontal lines between sections
- NO source URLs in the description body (URLs appear only in Grant Programs section)
- Clean readable formatting with proper spacing between sections

📋 REQUIRED SECTIONS (use these exact headers in this order):
### 🏢 Organization Name
### 📖 Background Information
### 🎯 Mission / Purpose
### 🌍 Geographic Focus
### 🗂 Funding Areas & Interests
### ✅ Eligibility Criteria
### 💰 Funding Amounts
### 📅 Proposal Deadlines / Grant Cycles
### 🔁 Grant Frequency
### 💡 Grant Programs & Awards
### 📞 Contact Information

RULES:
- Do NOT invent any information. Only use the data provided.
- If a field is missing, write "Visit the foundation website for details."
- Exactly ~500 words total (be precise).
- Professional, engaging tone that encourages applications.
- In "💡 Grant Programs & Awards": list each program as a bullet with a short description.
  If a program URL is available, include it as: url: <program_url> (plain text, no hyperlink).
- In "📞 Contact Information": include phone, email, and physical address if available.
- Merge similar information across programs rather than repeating it.
"""

CONSOLIDATOR_USER = """\
Foundation: {org_name}
State: {state}
Mission: {mission}
About: {about}
Geography served: {geography_served}
Focus areas: {focus_areas}
Foundation type: {foundation_type}
Contact: {contact}

Programs ({program_count} total):
{programs_summary}

Write the single consolidated grant opportunity description now.
"""
