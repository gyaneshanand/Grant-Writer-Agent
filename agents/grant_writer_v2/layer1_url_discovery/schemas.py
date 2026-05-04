from __future__ import annotations
from datetime import datetime
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field

from agents.grant_writer_v2.schemas.common import CandidateRecord

Layer1Status = Literal[
    "accepted_kg",
    "accepted_verifier",
    "accepted_llm",
    "rejected_no_candidates",
    "rejected_shell_address",
    "rejected_low_confidence",
    "needs_review",
    "error_serpapi",
    "error_blocked",
    "error_timeout",
]


class Layer1Output(BaseModel):
    ein: str
    status: Layer1Status
    url: Optional[str] = None
    confidence: float = 0.0

    method: str = ""
    evidence: str = ""
    evidence_signals: Dict[str, Any] = {}

    google_place_id: Optional[str] = None
    knowledge_graph_present: bool = False
    knowledge_graph_unclaimed: Optional[bool] = None

    serpapi_query: str = ""
    serpapi_total_results: Optional[int] = None
    candidates_seen: List[CandidateRecord] = []

    verifier_score: Optional[float] = None
    verifier_signals: Optional[Dict[str, float]] = None
    llm_rerank_used: bool = False
    llm_rerank_model: Optional[str] = None
    llm_rerank_reasoning: Optional[str] = None

    processed_at: datetime = Field(default_factory=datetime.utcnow)
    processing_ms: int = 0
    cost_usd: float = 0.0
