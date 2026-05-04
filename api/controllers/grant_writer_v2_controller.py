"""Grant Writer v2 API controller — 2 endpoints."""
from fastapi import APIRouter, HTTPException

from api.models.grant_writer_v2_schemas import (
    LayerRunRequest, LayerRunResponse,
    PipelineRunRequest, PipelineRunResponse,
)
from api.services.grant_writer_v2_service import run_single_layer, run_full_pipeline

router = APIRouter(prefix="/grant-writer-v2", tags=["Grant Writer v2"])


@router.post("/layer/{layer}/run", response_model=LayerRunResponse)
async def run_layer(layer: int, request: LayerRunRequest):
    """
    Run a single pipeline layer (1–5) for one foundation.
    Returns 409 if a prerequisite layer hasn't completed.
    Returns 400 if layer number is out of range.
    """
    if layer < 1 or layer > 5:
        raise HTTPException(status_code=400, detail=f"Layer must be 1–5, got {layer}")

    try:
        result = await run_single_layer(layer, request)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Layer {layer} failed: {e}")

    status = result.get("status", "")
    if "prerequisite_missing" in (result.get("error") or ""):
        raise HTTPException(
            status_code=409,
            detail={"error": "prerequisite_missing", "missing_layer": layer - 1},
        )

    return LayerRunResponse(
        ein=request.ein,
        layer=layer,
        status=status,
        output=result,
        cost_usd=result.get("cost_usd", 0.0),
        duration_ms=result.get("processing_ms", 0),
    )


@router.post("/pipeline/run", response_model=PipelineRunResponse)
async def run_pipeline(request: PipelineRunRequest):
    """
    Run a contiguous range of layers for one foundation in one HTTP call.
    Short-circuits on terminal rejection.
    """
    if request.start_layer > request.end_layer:
        raise HTTPException(
            status_code=400,
            detail=f"start_layer ({request.start_layer}) must be ≤ end_layer ({request.end_layer})",
        )

    try:
        result = await run_full_pipeline(
            foundation=request,
            start_layer=request.start_layer,
            end_layer=request.end_layer,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Pipeline failed: {e}")

    return PipelineRunResponse(
        ein=request.ein,
        layers_run=result.get("layers_run", []),
        final_status=result.get("final_status", "error"),
        outputs=result.get("outputs", {}),
        total_cost_usd=result.get("total_cost_usd", 0.0),
        total_duration_ms=result.get("total_duration_ms", 0),
    )
