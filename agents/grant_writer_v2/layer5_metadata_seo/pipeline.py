"""
Layer 5 — Metadata & SEO.
async def run(foundation: FoundationInput) -> Layer5Output

Flow:
  1. Check DB that L4 has completed; load L4-populated v2_grant_programs rows
  2. For each program: generate SEO fields, derive filters, generate slug, run dedup
  3. Write back to v2_grant_programs + set publish_status
  4. Write audit row to v2_pipeline_runs
"""
import time
import uuid

from agents.grant_writer_v2.core.audit import write_pipeline_run
from agents.grant_writer_v2.core.db import sql_all, sql_exec, sql_one
from agents.grant_writer_v2.core.llm import start_run, clear_run, get_run_cost
from agents.grant_writer_v2.core.logger import get_logger
from agents.grant_writer_v2.layer5_metadata_seo.duplicate_detector import build_search_blob, find_duplicate
from agents.grant_writer_v2.layer5_metadata_seo.filter_deriver import derive_filters
from agents.grant_writer_v2.layer5_metadata_seo.schemas import Layer5Output
from agents.grant_writer_v2.layer5_metadata_seo.seo_generator import generate_seo
from agents.grant_writer_v2.layer5_metadata_seo.slug_generator import generate_slug
from agents.grant_writer_v2.schemas.common import FoundationInput

logger = get_logger("layer5")


async def run(foundation: FoundationInput) -> Layer5Output:
    start = time.monotonic()
    ein = foundation.ein
    run_id = uuid.uuid4().hex
    start_run(run_id)

    try:
        # 1. Check prereq
        row = await sql_one(
            "SELECT v2_layer4_status FROM foundations WHERE ein = :ein",
            {"ein": ein},
        )
        if not row or row["v2_layer4_status"] != "completed":
            output = Layer5Output(
                ein=ein, status="error_no_layer4",
                error="prerequisite_missing: layer4 has not completed for this EIN",
                processing_ms=_ms(start),
            )
            await write_pipeline_run(ein=ein, layer="layer5", status=output.status,
                                     output_snapshot={"error": output.error},
                                     cost_usd=0.0, duration_ms=output.processing_ms)
            return output

        # Load consolidated description from L4 (primary input for SEO generation)
        desc_row = await sql_one(
            "SELECT v2_layer4_consolidated_description FROM foundations WHERE ein = :ein",
            {"ein": ein},
        )
        consolidated_description = (desc_row["v2_layer4_consolidated_description"] or "") if desc_row else ""

        # Load programs
        programs = await sql_all(
            """SELECT program_id, program_name, eligible_focus_areas, grant_amount_freeform,
                      proposal_deadline_freeform, eligibility_criteria,
                      eligible_applicant_types, eligible_geographies,
                      grant_amount_min_usd, grant_amount_max_usd, grant_amount_typical_usd,
                      deadline_type, is_currently_open, accepts_unsolicited, loi_required
               FROM v2_grant_programs
               WHERE ein = :ein AND verdict = 'VALID'""",
            {"ein": ein},
        )
        if not programs:
            output = Layer5Output(
                ein=ein, status="error_no_programs",
                error="No VALID programs found for this EIN",
                processing_ms=_ms(start),
            )
            await write_pipeline_run(ein=ein, layer="layer5", status=output.status,
                                     output_snapshot={"error": output.error},
                                     cost_usd=0.0, duration_ms=output.processing_ms)
            return output

        # Build existing blobs for dedup (across all programs for this EIN)
        enriched_blobs: list[dict] = []
        enriched_count = 0

        import json
        for _prog in programs:
            prog = dict(_prog)  # databases Record → plain dict
            def _safe(val):
                if not val:
                    return []
                if isinstance(val, list):
                    return val
                try:
                    return json.loads(val)
                except Exception:
                    return []

            focus_areas = _safe(prog.get("eligible_focus_areas"))

            # Generate SEO — primary input is the L4 consolidated description
            seo = await generate_seo(
                program_name=prog["program_name"],
                org_name=foundation.org_name,
                focus_areas=focus_areas,
                grant_amount=prog.get("grant_amount_freeform") or "",
                deadline=prog.get("proposal_deadline_freeform") or "",
                eligibility_summary=prog.get("eligibility_criteria") or "",
                ein=ein,
                run_id=run_id,
                consolidated_description=consolidated_description,
                budget_usd=0.05,
            )

            # Generate slug
            slug = generate_slug(foundation.org_name, prog["program_name"], ein)

            # Derive filters
            filters = derive_filters(dict(prog))

            # Build search blob
            enriched_row = {**dict(prog), **seo}
            search_blob = build_search_blob(enriched_row)

            # Dedup check
            duplicate_of = find_duplicate(prog["program_id"], search_blob, enriched_blobs)
            enriched_blobs.append({"program_id": prog["program_id"], "search_blob": search_blob})

            publish_status = "duplicate" if duplicate_of else "ready"

            # Write back
            await _persist_program(
                program_id=prog["program_id"],
                ein=ein,
                slug=slug,
                seo=seo,
                filters=filters,
                search_blob=search_blob,
                duplicate_of=duplicate_of,
                publish_status=publish_status,
            )
            enriched_count += 1

        cost_usd = get_run_cost(run_id)

        # Mark pipeline done on foundations row
        try:
            await sql_exec(
                """UPDATE foundations SET
                     v2_layer5_status = 'completed',
                     v2_layer5_processed_at = NOW(),
                     v2_pipeline_status = 'completed'
                   WHERE ein = :ein""",
                {"ein": ein},
            )
        except Exception as e:
            logger.error(f"[L5] update foundations status failed for {ein}: {e}")

        output = Layer5Output(
            ein=ein, status="completed",
            programs_enriched=enriched_count,
            cost_usd=cost_usd, processing_ms=_ms(start),
        )
        await write_pipeline_run(
            ein=ein, layer="layer5", status="completed",
            output_snapshot={"programs_enriched": enriched_count},
            cost_usd=cost_usd, duration_ms=output.processing_ms,
        )
        return output

    finally:
        clear_run(run_id)


