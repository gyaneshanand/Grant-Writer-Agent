"""Thin service wrapper for grant_writer_v2 pipeline calls."""
from agents.grant_writer_v2.orchestrator import run_layer, run_pipeline
from agents.grant_writer_v2.schemas.common import FoundationInput


async def run_single_layer(layer: int, foundation: FoundationInput) -> dict:
    return await run_layer(layer, foundation)


async def run_full_pipeline(
    foundation: FoundationInput,
    start_layer: int = 1,
    end_layer: int = 5,
) -> dict:
    return await run_pipeline(foundation, start_layer=start_layer, end_layer=end_layer)
