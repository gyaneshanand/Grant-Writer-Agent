from __future__ import annotations
from datetime import datetime
from typing import Dict, List, Optional
from pydantic import BaseModel, Field

from agents.grant_writer_v2.schemas.common import ContactInfo


class OrgProfile(BaseModel):
    """Foundation-level org profile produced by Layer 3."""
    ein: str
    org_name: str
    mission: str = ""
    background: str = ""
    about: str = ""
    contact: ContactInfo = Field(default_factory=ContactInfo)

    # Identity
    legal_name: str = ""
    dba_names: List[str] = []
    foundation_type: str = "unknown"
    irs_subsection: str = "501(c)(3)"
    irs_ruling_year: Optional[int] = None
    ntee_code: Optional[str] = None

    # Web presence
    website_url: Optional[str] = None
    website_confidence: Optional[float] = None
    social_profiles: Dict[str, str] = {}

    # Focus & geography (controlled vocabularies)
    focus_areas: List[str] = []
    focus_areas_detail: str = ""
    geography_served: List[str] = []
    geography_served_detail: str = ""
    populations_served: List[str] = []

    # Financials (from 990-PF — no LLM)
    total_assets_usd: Optional[float] = None
    total_assets_year: Optional[int] = None
    annual_giving_usd: Optional[float] = None
    annual_giving_year: Optional[int] = None
    grants_paid_3yr_avg_usd: Optional[float] = None
    typical_grant_count_per_year: Optional[int] = None
    fiscal_year_end: Optional[str] = None

    # Operations
    founded_year: Optional[int] = None
    administrative_address_pattern: Optional[str] = None

    # Grant-making summary
    grant_program_count: int = 0
    grant_program_names: List[str] = []
    accepts_unsolicited_proposals: bool = True
    is_invitation_only: bool = False
    application_methods_offered: List[str] = []

    # Provenance
    source_pages: List[str] = []
    extraction_model: Optional[str] = None
    extraction_prompt_version: Optional[str] = None
    evidence_quotes: Dict[str, str] = {}

    # Lifecycle
    first_seen_at: datetime = Field(default_factory=datetime.utcnow)
    last_verified_at: datetime = Field(default_factory=datetime.utcnow)
    is_stale: bool = False