def _ms(start: float) -> int:
    return int((time.monotonic() - start) * 1000)


async def _persist_program(
    program_id: str,
    ein: str,
    slug: str,
    seo: dict,
    filters: dict,
    search_blob: str,
    duplicate_of,
    publish_status: str,
) -> None:
    try:
        import json
        await sql_exec(
            """
            UPDATE v2_grant_programs SET
              slug                              = :slug,
              opportunity_title                 = :opportunity_title,
              h1_tag                            = :h1_tag,
              meta_title                        = :meta_title,
              meta_description                  = :meta_description,
              opportunity_teaser                = :opportunity_teaser,
              opportunity_title_for_subscriber  = :opportunity_title_for_subscriber,
              filter_focus_areas                = :filter_focus_areas,
              filter_applicant_types            = :filter_applicant_types,
              filter_geographies                = :filter_geographies,
              filter_funding_bucket             = :filter_funding_bucket,
              filter_deadline_type              = :filter_deadline_type,
              filter_is_open                    = :filter_is_open,
              filter_accepts_unsolicited        = :filter_accepts_unsolicited,
              filter_loi_required               = :filter_loi_required,
              filter_geo_scope                  = :filter_geo_scope,
              search_blob                       = :search_blob,
              duplicate_of_program_id           = :duplicate_of,
              publish_status                    = :publish_status
            WHERE program_id = :program_id AND ein = :ein
            """,
            {
                "program_id": program_id,
                "ein": ein,
                "slug": slug,
                "opportunity_title": seo.get("opportunity_title", "")[:70],
                "h1_tag": seo.get("h1_tag", "")[:60],
                "meta_title": seo.get("meta_title", "")[:60],
                "meta_description": seo.get("meta_description", "")[:150],
                "opportunity_teaser": seo.get("opportunity_teaser", ""),
                "opportunity_title_for_subscriber": seo.get("opportunity_title_for_subscriber", "")[:150],
                **filters,
                "search_blob": search_blob[:65535],
                "duplicate_of": duplicate_of,
                "publish_status": publish_status,
            },
        )
    except Exception as e:
        logger.error(f"[L5] persist program {program_id} failed: {e}")
