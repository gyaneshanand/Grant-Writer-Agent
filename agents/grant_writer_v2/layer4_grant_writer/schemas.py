"""Layer 4 output schema."""
from typing import Optional
from pydantic import BaseModel
from agents.grant_writer_v2.schemas.grant_program import GrantProgramRecord


class Layer4Output(BaseModel):
    ein: str
    status: str     # "completed" | "error_no_layer2" | "error_no_programs" | "error_extraction"
    programs_written: int = 0
    consolidated_description: Optional[str] = None
    cost_usd: float = 0.0
    processing_ms: int = 0
    error: Optional[str] = None
