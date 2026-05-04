from __future__ import annotations
from datetime import datetime
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field, field_validator

from agents.grant_writer_v2.schemas.common import RuleEvaluation, DeadlineSlot, ContactInfo
from agents.grant_writer_v2.core.vocab import (
    validate_focus_areas, validate_applicant_types,
    validate_application_methods, validate_deadline_type,
)

OverrideReason = Literal[
    "geography_excluded", "past_only", "explicit_no_unsolicited", "donation_only"
]

VerdictType = Literal["VALID", "NEEDS_REVIEW", "INVALID", "ERROR"]


class SixRuleResult(BaseModel):
    has_grants: RuleEvaluation
    accepts_applications: RuleEvaluation
    not_invitation_only: RuleEvaluation
    not_donation_only: RuleEvaluation
    allows_unsolicited: RuleEvaluation
    geography_valid: RuleEvaluation
    active_or_recurring: RuleEvaluation

    def all_pass(self, confidence_threshold: float = 0.7) -> bool:
        rules = [
            self.has_grants, self.accepts_applications, self.not_invitation_only,
            self.not_donation_only, self.allows_unsolicited, self.geography_valid,
            self.active_or_recurring,
        ]
        return all(r.value and r.confidence >= confidence_threshold for r in rules)

    def any_fail_hard(self, confidence_threshold: float = 0.8) -> bool:
        """True if any rule is definitively False with high confidence."""
        rules = [
            self.has_grants, self.accepts_applications, self.not_invitation_only,
            self.not_donation_only, self.allows_unsolicited, self.geography_valid,
            self.active_or_recurring,
        ]
        return any(not r.value and r.confidence >= confidence_threshold for r in rules)


class GrantProgramVerdict(BaseModel):
    """Per-program verdict from Layer 2 grant detection."""
    program_id: str
    ein: str
    program_name: str
    program_url: Optional[str] = None
    verdict: VerdictType
    verdict_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    verdict_reasoning: str = ""
    rules: SixRuleResult
    override_applied: Optional[OverrideReason] = None
    source_pages: List[str] = []
    extracted_at: datetime = Field(default_factory=datetime.utcnow)


class GrantProgramRecord(BaseModel):
    """
    PRIMARY UNIT — full structured record for one grant program.
    Populated across layers 2 (verdict + rules), 4 (all structured fields), 5 (SEO/filters).
    """
    # Identity
    program_id: str
    ein: str
    program_name: str
    program_slug: Optional[str] = None
    program_url: Optional[str] = None

    # Verdict (from L2)
    verdict: VerdictType = "NEEDS_REVIEW"
    verdict_confidence: float = 0.0
    rules: Optional[SixRuleResult] = None
    override_applied: Optional[OverrideReason] = None

    # Funding (L4)
    funding_priorities: str = ""
    types_of_grant: str = ""
    grant_amount_freeform: str = ""
    grant_amount_min_usd: Optional[float] = None
    grant_amount_max_usd: Optional[float] = None
    grant_amount_typical_usd: Optional[float] = None
    grant_amount_currency: str = "USD"
    funding_match_required: Optional[bool] = None
    funding_match_percent: Optional[float] = None

    # Eligibility (L4)
    eligibility_criteria: str = ""
    eligible_applicants_freeform: str = ""
    eligible_applicant_types: List[str] = []
    eligible_locations_freeform: str = ""
    eligible_geographies: List[str] = []
    excluded_geographies: List[str] = []
    eligible_focus_areas: List[str] = []
    excluded_uses: List[str] = []
    minimum_org_age_years: Optional[int] = None
    minimum_budget_usd: Optional[float] = None
    maximum_budget_usd: Optional[float] = None
    requires_501c3: Optional[bool] = None

    # Deadlines (L4)
    proposal_deadline_freeform: str = ""
    deadlines: List[DeadlineSlot] = []
    deadline_type: str = "not_specified"
    next_deadline_iso: Optional[str] = None
    is_currently_open: Optional[bool] = None
    application_window_days: Optional[int] = None
    loi_required: Optional[bool] = None
    loi_deadline_iso: Optional[str] = None

    # Application process (L4)
    application_method: List[str] = []
    application_portal_url: Optional[str] = None
    application_email: Optional[str] = None
    application_steps: List[str] = []
    required_documents: List[str] = []
    review_timeline_weeks: Optional[int] = None

    # Type flags (L4)
    is_invitation_only: bool = False
    accepts_unsolicited: bool = True
    is_recurring: bool = False
    is_currently_active: bool = True
    recurrence: str = "Not specified"

    # Contact (L4)
    contact_info: ContactInfo = Field(default_factory=ContactInfo)

    # Provenance (mandatory)
    source_pages: List[str] = []
    source_pdfs: List[str] = []
    extraction_method: str = ""
    extraction_model: str = ""
    extraction_prompt_version: str = ""
    extraction_timestamp: Optional[datetime] = None
    extraction_confidence: float = 0.0
    evidence_quotes: Dict[str, str] = {}

    # Quality
    completeness_score: float = 0.0

    # Lifecycle
    first_seen_at: datetime = Field(default_factory=datetime.utcnow)
    last_verified_at: datetime = Field(default_factory=datetime.utcnow)
    is_stale: bool = False
    duplicate_of_program_id: Optional[str] = None
    superseded_by_program_id: Optional[str] = None
    version: int = 1
    previous_version_id: Optional[str] = None

    @field_validator("eligible_applicant_types", mode="before")
    @classmethod
    def _check_applicant_types(cls, v):
        if v:
            try:
                return validate_applicant_types(v)
            except ValueError:
                return v  # flag for review rather than hard reject
        return v

    @field_validator("eligible_focus_areas", mode="before")
    @classmethod
    def _check_focus_areas(cls, v):
        if v:
            try:
                return validate_focus_areas(v)
            except ValueError:
                return v
        return v

    @field_validator("application_method", mode="before")
    @classmethod
    def _check_app_methods(cls, v):
        if v:
            try:
                return validate_application_methods(v)
            except ValueError:
                return v
        return v

    def compute_completeness(self) -> float:
        """Fraction of meaningful fields that are populated (not empty/None/'Not specified')."""
        fields_to_check = [
            self.funding_priorities, self.types_of_grant, self.grant_amount_freeform,
            self.eligibility_criteria, self.eligible_applicants_freeform,
            self.proposal_deadline_freeform, self.application_method,
            self.eligible_focus_areas, self.eligible_geographies,
        ]
        populated = sum(
            1 for f in fields_to_check
            if f and f not in ("", "Not specified", [], None)
        )
        return round(populated / len(fields_to_check), 2)
