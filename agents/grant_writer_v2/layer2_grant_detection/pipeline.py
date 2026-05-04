"""
Layer 2 — Grant Detection.
async def run(foundation: FoundationInput) -> Layer2Output

Flow:
  1. Read v2_layer1_url from DB — return 409-equivalent error if missing
  2. Build initial GraphState
  3. Run LangGraph StateGraph (crawl → identify → evaluate → aggregate)
  4. Persist verdicts to v2_grant_programs + foundations rollup columns
  5. Write audit row to v2_pipeline_runs
"""
import json
import time
import uuid

from agents.grant_writer_v2.core.audit import write_pipeline_run
from agents.grant_writer_v2.core.corpus_cache import save_corpus
from agents.grant_writer_v2.core.db import sql_exec, sql_exec_many, sql_one
from agents.grant_writer_v2.core.llm import start_run, clear_run, get_run_cost
from agents.grant_writer_v2.core.logger import get_logger
from agents.grant_writer_v2.layer2_grant_detection.graph import build_graph
from agents.grant_writer_v2.layer2_grant_detection.schemas import Layer2Output
from agents.grant_writer_v2.layer2_grant_detection.verdict_aggregator import aggregate
from agents.grant_writer_v2.schemas.common import FoundationInput
from agents.grant_writer_v2.schemas.grant_program import GrantProgramVerdict

logger = get_logger("layer2")


async def run(foundation: FoundationInput) -> Layer2Output:
    start = time.monotonic()
    ein = foundation.ein
    run_id = uuid.uuid4().hex
    start_run(run_id)

    try:
        # 1. Read prerequisite from DB
        row = await sql_one(
            "SELECT v2_layer1_url, v2_layer1_status FROM foundations WHERE ein = :ein",
            {"ein": ein},
        )
        if not row or not row["v2_layer1_url"]:
            output = Layer2Output(
                ein=ein,
                status="error_no_url",
                error="prerequisite_missing: layer1 has not completed for this EIN",
                processing_ms=_ms(start),
            )
            await write_pipeline_run(
                ein=ein, layer="layer2", status=output.status,
                output_snapshot={"error": output.error},
                cost_usd=0.0, duration_ms=output.processing_ms,
            )
            return output

        raw_url = row["v2_layer1_url"]
        # Always start crawl from root domain, not a deep page
        from urllib.parse import urlparse
        parsed = urlparse(raw_url)
        base_url = f"{parsed.scheme}://{parsed.netloc}/"
        logger.info(f"[L2] {ein} — crawling {base_url} (L1 url: {raw_url})")

        # 2. Build shared state_ref (tools mutate this, graph reads it)
        state_ref: dict = {
            "ein": ein,
            "base_url": base_url,
            "visited_urls": [],
            "corpus": [],
            "iterations": 0,
            "pages_fetched": 0,
            "pdfs_processed": 0,
            "bytes_fetched": 0,
            "cost_usd": 0.0,
        }

        initial_state = {
            "ein": ein,
            "org_name": foundation.org_name,
            "base_url": base_url,
            "run_id": run_id,
            "visited_urls": [],
            "corpus": [],
            "messages": [],
            "iterations": 0,
            "pages_fetched": 0,
            "pdfs_processed": 0,
            "bytes_fetched": 0,
            "cost_usd": 0.0,
            "programs": [],
            "verdicts": [],
            "stop_reason": "",
            "error": None,
        }

        # 3. Run the graph
        graph = build_graph(state_ref)
        try:
            final_state = await graph.ainvoke(initial_state)
        except Exception as e:
            logger.error(f"[L2] graph.ainvoke failed for {ein}: {e}")
            cost = get_run_cost(run_id)
            output = Layer2Output(
                ein=ein, status="error_graph",
                cost_usd=cost, processing_ms=_ms(start),
                error=str(e),
                stop_reason="error",
            )
            await _persist(foundation, output, [])
            return output

        # 4. Persist corpus for L3/L4 to reuse
        corpus = state_ref.get("corpus", [])
        if corpus:
            save_corpus(ein, corpus)

        # Extract results
        verdicts: list[GrantProgramVerdict] = final_state.get("verdicts", [])
        stop_reason = final_state.get("stop_reason", "completed") or "completed"
        cost_usd = get_run_cost(run_id)

        rollup_str, valid_count, total_count = aggregate(verdicts)

        pages = final_state.get("pages_fetched", 0)
        if not verdicts and pages == 0:
            status = "needs_review"
            stop_reason = "bot_protected"
            rollup_str = "UNKNOWN_BOT_PROTECTED"
        elif not verdicts:
            status = "rejected_no_programs"
        elif stop_reason not in ("completed", ""):
            status = "needs_review"
        else:
            status = "completed"

        output = Layer2Output(
            ein=ein,
            status=status,
            rollup_verdict=rollup_str,
            valid_program_count=valid_count,
            total_program_count=total_count,
            programs=verdicts,
            stop_reason=stop_reason,
            pages_fetched=final_state.get("pages_fetched", 0),
            pdfs_processed=final_state.get("pdfs_processed", 0),
            cost_usd=cost_usd,
            processing_ms=_ms(start),
        )

        await _persist(foundation, output, verdicts)
        return output

    finally:
        clear_run(run_id)


