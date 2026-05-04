from __future__ import annotations
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field


class SeoMetadata(BaseModel):
    """6 LLM-generated SEO fields with strict character limits."""
    opportunity_title: str = Field(max_length=70, default="")
    h1_tag: str = Field(max_length=60, default="")
    meta_title: str = Field(max_length=60, default="")
    meta_description: str = Field(max_length=160, default="")
    opportunity_teaser: str = ""
    opportunity_title_for_subscriber: str = Field(max_length=150, default="")


class GrantProgramMetadata(BaseModel):
    """Layer 5 enrichment appended to GrantProgramRecord at storage."""
    program_id: str
    foundation_ein: str

    # SEO copy (from SeoMetadata)
    opportunity_title: str = ""
    h1_tag: str = ""
    meta_title: str = ""
    meta_description: str = ""
    opportunity_teaser: str = ""
    opportunity_title_for_subscriber: str = ""

    # URL & nav (deterministic)
    slug: str = ""
    canonical_url: Optional[str] = None

    # Categorization
    categories: List[str] = []
    primary_category: Optional[str] = None
    tags: List[str] = []

    # Filters (deterministic from L4 structured fields)
    filter_funding_range: str = "unspecified"
    filter_funding_min_usd: Optional[float] = None
    filter_funding_max_usd: Optional[float] = None
    filter_eligibility: List[str] = []
    filter_geography_country: List[str] = []
    filter_geography_state: List[str] = []
    filter_geography_scope: str = "national"
    filter_deadline_type: str = "not_specified"
    filter_currently_open: bool = False
    filter_next_deadline_iso: Optional[str] = None
    filter_days_until_deadline: Optional[int] = None

    # Search index
    search_blob: str = ""
    search_keywords: List[str] = []

    # OG / Social
    og_title: Optional[str] = None
    og_description: Optional[str] = None
    og_image_url: Optional[str] = None

    # Dedup
    duplicate_of_program_id: Optional[str] = None
    similarity_score_to_duplicate: Optional[float] = None
    duplicate_review_status: Optional[str] = None

    # Provenance
    generated_by_model: str = ""
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    prompt_version: str = ""

    # Versioning & lifecycle
    version: int = 1
    previous_version_id: Optional[str] = None
    publish_status: str = "draft"
    published_at: Optional[datetime] = None
