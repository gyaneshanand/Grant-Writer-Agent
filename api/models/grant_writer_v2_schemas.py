"""Request/response Pydantic models for the Grant Writer v2 API."""
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from agents.grant_writer_v2.schemas.common import FoundationInput


class LayerRunRequest(FoundationInput):
    """Request body for POST /layer/{layer}/run — identical to FoundationInput."""
    pass


class PipelineRunRequest(FoundationInput):
    """Request body for POST /pipeline/run."""
    start_layer: int = Field(default=1, ge=1, le=5)
    end_layer: int = Field(default=5, ge=1, le=5)


class LayerRunResponse(BaseModel):
    ein: str
    layer: int
    status: str
    output: Dict[str, Any]
    cost_usd: float = 0.0
    duration_ms: int = 0


class PipelineRunResponse(BaseModel):
    ein: str
    layers_run: List[int]
    final_status: str
    outputs: Dict[str, Any]
    total_cost_usd: float = 0.0
    total_duration_ms: int = 0


# ── v2 result response — backward-compatible with v1 PipelineResponse ─────────

class V2GrantData(BaseModel):
    """Per-program structured data. Mirrors v1 GrantDataResponse + v2 extra fields."""
    # v1 backward-compatible fields
    grant_name: str = "Not specified"
    funding_priorities: str = "Not specified"
    types_of_grant: str = "Not specified"
    eligibility_criteria: str = "Not specified"
    eligible_applicants: List[str] = []
    eligible_locations: str = "Not specified"
    grant_amount_range: str = "Not specified"
    grant_amount: str = "Not specified"
    proposal_deadline: str = "Not specified"
    recurrence: str = "Not specified"
    contact_info: Dict[str, str] = Field(default_factory=lambda: {
        "email": "Not specified", "phone": "Not specified", "address": "Not specified"
    })
    organization_info: str = "Not specified"
    grant_summary: str = "Not specified"
    grant_url: str = "Not specified"

    # v2 extra fields
    program_id: Optional[str] = None
    verdict: Optional[str] = None
    grant_amount_min_usd: Optional[float] = None
    grant_amount_max_usd: Optional[float] = None
    grant_amount_typical_usd: Optional[float] = None
    deadline_type: Optional[str] = None
    next_deadline_iso: Optional[str] = None
    is_currently_open: Optional[bool] = None
    loi_required: Optional[bool] = None
    accepts_unsolicited: Optional[bool] = None
    is_recurring: Optional[bool] = None
    is_invitation_only: Optional[bool] = None
    eligible_geographies: List[str] = []
    eligible_focus_areas: List[str] = []
    eligible_applicant_types: List[str] = []
    application_method: List[str] = []
    application_portal_url: Optional[str] = None
    application_steps: List[str] = []
    required_documents: List[str] = []
    excluded_uses: List[str] = []

    # v2 SEO fields (populated by L5)
    program_slug: Optional[str] = None
    opportunity_title: Optional[str] = None
    h1_tag: Optional[str] = None
    meta_title: Optional[str] = None
    meta_description: Optional[str] = None
    opportunity_teaser: Optional[str] = None
    opportunity_title_for_subscriber: Optional[str] = None
    search_blob: Optional[str] = None


class V2OrganizationData(BaseModel):
    """Org profile. Mirrors v1 OrganizationDataResponse + v2 extra fields."""
    # v1 backward-compatible fields
    org_name: str
    mission: Optional[str] = None
    background: Optional[str] = None
    about: Optional[str] = None
    contact: Optional[Dict[str, Any]] = None

    # v2 extra fields
    legal_name: Optional[str] = None
    foundation_type: Optional[str] = None
    focus_areas: List[str] = []
    geography_served: Optional[str] = None
    annual_giving_usd: Optional[float] = None
    total_assets_usd: Optional[float] = None
    foundation_url: Optional[str] = None


class V2Metadata(BaseModel):
    """SEO metadata. Mirrors v1 MetadataWriterResponse + opportunity_teaser."""
    opportunity_title: str = "Not specified"
    h1_tag: str = "Not specified"
    meta_title: str = "Not specified"
    meta_description: str = "Not specified"
    opportunity_teaser: str = "Not specified"       # ~500-word vague narrative (new in v2)
    opportunity_title_for_subscriber: str = "Not specified"


class V2PipelineResponse(BaseModel):
    """
    Full pipeline result for an EIN.
    Backward-compatible with v1 PipelineResponse shape:
      grants_data, organization_data, consolidated_description, metadata
    Plus v2 pipeline status fields on top.
    """
    # v1 backward-compatible fields
    grants_data: List[V2GrantData] = []
    organization_data: Optional[V2OrganizationData] = None
    consolidated_description: str = ""
    metadata: V2Metadata = Field(default_factory=V2Metadata)

    # v2 pipeline status
    ein: str
    pipeline_status: Optional[str] = None
    layer1_status: Optional[str] = None
    layer2_rollup_verdict: Optional[str] = None
    layer2_program_count: int = 0
    layer2_valid_program_count: int = 0
    foundation_url: Optional[str] = None
