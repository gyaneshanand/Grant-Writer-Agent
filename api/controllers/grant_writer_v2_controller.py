"""Grant Writer v2 API controller — 3 endpoints."""
import json
from fastapi import APIRouter, HTTPException

from api.models.grant_writer_v2_schemas import (
    LayerRunRequest, LayerRunResponse,
    PipelineRunRequest, PipelineRunResponse,
    V2PipelineResponse, V2GrantData, V2OrganizationData, V2Metadata,
)
from api.services.grant_writer_v2_service import run_single_layer, run_full_pipeline
from agents.grant_writer_v2.core.db import sql_one, sql_all

router = APIRouter(prefix="/grant-writer-v2", tags=["Grant Writer v2"])


def _safe_json(val):
    """Parse a JSON DB value or return the value as-is if already parsed."""
    if val is None:
        return None
    if isinstance(val, (list, dict)):
        return val
    try:
        return json.loads(val)
    except Exception:
        return val


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


@router.get("/result/{ein}", response_model=V2PipelineResponse)
async def get_result(ein: str):
    """
    Return the full pipeline result for a completed EIN in a format that is
    backward-compatible with the v1 PipelineResponse shape, plus all v2 fields.

    Laravel reads this after the pipeline finishes to get:
      - grants_data  (list of per-program structured data)
      - organization_data  (org profile)
      - consolidated_description  (11-section Markdown)
      - metadata  (SEO fields from L5)
    """
    # Load foundations row
    found = await sql_one(
        """SELECT ein, v2_pipeline_status, v2_layer1_status, v2_layer1_url,
                  v2_layer2_rollup_verdict, v2_layer2_program_count, v2_layer2_valid_program_count,
                  v2_legal_name, v2_mission, v2_about, v2_foundation_type,
                  v2_focus_areas, v2_geography_served, v2_annual_giving_usd, v2_total_assets_usd,
                  v2_contact, v2_layer4_consolidated_description, name
           FROM foundations WHERE ein = :ein""",
        {"ein": ein},
    )
    if not found:
        raise HTTPException(status_code=404, detail=f"No pipeline data found for EIN {ein}")

    f = dict(found)

    # ── Organization data ─────────────────────────────────────────────────────
    contact_raw = _safe_json(f.get("v2_contact")) or {}
    org_data = V2OrganizationData(
        org_name=f.get("v2_legal_name") or f.get("name") or ein,
        mission=f.get("v2_mission"),
        background=f.get("v2_about"),
        about=f.get("v2_about"),
        contact=contact_raw if contact_raw else None,
        legal_name=f.get("v2_legal_name"),
        foundation_type=f.get("v2_foundation_type"),
        focus_areas=_safe_json(f.get("v2_focus_areas")) or [],
        geography_served=_safe_json(f.get("v2_geography_served")) or None,
        annual_giving_usd=f.get("v2_annual_giving_usd"),
        total_assets_usd=f.get("v2_total_assets_usd"),
        foundation_url=f.get("v2_layer1_url"),
    )

    # ── Per-program data ──────────────────────────────────────────────────────
    prog_rows = await sql_all(
        """SELECT program_id, program_name, verdict, slug AS program_slug,
                  funding_priorities, types_of_grant, eligibility_criteria,
                  eligible_applicants_freeform, eligible_locations_freeform,
                  grant_amount_freeform, grant_amount_min_usd, grant_amount_max_usd,
                  grant_amount_typical_usd, proposal_deadline_freeform, deadline_type,
                  next_deadline_iso, is_currently_open, loi_required, accepts_unsolicited,
                  is_recurring, is_invitation_only, eligible_geographies, eligible_focus_areas,
                  eligible_applicant_types, application_method, application_portal_url,
                  application_steps, required_documents, excluded_uses,
                  opportunity_title, h1_tag, meta_title, meta_description,
                  opportunity_teaser, opportunity_title_for_subscriber, search_blob, program_url
           FROM v2_grant_programs WHERE ein = :ein ORDER BY verdict ASC""",
        {"ein": ein},
    )

    grants_data: list[V2GrantData] = []
    # Pick metadata from first VALID program for the top-level metadata field
    first_valid: dict = {}

    for _r in prog_rows:
        r = dict(_r)
        if r.get("verdict") == "VALID" and not first_valid:
            first_valid = r

        contact_info = {"email": "Not specified", "phone": "Not specified", "address": "Not specified"}
        if contact_raw:
            contact_info = {
                "email": contact_raw.get("email") or "Not specified",
                "phone": contact_raw.get("phone") or "Not specified",
                "address": " ".join(filter(None, [
                    contact_raw.get("address", ""),
                    contact_raw.get("address_city", ""),
                    contact_raw.get("address_state", ""),
                    contact_raw.get("address_zip", ""),
                ])) or "Not specified",
            }

        grants_data.append(V2GrantData(
            # v1 backward-compatible fields
            grant_name=r.get("program_name") or "Not specified",
            funding_priorities=r.get("funding_priorities") or "Not specified",
            types_of_grant=r.get("types_of_grant") or "Not specified",
            eligibility_criteria=r.get("eligibility_criteria") or "Not specified",
            eligible_applicants=_safe_json(r.get("eligible_applicant_types")) or [],
            eligible_locations=r.get("eligible_locations_freeform") or "Not specified",
            grant_amount_range=r.get("grant_amount_freeform") or "Not specified",
            grant_amount=r.get("grant_amount_freeform") or "Not specified",
            proposal_deadline=r.get("proposal_deadline_freeform") or "Not specified",
            recurrence="Recurring" if r.get("is_recurring") else "Not specified",
            contact_info=contact_info,
            organization_info=f.get("v2_mission") or "Not specified",
            grant_summary=r.get("opportunity_title") or r.get("program_name") or "Not specified",
            grant_url=r.get("program_url") or r.get("application_portal_url") or f.get("v2_layer1_url") or "Not specified",
            # v2 extra fields
            program_id=r.get("program_id"),
            verdict=r.get("verdict"),
            grant_amount_min_usd=r.get("grant_amount_min_usd"),
            grant_amount_max_usd=r.get("grant_amount_max_usd"),
            grant_amount_typical_usd=r.get("grant_amount_typical_usd"),
            deadline_type=r.get("deadline_type"),
            next_deadline_iso=str(r["next_deadline_iso"]) if r.get("next_deadline_iso") else None,
            is_currently_open=bool(r["is_currently_open"]) if r.get("is_currently_open") is not None else None,
            loi_required=bool(r["loi_required"]) if r.get("loi_required") is not None else None,
            accepts_unsolicited=bool(r["accepts_unsolicited"]) if r.get("accepts_unsolicited") is not None else None,
            is_recurring=bool(r["is_recurring"]) if r.get("is_recurring") is not None else None,
            is_invitation_only=bool(r["is_invitation_only"]) if r.get("is_invitation_only") is not None else None,
            eligible_geographies=_safe_json(r.get("eligible_geographies")) or [],
            eligible_focus_areas=_safe_json(r.get("eligible_focus_areas")) or [],
            eligible_applicant_types=_safe_json(r.get("eligible_applicant_types")) or [],
            application_method=_safe_json(r.get("application_method")) or [],
            application_portal_url=r.get("application_portal_url"),
            application_steps=_safe_json(r.get("application_steps")) or [],
            required_documents=_safe_json(r.get("required_documents")) or [],
            excluded_uses=_safe_json(r.get("excluded_uses")) or [],
            # SEO fields
            program_slug=r.get("program_slug"),
            opportunity_title=r.get("opportunity_title"),
            h1_tag=r.get("h1_tag"),
            meta_title=r.get("meta_title"),
            meta_description=r.get("meta_description"),
            opportunity_teaser=r.get("opportunity_teaser"),
            opportunity_title_for_subscriber=r.get("opportunity_title_for_subscriber"),
            search_blob=r.get("search_blob"),
        ))

    # ── Metadata (from first VALID program, matches v1 MetadataWriterResponse) ─
    metadata = V2Metadata(
        opportunity_title=first_valid.get("opportunity_title") or "Not specified",
        h1_tag=first_valid.get("h1_tag") or "Not specified",
        meta_title=first_valid.get("meta_title") or "Not specified",
        meta_description=first_valid.get("meta_description") or "Not specified",
        opportunity_teaser=first_valid.get("opportunity_teaser") or "Not specified",
        opportunity_title_for_subscriber=first_valid.get("opportunity_title_for_subscriber") or "Not specified",
    )

    return V2PipelineResponse(
        # v1 backward-compatible
        grants_data=grants_data,
        organization_data=org_data,
        consolidated_description=f.get("v2_layer4_consolidated_description") or "",
        metadata=metadata,
        # v2 pipeline status
        ein=ein,
        pipeline_status=f.get("v2_pipeline_status"),
        layer1_status=f.get("v2_layer1_status"),
        layer2_rollup_verdict=f.get("v2_layer2_rollup_verdict"),
        layer2_program_count=f.get("v2_layer2_program_count") or 0,
        layer2_valid_program_count=f.get("v2_layer2_valid_program_count") or 0,
        foundation_url=f.get("v2_layer1_url"),
    )
