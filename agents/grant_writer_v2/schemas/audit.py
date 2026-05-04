from __future__ import annotations
from datetime import datetime
from typing import Any, Dict, Literal, Optional
from pydantic import BaseModel, Field


class PipelineRun(BaseModel):
    run_id: str
    ein: str
    layer: Literal["layer1", "layer2", "layer3", "layer4", "layer5"]
    status: str
    output_snapshot: Dict[str, Any] = {}
    model: Optional[str] = None
    prompt_version: Optional[str] = None
    cost_usd: float = 0.0
    duration_ms: int = 0
    created_at: datetime = Field(default_factory=datetime.utcnow)


class LLMCallRecord(BaseModel):
    id: Optional[int] = None
    ein: Optional[str] = None
    layer: str = ""
    provider: str = "openrouter"
    model: str = ""
    prompt_hash: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    latency_ms: int = 0
    status: str = "ok"
    error_message: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
