"""Layer 5 output schema."""
from typing import Optional
from pydantic import BaseModel


class Layer5Output(BaseModel):
    ein: str
    status: str     # "completed" | "error_no_layer4" | "error_no_programs"
    programs_enriched: int = 0
    cost_usd: float = 0.0
    processing_ms: int = 0
    error: Optional[str] = None
