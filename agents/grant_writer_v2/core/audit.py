"""
Audit helpers — write pipeline run rows to v2_pipeline_runs.
"""
import json
import uuid
from datetime import datetime
from typing import Any, Optional

from agents.grant_writer_v2.core.logger import get_logger

logger = get_logger("audit")


async def write_pipeline_run(
    ein: str,
    layer: str,
    status: str,
    output_snapshot: dict[str, Any],
    *,
    model: Optional[str] = None,
    prompt_version: Optional[str] = None,
    cost_usd: float = 0.0,
    duration_ms: int = 0,
) -> str:
    """
    Append a row to v2_pipeline_runs. Returns the run_id.
    Best-effort — logs warning on failure but never raises.
    """
    run_id = str(uuid.uuid4())
    try:
        from agents.grant_writer_v2.core.db import sql_exec
        await sql_exec(
            """
            INSERT INTO v2_pipeline_runs
              (run_id, ein, layer, status, output_snapshot, model,
               prompt_version, cost_usd, duration_ms)
            VALUES
              (:run_id, :ein, :layer, :status, :output_snapshot, :model,
               :prompt_version, :cost_usd, :duration_ms)
            """,
            {
                "run_id": run_id,
                "ein": ein,
                "layer": layer,
                "status": status,
                "output_snapshot": json.dumps(output_snapshot),
                "model": model,
                "prompt_version": prompt_version,
                "cost_usd": cost_usd,
                "duration_ms": duration_ms,
            },
        )
    except Exception as e:
        logger.warning(f"Failed to write pipeline run for {ein}/{layer}: {e}")
    return run_id
