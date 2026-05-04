from __future__ import annotations
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field


class FoundationInput(BaseModel):
    """Request body Laravel sends to every layer endpoint."""
    org_name: str = Field(..., description="Legal name of the foundation")
    ein: str = Field(..., description="9-digit EIN (IRS identifier), primary key")
    state: str = Field(..., description="2-letter US state code")
    city: Optional[str] = None
    address: Optional[str] = None
    ntee_code: Optional[str] = None


class ContactInfo(BaseModel):
    email: str = ""
    phone: str = ""
    address: str = ""
    contact_person: Optional[str] = None
    contact_title: Optional[str] = None
    secondary_email: Optional[str] = None
    fax: Optional[str] = None
    address_street: Optional[str] = None
    address_city: Optional[str] = None
    address_state: Optional[str] = None
    address_zip: Optional[str] = None
    address_country: Optional[str] = "US"
    other_info: Optional[str] = ""


class DeadlineSlot(BaseModel):
    cycle_label: str = ""
    deadline_iso: Optional[str] = None
    deadline_type: str = "full_proposal"
    is_recurring: bool = False
    raw_text: str = ""


class RuleEvaluation(BaseModel):
    """Result of evaluating one business rule against a grant program."""
    value: bool
    confidence: float = Field(ge=0.0, le=1.0)
    evidence_quote: str = ""
    source_url: str = ""
    extracted_metadata: Dict[str, Any] = {}


class CrawledPage(BaseModel):
    url: str
    title: Optional[str] = None
    http_status: int = 0
    bytes_fetched: int = 0
    keyword_matches: List[str] = []
    extracted_text_chars: int = 0
    used_in_classification: bool = False
    page_type: Optional[str] = None


class CandidateRecord(BaseModel):
    """One URL candidate considered during Layer 1 URL discovery."""
    url: str
    position: int
    title: str = ""
    snippet: str = ""
    blocklisted: bool = False
    blocklist_category: Optional[str] = None
    blocklist_domain: Optional[str] = None
    verifier_score: Optional[float] = None
    verifier_signals: Optional[Dict[str, float]] = None
    selected: bool = False
    rejection_reason: Optional[str] = None
