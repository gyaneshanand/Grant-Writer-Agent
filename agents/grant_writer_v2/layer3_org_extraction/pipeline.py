"""
Layer 3 — Org Profile Extraction.
async def run(foundation: FoundationInput) -> Layer3Output

Flow:
  1. Check DB that L2 has completed for this EIN
  2. Load L2 corpus from disk cache
  3. Run LLM extractor (+ optional about-page fetch)
  4. Persist OrgProfile to foundations table
  5. Write audit row to v2_pipeline_runs
"""
import json
import time
import uuid

from agents.grant_writer_v2.core.audit import write_pipeline_run
from agents.grant_writer_v2.core.corpus_cache import load_corpus
from agents.grant_writer_v2.core.db import sql_exec, sql_one
from agents.grant_writer_v2.core.llm import start_run, clear_run, get_run_cost
from agents.grant_writer_v2.core.logger import get_logger
from agents.grant_writer_v2.layer3_org_extraction.extractor import extract
from agents.grant_writer_v2.layer3_org_extraction.schemas import Layer3Output
from agents.grant_writer_v2.schemas.common import FoundationInput

logger = get_logger("layer3")


async def run(foundation: FoundationInput) -> Layer3Output:
    start = time.monotonic()
    ein = foundation.ein
    run_id = uuid.uuid4().hex
    start_run(run_id)

    try:
        # 1. Check prereq
        row = await sql_one(
            "SELECT v2_layer2_status, v2_layer1_url FROM foundations WHERE ein = :ein",
            {"ein": ein},
        )
        if not row or not row["v2_layer2_status"]:
            output = Layer3Output(
                ein=ein, status="error_no_layer2",
                error="prerequisite_missing: layer2 has not completed for this EIN",
                processing_ms=_ms(start),
            )
            await write_pipeline_run(ein=ein, layer="layer3", status=output.status,
                                     output_snapshot={"error": output.error},
                                     cost_usd=0.0, duration_ms=output.processing_ms)
            return output

        base_url = row["v2_layer1_url"] or ""

        # 2. Load corpus
        corpus = load_corpus(ein)
        if not corpus:
            output = Layer3Output(
                ein=ein, status="error_no_corpus",
                error="L2 corpus not found on disk — re-run layer2 first",
                processing_ms=_ms(start),
            )
            await write_pipeline_run(ein=ein, layer="layer3", status=output.status,
                                     output_snapshot={"error": output.error},
                                     cost_usd=0.0, duration_ms=output.processing_ms)
            return output

        # 3. Extract
        profile = await extract(
            corpus=corpus,
            foundation=foundation,
            base_url=base_url,
            run_id=run_id,
            budget_usd=0.20,
        )
        cost = get_run_cost(run_id)

        if not profile:
            output = Layer3Output(
                ein=ein, status="error_extraction",
                cost_usd=cost, processing_ms=_ms(start),
                error="LLM extraction returned no profile",
            )
            await write_pipeline_run(ein=ein, layer="layer3", status=output.status,
                                     output_snapshot={"error": output.error},
                                     cost_usd=cost, duration_ms=output.processing_ms)
            return output

        output = Layer3Output(
            ein=ein, status="completed",
            profile=profile, cost_usd=cost, processing_ms=_ms(start),
        )

        await _persist(foundation, profile)
        await write_pipeline_run(
            ein=ein, layer="layer3", status="completed",
            output_snapshot={
                "foundation_type": profile.foundation_type,
                "focus_areas": profile.focus_areas,
                "mission_chars": len(profile.mission),
            },
            cost_usd=cost, duration_ms=output.processing_ms,
        )
        return output

    finally:
        clear_run(run_id)


def _ms(start: float) -> int:
    return int((time.monotonic() - start) * 1000)


async def _persist(foundation: FoundationInput, profile) -> None:
    ein = foundation.ein
    try:
        await sql_exec(
            """
            UPDATE foundations SET
              v2_legal_name              = :legal_name,
              v2_mission                 = :mission,
              v2_about                   = :about,
              v2_foundation_type         = :foundation_type,
              v2_focus_areas             = :focus_areas,
              v2_geography_served        = :geography_served,
              v2_annual_giving_usd       = :annual_giving_usd,
              v2_total_assets_usd        = :total_assets_usd,
              v2_layer3_status           = 'completed',
              v2_layer3_processed_at     = NOW(),
              v2_pipeline_status         = 'layer3_done'
            WHERE ein = :ein
            """,
            {
                "ein": ein,
                "legal_name": profile.legal_name,
                "mission": profile.mission,
                "about": profile.about,
                "foundation_type": profile.foundation_type,
                "focus_areas": json.dumps(profile.focus_areas or []),
                "geography_served": json.dumps(profile.geography_served_detail or ""),
                "annual_giving_usd": profile.annual_giving_usd,
                "total_assets_usd": profile.total_assets_usd,
            },
        )
    except Exception as e:
        logger.error(f"[L3] persist failed for {ein}: {e}")
