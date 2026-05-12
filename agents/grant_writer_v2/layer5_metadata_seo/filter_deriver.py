"""
Deterministic filter field derivation for Layer 5.
Maps structured L4 fields → filter/facet values for the search UI.
"""
from agents.grant_writer_v2.core.vocab import bucket_funding_amount


def derive_filters(program_row: dict) -> dict:
    """
    Input: one row from v2_grant_programs (as dict).
    Returns dict of filter fields ready to write back to the row.
    """
    import json

    def _safe_json(val):
        if not val:
            return []
        if isinstance(val, list):
            return val
        try:
            return json.loads(val)
        except Exception:
            return []

    focus_areas = _safe_json(program_row.get("eligible_focus_areas"))
    applicant_types = _safe_json(program_row.get("eligible_applicant_types"))
    geographies = _safe_json(program_row.get("eligible_geographies"))

    min_usd = program_row.get("grant_amount_min_usd")
    max_usd = program_row.get("grant_amount_max_usd")
    typical_usd = program_row.get("grant_amount_typical_usd")

    # Use typical if min/max missing
    amount_for_bucket = typical_usd or max_usd or min_usd
    funding_bucket = bucket_funding_amount(
        min_usd=float(min_usd) if min_usd is not None else None,
        max_usd=float(max_usd) if max_usd is not None else None,
    ) if (min_usd is not None or max_usd is not None) else "unspecified"

    # Geographic scope
    geo_scope = "us_only"
    if geographies:
        upper = [g.upper() for g in geographies]
        if "INTL" in upper or "INTERNATIONAL" in upper:
            geo_scope = "international"
        elif any(g not in _US_STATE_CODES and g not in ("US", "PR", "GU", "VI", "AS", "MP") for g in upper):
            geo_scope = "international"

    # is_currently_open: if explicitly False → closed; if True → open;
    # if None/unknown but deadline_type is rolling/not_specified → treat as open (None = unknown)
    raw_open = program_row.get("is_currently_open")
    deadline_type = program_row.get("deadline_type") or "not_specified"
    if raw_open is True:
        filter_is_open = True
    elif raw_open is False:
        filter_is_open = False
    elif deadline_type in ("rolling", "not_specified", "ongoing"):
        filter_is_open = True
    else:
        filter_is_open = None

    return {
        "filter_focus_areas": json.dumps(focus_areas),
        "filter_applicant_types": json.dumps(applicant_types),
        "filter_geographies": json.dumps(geographies),
        "filter_funding_bucket": funding_bucket,
        "filter_deadline_type": deadline_type,
        "filter_is_open": filter_is_open,
        "filter_accepts_unsolicited": bool(program_row.get("accepts_unsolicited", True)),
        "filter_loi_required": bool(program_row.get("loi_required")),
        "filter_geo_scope": geo_scope,
    }


_US_STATE_CODES = {
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA", "HI", "ID",
    "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD", "MA", "MI", "MN", "MS",
    "MO", "MT", "NE", "NV", "NH", "NJ", "NM", "NY", "NC", "ND", "OH", "OK",
    "OR", "PA", "RI", "SC", "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV",
    "WI", "WY", "DC",
}
