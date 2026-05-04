"""
Pure Python rollup: list[GrantProgramVerdict] → foundation-level rollup verdict.
No LLM, no IO.
"""
from agents.grant_writer_v2.schemas.grant_program import GrantProgramVerdict


def aggregate(verdicts: list[GrantProgramVerdict]) -> tuple[str, int, int]:
    """
    Returns (rollup_verdict, valid_count, total_count).
    rollup_verdict: "VALID" | "INVALID" | "NEEDS_REVIEW"

    Logic (per Rules_Reference):
    - If ≥1 program is VALID → VALID
    - Else if ≥1 program is NEEDS_REVIEW → NEEDS_REVIEW
    - Else → INVALID
    """
    if not verdicts:
        return "INVALID", 0, 0

    total = len(verdicts)
    valid = sum(1 for v in verdicts if v.verdict == "VALID")
    needs_review = sum(1 for v in verdicts if v.verdict == "NEEDS_REVIEW")

    if valid > 0:
        return "VALID", valid, total
    if needs_review > 0:
        return "NEEDS_REVIEW", 0, total
    return "INVALID", 0, total
