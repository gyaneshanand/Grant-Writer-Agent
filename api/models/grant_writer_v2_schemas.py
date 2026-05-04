"""Request/response Pydantic models for the Grant Writer v2 API."""
from typing import Any, Optional
from pydantic import BaseModel, Field

from agents.grant_writer_v2.schemas.common import FoundationInput


class LayerRunRequest(FoundationInput):
    """Request body for POST /layer/{layer}/run — identical to FoundationInput."""
    pass


class PipelineRunRequest(FoundationInput):
    """Request body for POST /pipeline/run."""
    start_layer: int = Field(default=1, ge=1, le=5)
    end_layer: int = Field(default=5, ge=1, le=5)


class LayerRunResponse(BaseModel):
    ein: str
    layer: int
    status: str
    output: dict[str, Any]
    cost_usd: float = 0.0
    duration_ms: int = 0


class PipelineRunResponse(BaseModel):
    ein: str
    layers_run: list[int]
    final_status: str
    outputs: dict[str, Any]
    total_cost_usd: float = 0.0
    total_duration_ms: int = 0
