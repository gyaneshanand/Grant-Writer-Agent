"""Layer 5 output schema."""
from typing import Any, Optional
from pydantic import BaseModel


class ProgramSEOResult(BaseModel):
    program_id: str
    program_name: str
    slug: str
    opportunity_title: str
    h1_tag: str
    meta_title: str
    meta_description: str
    opportunity_teaser: str
    opportunity_title_for_subscriber: str
    filter_focus_areas: list[str]
    filter_applicant_types: list[str]
    filter_geographies: list[str]
    filter_funding_bucket: str
    filter_deadline_type: str
    filter_is_open: Optional[bool]
    filter_accepts_unsolicited: bool
    filter_loi_required: bool
    filter_geo_scope: str
    publish_status: str
    duplicate_of_program_id: Optional[str]


class Layer5Output(BaseModel):
    ein: str
    status: str     # "completed" | "error_no_layer4" | "error_no_programs"
    programs_enriched: int = 0
    programs: list[ProgramSEOResult] = []
    cost_usd: float = 0.0
    processing_ms: int = 0
    error: Optional[str] = None
