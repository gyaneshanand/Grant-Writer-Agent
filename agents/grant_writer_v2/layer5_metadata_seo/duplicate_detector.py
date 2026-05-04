"""
Duplicate detection for Layer 5.
Uses MinHash similarity over the search_blob to detect near-duplicate programs.
Requires: datasketch
"""
from typing import Optional

from agents.grant_writer_v2.core.logger import get_logger

logger = get_logger("layer5.dedup")

SIMILARITY_THRESHOLD = 0.85
NUM_PERM = 128


def _shingles(text: str, k: int = 3) -> set[str]:
    text = text.lower()
    return {text[i:i+k] for i in range(len(text) - k + 1)} if len(text) >= k else {text}


def _minhash(text: str):
    try:
        from datasketch import MinHash
        m = MinHash(num_perm=NUM_PERM)
        for s in _shingles(text):
            m.update(s.encode("utf-8"))
        return m
    except ImportError:
        return None


def find_duplicate(
    program_id: str,
    search_blob: str,
    existing: list[dict],  # list of {program_id, search_blob}
) -> Optional[str]:
    """
    Returns the program_id of a near-duplicate in `existing`, or None.
    Falls back to None if datasketch is not installed.
    """
    if not search_blob or not existing:
        return None

    m1 = _minhash(search_blob)
    if m1 is None:
        return None

    for other in existing:
        if other["program_id"] == program_id:
            continue
        m2 = _minhash(other.get("search_blob", ""))
        if m2 is None:
            continue
        try:
            if m1.jaccard(m2) >= SIMILARITY_THRESHOLD:
                return other["program_id"]
        except Exception:
            pass
    return None


def build_search_blob(program_row: dict) -> str:
    """Build a flat text blob from structured fields for full-text indexing + dedup."""
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

    parts = [
        program_row.get("program_name", ""),
        program_row.get("funding_priorities", ""),
        program_row.get("types_of_grant", ""),
        program_row.get("eligibility_criteria", ""),
        program_row.get("eligible_applicants_freeform", ""),
        program_row.get("eligible_locations_freeform", ""),
        " ".join(_safe_json(program_row.get("eligible_focus_areas"))),
        " ".join(_safe_json(program_row.get("eligible_geographies"))),
        program_row.get("proposal_deadline_freeform", ""),
        program_row.get("grant_amount_freeform", ""),
        program_row.get("opportunity_title", ""),
        program_row.get("meta_description", ""),
    ]
    return " ".join(p for p in parts if p).lower()