def _ms(start: float) -> int:
    return int((time.monotonic() - start) * 1000)


async def _persist(
    foundation: FoundationInput,
    output: Layer2Output,
    verdicts: list[GrantProgramVerdict],
) -> None:
    ein = foundation.ein

    # Update foundations rollup columns
    try:
        await sql_exec(
            """
            UPDATE foundations SET
              v2_layer2_status             = :status,
              v2_layer2_rollup_verdict     = :rollup,
              v2_layer2_valid_program_count= :valid_count,
              v2_layer2_program_count      = :total_count,
              v2_layer2_stop_reason        = :stop_reason,
              v2_layer2_cost_usd           = :cost_usd,
              v2_layer2_processed_at       = NOW(),
              v2_pipeline_status           = :pipeline_status
            WHERE ein = :ein
            """,
            {
                "ein": ein,
                "status": output.status,
                "rollup": output.rollup_verdict,
                "valid_count": output.valid_program_count,
                "total_count": output.total_program_count,
                "stop_reason": output.stop_reason,
                "cost_usd": output.cost_usd,
                "pipeline_status": "layer2_done" if output.rollup_verdict else "layer2_rejected",
            },
        )
    except Exception as e:
        logger.error(f"[L2] persist foundations update failed for {ein}: {e}")

    # Persist individual program verdicts
    if verdicts:
        rows = [
            {
                "program_id": v.program_id,
                "ein": ein,
                "program_name": v.program_name,
                "verdict": v.verdict,
                "verdict_confidence": v.verdict_confidence,
                "rules_json": v.rules.model_dump_json() if v.rules else None,
            }
            for v in verdicts
        ]
        try:
            await sql_exec_many(
                """
                INSERT INTO v2_grant_programs
                  (program_id, ein, program_name, verdict, verdict_confidence, rules_json)
                VALUES
                  (:program_id, :ein, :program_name, :verdict, :verdict_confidence, :rules_json)
                ON DUPLICATE KEY UPDATE
                  verdict            = VALUES(verdict),
                  verdict_confidence = VALUES(verdict_confidence),
                  rules_json         = VALUES(rules_json)
                """,
                rows,
            )
        except Exception as e:
            logger.error(f"[L2] persist v2_grant_programs failed for {ein}: {e}")

    await write_pipeline_run(
        ein=ein,
        layer="layer2",
        status=output.status,
        output_snapshot={
            "rollup_verdict": output.rollup_verdict,
            "valid_program_count": output.valid_program_count,
            "total_program_count": output.total_program_count,
            "stop_reason": output.stop_reason,
            "pages_fetched": output.pages_fetched,
            "pdfs_processed": output.pdfs_processed,
        },
        cost_usd=output.cost_usd,
        duration_ms=output.processing_ms,
    )
