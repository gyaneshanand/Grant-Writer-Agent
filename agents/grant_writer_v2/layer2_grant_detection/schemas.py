"""Layer 2 Pydantic schemas and LangGraph GraphState."""
from typing import Annotated, Any, Optional
from typing_extensions import TypedDict
from pydantic import BaseModel

from agents.grant_writer_v2.schemas.grant_program import GrantProgramVerdict


# ── LangGraph state ────────────────────────────────────────────────────────────

class GraphState(TypedDict):
    # inputs (set once at graph entry)
    ein: str
    org_name: str
    base_url: str           # verified URL from L1
    run_id: str

    # agent accumulators
    visited_urls: list[str]
    corpus: list[dict]      # list of {url, text, content_type, source}
    messages: Annotated[list, lambda x, y: x + y]   # LangGraph message accumulation

    # cap counters (all checked by conditional edges)
    iterations: int
    pages_fetched: int
    pdfs_processed: int
    bytes_fetched: int
    cost_usd: float

    # downstream nodes
    programs: list[dict]            # raw program dicts from program_identifier
    verdicts: list[GrantProgramVerdict]
    stop_reason: str                # completed | max_iterations | max_pages | max_bytes | max_cost | error
    error: Optional[str]


# ── Pipeline output ────────────────────────────────────────────────────────────

class Layer2Output(BaseModel):
    ein: str
    status: str         # "completed" | "rejected_no_programs" | "error_no_url" | "error_graph" | "needs_review"
    rollup_verdict: Optional[str] = None    # VALID | INVALID | NEEDS_REVIEW
    valid_program_count: int = 0
    total_program_count: int = 0
    programs: list[GrantProgramVerdict] = []
    stop_reason: Optional[str] = None
    pages_fetched: int = 0
    pdfs_processed: int = 0
    cost_usd: float = 0.0
    processing_ms: int = 0
    error: Optional[str] = None
