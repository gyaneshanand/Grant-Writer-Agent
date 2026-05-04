"""Layer 3 output schema."""
from typing import Optional
from pydantic import BaseModel
from agents.grant_writer_v2.schemas.org_profile import OrgProfile


class Layer3Output(BaseModel):
    ein: str
    status: str     # "completed" | "error_no_corpus" | "error_extraction" | "error_no_layer2"
    profile: Optional[OrgProfile] = None
    cost_usd: float = 0.0
    processing_ms: int = 0
    error: Optional[str] = None
