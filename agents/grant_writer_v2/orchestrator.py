"""
Orchestrator for grant_writer_v2.
Called by the API service when Laravel requests multiple layers in one HTTP call.
Each layer is independently invokable — this is just a sequencing convenience.
"""
from typing import Optional

from agents.grant_writer_v2.core.logger import get_logger
from agents.grant_writer_v2.schemas.common import FoundationInput

logger = get_logger("orchestrator")

# Prerequisite map: layer N requires layer N-1 to have a non-error output
_PREREQS = {2: 1, 3: 2, 4: 2, 5: 4}

# Terminal-reject statuses that stop the pipeline
_TERMINAL_REJECT = {
    "rejected_no_candidates", "rejected_low_confidence",
    "rejected_no_programs", "error_no_url", "error_serpapi",
}


async def run_layer(layer: int, foundation: FoundationInput) -> dict:
    """
    Run a single layer and return its output as a dict.
    Raises ValueError for unknown layer numbers.
    """
    if layer == 1:
        from agents.grant_writer_v2.layer1_url_discovery.pipeline import run
    elif layer == 2:
        from agents.grant_writer_v2.layer2_grant_detection.pipeline import run
    elif layer == 3:
        from agents.grant_writer_v2.layer3_org_extraction.pipeline import run
    elif layer == 4:
        from agents.grant_writer_v2.layer4_grant_writer.pipeline import run
    elif layer == 5:
        from agents.grant_writer_v2.layer5_metadata_seo.pipeline import run
    else:
        raise ValueError(f"Unknown layer: {layer}")

    output = await run(foundation)
    return output.model_dump()


async def run_pipeline(
    foundation: FoundationInput,
    start_layer: int = 1,
    end_layer: int = 5,
) -> dict:
    """
    Run layers [start_layer, end_layer] sequentially for one foundation.
    Short-circuits on terminal reject.
    Returns dict: {layer_number: layer_output_dict, "total_cost_usd": float, "total_duration_ms": int}
    """
    outputs: dict = {}
    total_cost = 0.0
    total_ms = 0

    for layer in range(start_layer, end_layer + 1):
        try:
            result = await run_layer(layer, foundation)
            outputs[layer] = result
            total_cost += result.get("cost_usd", 0.0)
            total_ms += result.get("processing_ms", 0)

            status = result.get("status", "")
            if status in _TERMINAL_REJECT:
                logger.info(
                    f"[orchestrator] {foundation.ein} — terminal reject at layer {layer}: {status}"
                )
                break

        except Exception as e:
            logger.error(f"[orchestrator] {foundation.ein} layer {layer} error: {e}")
            outputs[layer] = {"status": "error", "error": str(e)}
            break

    # Determine final status
    last_layer = max(outputs.keys()) if outputs else start_layer
    final_status = outputs.get(last_layer, {}).get("status", "error")

    return {
        "ein": foundation.ein,
        "layers_run": sorted(outputs.keys()),
        "final_status": final_status,
        "outputs": outputs,
        "total_cost_usd": round(total_cost, 6),
        "total_duration_ms": total_ms,
    }
