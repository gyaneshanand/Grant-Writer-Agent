"""Tests for Layer 2 — including cost cap / runaway-agent fixture."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from agents.grant_writer_v2.layer2_grant_detection.pipeline import run
from agents.grant_writer_v2.layer2_grant_detection.verdict_aggregator import aggregate
from agents.grant_writer_v2.schemas.common import RuleEvaluation
from agents.grant_writer_v2.schemas.grant_program import GrantProgramVerdict, SixRuleResult


# ── Verdict aggregator unit tests ─────────────────────────────────────────────

def _make_verdict(verdict: str) -> GrantProgramVerdict:
    rule = RuleEvaluation(value=verdict == "VALID", confidence=0.9)
    rules = SixRuleResult(
        has_grants=rule, accepts_applications=rule, not_invitation_only=rule,
        not_donation_only=rule, allows_unsolicited=rule, geography_valid=rule,
        active_or_recurring=rule,
    )
    return GrantProgramVerdict(
        program_id="test_id",
        ein="123456789",
        program_name="Test Program",
        verdict=verdict,
        rules=rules,
    )


def test_aggregate_valid():
    verdicts = [_make_verdict("VALID"), _make_verdict("INVALID")]
    rollup, valid, total = aggregate(verdicts)
    assert rollup == "VALID"
    assert valid == 1
    assert total == 2


def test_aggregate_needs_review():
    verdicts = [_make_verdict("NEEDS_REVIEW"), _make_verdict("INVALID")]
    rollup, valid, total = aggregate(verdicts)
    assert rollup == "NEEDS_REVIEW"
    assert valid == 0


def test_aggregate_invalid():
    verdicts = [_make_verdict("INVALID")]
    rollup, valid, total = aggregate(verdicts)
    assert rollup == "INVALID"


def test_aggregate_empty():
    rollup, valid, total = aggregate([])
    assert rollup == "INVALID"
    assert total == 0


# ── SixRuleResult.all_pass ────────────────────────────────────────────────────

def test_all_pass_true():
    rule = RuleEvaluation(value=True, confidence=0.9)
    rules = SixRuleResult(
        has_grants=rule, accepts_applications=rule, not_invitation_only=rule,
        not_donation_only=rule, allows_unsolicited=rule, geography_valid=rule,
        active_or_recurring=rule,
    )
    assert rules.all_pass(0.6) is True


def test_all_pass_low_confidence():
    rule_ok = RuleEvaluation(value=True, confidence=0.9)
    rule_low = RuleEvaluation(value=True, confidence=0.3)
    rules = SixRuleResult(
        has_grants=rule_ok, accepts_applications=rule_ok, not_invitation_only=rule_ok,
        not_donation_only=rule_ok, allows_unsolicited=rule_ok, geography_valid=rule_ok,
        active_or_recurring=rule_low,
    )
    assert rules.all_pass(0.6) is False


def test_any_fail_hard():
    rule_ok = RuleEvaluation(value=True, confidence=0.9)
    rule_fail = RuleEvaluation(value=False, confidence=0.95)
    rules = SixRuleResult(
        has_grants=rule_fail, accepts_applications=rule_ok, not_invitation_only=rule_ok,
        not_donation_only=rule_ok, allows_unsolicited=rule_ok, geography_valid=rule_ok,
        active_or_recurring=rule_ok,
    )
    assert rules.any_fail_hard(0.8) is True


# ── Pipeline: missing prereq ──────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_pipeline_no_layer1(akindale_foundation):
    with patch("agents.grant_writer_v2.layer2_grant_detection.pipeline.sql_one",
               new_callable=AsyncMock, return_value=None), \
         patch("agents.grant_writer_v2.layer2_grant_detection.pipeline.write_pipeline_run",
               new_callable=AsyncMock):
        output = await run(akindale_foundation)
    assert output.status == "error_no_url"
    assert "prerequisite_missing" in (output.error or "")


# ── Runaway agent cap test ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_pipeline_respects_iteration_cap(akindale_foundation):
    """
    The graph must stop within V2_L2_MAX_ITERATIONS even if the LLM always
    wants to call another tool.
    """
    from agents.grant_writer_v2.config import v2_settings

    # Mock DB to return a layer1 URL
    layer1_row = {"v2_layer1_url": "https://www.example.org", "v2_layer1_status": "accepted_verifier"}

    # Mock the LLM to always return a tool_call (runaway agent)
    tool_call_msg = MagicMock()
    tool_call_msg.tool_calls = [MagicMock(id="call_1", function=MagicMock(name="fetch_page", arguments='{"url":"https://www.example.org"}'))]

    runaway_llm = MagicMock()
    runaway_llm.bind_tools.return_value = runaway_llm
    runaway_llm.invoke.return_value = tool_call_msg

    # Mock fetch_page to return something minimal
    tool_result = MagicMock()
    tool_result.content = "Some page content"

    with patch("agents.grant_writer_v2.layer2_grant_detection.pipeline.sql_one",
               new_callable=AsyncMock, return_value=layer1_row), \
         patch("agents.grant_writer_v2.layer2_grant_detection.pipeline.sql_exec",
               new_callable=AsyncMock), \
         patch("agents.grant_writer_v2.layer2_grant_detection.pipeline.sql_exec_many",
               new_callable=AsyncMock), \
         patch("agents.grant_writer_v2.layer2_grant_detection.pipeline.write_pipeline_run",
               new_callable=AsyncMock), \
         patch("agents.grant_writer_v2.layer2_grant_detection.pipeline.save_corpus"), \
         patch("agents.grant_writer_v2.layer2_grant_detection.graph.get_chat_model",
               return_value=runaway_llm), \
         patch("agents.grant_writer_v2.layer2_grant_detection.program_identifier.identify_programs",
               new_callable=AsyncMock, return_value=[]):
        output = await run(akindale_foundation)

    # Must terminate — not hang
    assert output is not None
    assert output.stop_reason in (
        "max_iterations", "max_pages", "max_bytes", "max_cost", "completed", "error"
    )
