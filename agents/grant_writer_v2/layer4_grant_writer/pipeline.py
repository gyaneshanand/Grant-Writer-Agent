"""
Layer 4 — Grant Writer.
async def run(foundation: FoundationInput) -> Layer4Output

Flow:
  1. Check DB that L2 has completed; read VALID program verdicts
  2. Load L2 corpus + L3 org profile from DB
  3. Per-program LLM extraction for each VALID verdict
  4. Foundation-level consolidator
  5. Persist GrantProgramRecords to v2_grant_programs + consolidated_description to foundations
  6. Write audit row to v2_pipeline_runs
"""
import json
import time
import uuid

from agents.grant_writer_v2.core.audit import write_pipeline_run
from agents.grant_writer_v2.core.corpus_cache import load_corpus
from agents.grant_writer_v2.core.db import sql_all, sql_exec, sql_exec_many, sql_one
from agents.grant_writer_v2.core.llm import BudgetExceeded, start_run, clear_run, get_run_cost
from agents.grant_writer_v2.core.logger import get_logger
from agents.grant_writer_v2.layer4_grant_writer.consolidator import consolidate
from agents.grant_writer_v2.layer4_grant_writer.per_program_extractor import extract_program
from agents.grant_writer_v2.layer4_grant_writer.schemas import Layer4Output
from agents.grant_writer_v2.schemas.common import FoundationInput
from agents.grant_writer_v2.schemas.grant_program import GrantProgramRecord, GrantProgramVerdict, SixRuleResult
from agents.grant_writer_v2.schemas.common import RuleEvaluation

logger = get_logger("layer4")

LAYER4_BUDGET_USD = 2.0


async def run(foundation: FoundationInput) -> Layer4Output:
    start = time.monotonic()
    ein = foundation.ein
    run_id = uuid.uuid4().hex
    start_run(run_id)

    try:
        # 1. Check prereq
        row = await sql_one(
            "SELECT v2_layer2_rollup_verdict, v2_layer2_status, v2_mission FROM foundations WHERE ein = :ein",
            {"ein": ein},
        )
        if not row or not row.get("v2_layer2_status"):
            output = Layer4Output(
                ein=ein, status="error_no_layer2",
                error="prerequisite_missing: layer2 has not completed for this EIN",
                processing_ms=_ms(start),
            )
            await write_pipeline_run(ein=ein, layer="layer4", status=output.status,
                                     output_snapshot={"error": output.error},
                                     cost_usd=0.0, duration_ms=output.processing_ms)
            return output

        mission = row.get("v2_mission") or ""

        # 2. Load VALID program verdicts from DB
        verdict_rows = await sql_all(
            "SELECT program_id, program_name, verdict, verdict_confidence, rules_json FROM v2_grant_programs WHERE ein = :ein AND verdict = 'VALID'",
            {"ein": ein},
        )
        if not verdict_rows:
            output = Layer4Output(
                ein=ein, status="error_no_programs",
                error="No VALID programs found for this EIN — run layer2 first",
                processing_ms=_ms(start),
            )
            await write_pipeline_run(ein=ein, layer="layer4", status=output.status,
                                     output_snapshot={"error": output.error},
                                     cost_usd=0.0, duration_ms=output.processing_ms)
            return output

        # Reconstruct verdict objects
        verdicts = _rows_to_verdicts(ein, verdict_rows)

        # 3. Load corpus
        corpus = load_corpus(ein)

        # 4. Per-program extraction
        records: list[GrantProgramRecord] = []
        budget_per_program = LAYER4_BUDGET_USD / max(len(verdicts), 1)
        for verdict in verdicts:
            try:
                record = await extract_program(
                    verdict=verdict,
                    corpus=corpus,
                    org_name=foundation.org_name,
                    ein=ein,
                    run_id=run_id,
                    budget_usd=budget_per_program,
                )
                if record:
                    records.append(record)
            except BudgetExceeded:
                logger.warning(f"[L4] budget exceeded for {ein}; stopping at {len(records)} programs")
                break
            except Exception as e:
                logger.error(f"[L4] extraction error for {verdict.program_name}: {e}")

        # 5. Consolidate
        cost_so_far = get_run_cost(run_id)
        consolidated = await consolidate(
            programs=records,
            org_name=foundation.org_name,
            state=foundation.state,
            mission=mission,
            ein=ein,
            run_id=run_id,
            budget_usd=max(0.10, LAYER4_BUDGET_USD - cost_so_far),
        )

        cost_usd = get_run_cost(run_id)
        output = Layer4Output(
            ein=ein, status="completed",
            programs_written=len(records),
            consolidated_description=consolidated,
            cost_usd=cost_usd, processing_ms=_ms(start),
        )

        await _persist(foundation, records, consolidated)
        await write_pipeline_run(
            ein=ein, layer="layer4", status="completed",
            output_snapshot={"programs_written": len(records), "consolidated_chars": len(consolidated)},
            cost_usd=cost_usd, duration_ms=output.processing_ms,
        )
        return output

    finally:
        clear_run(run_id)


def _ms(start: float) -> int:
    return int((time.monotonic() - start) * 1000)


def _rows_to_verdicts(ein: str, rows: list[dict]) -> list[GrantProgramVerdict]:
    verdicts = []
    for r in rows:
        rules = None
        if r.get("rules_json"):
            try:
                rules_data = json.loads(r["rules_json"])
                default_rule = RuleEvaluation(value=False, confidence=0.0)
                rules = SixRuleResult(
                    has_grants=RuleEvaluation(**rules_data.get("has_grants", {})) if rules_data.get("has_grants") else default_rule,
                    accepts_applications=RuleEvaluation(**rules_data.get("accepts_applications", {})) if rules_data.get("accepts_applications") else default_rule,
                    not_invitation_only=RuleEvaluation(**rules_data.get("not_invitation_only", {})) if rules_data.get("not_invitation_only") else default_rule,
                    not_donation_only=RuleEvaluation(**rules_data.get("not_donation_only", {})) if rules_data.get("not_donation_only") else default_rule,
                    allows_unsolicited=RuleEvaluation(**rules_data.get("allows_unsolicited", {})) if rules_data.get("allows_unsolicited") else default_rule,
                    geography_valid=RuleEvaluation(**rules_data.get("geography_valid", {})) if rules_data.get("geography_valid") else default_rule,
                    active_or_recurring=RuleEvaluation(**rules_data.get("active_or_recurring", {})) if rules_data.get("active_or_recurring") else default_rule,
                )
            except Exception:
                pass
        verdicts.append(GrantProgramVerdict(
            program_id=r["program_id"],
            ein=ein,
            program_name=r["program_name"],
            verdict=r["verdict"],
            verdict_confidence=float(r.get("verdict_confidence") or 0.0),
            rules=rules,
        ))
    return verdicts


async def _persist(
    foundation: FoundationInput,
    records: list[GrantProgramRecord],
    consolidated: str,
) -> None:
    ein = foundation.ein

    # Update each program record in v2_grant_programs
    for rec in records:
        try:
            await sql_exec(
                """
                UPDATE v2_grant_programs SET
                  funding_priorities          = :funding_priorities,
                  types_of_grant              = :types_of_grant,
                  grant_amount_freeform       = :grant_amount_freeform,
                  grant_amount_min_usd        = :grant_amount_min_usd,
                  grant_amount_max_usd        = :grant_amount_max_usd,
                  eligibility_criteria        = :eligibility_criteria,
                  eligible_applicant_types    = :eligible_applicant_types,
                  eligible_geographies        = :eligible_geographies,
                  eligible_focus_areas        = :eligible_focus_areas,
                  proposal_deadline_freeform  = :proposal_deadline_freeform,
                  deadline_type               = :deadline_type,
                  next_deadline_iso           = :next_deadline_iso,
                  is_currently_open           = :is_currently_open,
                  loi_required                = :loi_required,
                  application_method          = :application_method,
                  application_portal_url      = :application_portal_url,
                  application_steps           = :application_steps,
                  required_documents          = :required_documents,
                  is_invitation_only          = :is_invitation_only,
                  accepts_unsolicited         = :accepts_unsolicited,
                  is_recurring                = :is_recurring,
                  is_currently_active         = :is_currently_active,
                  completeness_score          = :completeness_score,
                  extraction_model            = :extraction_model,
                  extraction_prompt_version   = :extraction_prompt_version
                WHERE program_id = :program_id AND ein = :ein
                """,
                {
                    "program_id": rec.program_id,
                    "ein": ein,
                    "funding_priorities": rec.funding_priorities,
                    "types_of_grant": rec.types_of_grant,
                    "grant_amount_freeform": rec.grant_amount_freeform,
                    "grant_amount_min_usd": rec.grant_amount_min_usd,
                    "grant_amount_max_usd": rec.grant_amount_max_usd,
                    "eligibility_criteria": rec.eligibility_criteria,
                    "eligible_applicant_types": json.dumps(rec.eligible_applicant_types),
                    "eligible_geographies": json.dumps(rec.eligible_geographies),
                    "eligible_focus_areas": json.dumps(rec.eligible_focus_areas),
                    "proposal_deadline_freeform": rec.proposal_deadline_freeform,
                    "deadline_type": rec.deadline_type,
                    "next_deadline_iso": rec.next_deadline_iso,
                    "is_currently_open": rec.is_currently_open,
                    "loi_required": rec.loi_required,
                    "application_method": json.dumps(rec.application_method),
                    "application_portal_url": rec.application_portal_url,
                    "application_steps": json.dumps(rec.application_steps),
                    "required_documents": json.dumps(rec.required_documents),
                    "is_invitation_only": rec.is_invitation_only,
                    "accepts_unsolicited": rec.accepts_unsolicited,
                    "is_recurring": rec.is_recurring,
                    "is_currently_active": rec.is_currently_active,
                    "completeness_score": rec.completeness_score,
                    "extraction_model": rec.extraction_model,
                    "extraction_prompt_version": rec.extraction_prompt_version,
                },
            )
        except Exception as e:
            logger.error(f"[L4] persist program {rec.program_id} failed: {e}")

    # Update consolidated description on foundations row
    try:
        await sql_exec(
            """
            UPDATE foundations SET
              v2_layer4_consolidated_description = :consolidated,
              v2_layer4_status                   = 'completed',
              v2_layer4_processed_at             = NOW(),
              v2_pipeline_status                 = 'layer4_done'
            WHERE ein = :ein
            """,
            {"ein": ein, "consolidated": consolidated},
        )
    except Exception as e:
        logger.error(f"[L4] persist consolidated description failed for {ein}: {e}")
