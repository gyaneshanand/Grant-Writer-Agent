"""
End-to-end integration tests — skipped by default (require live DB + API keys).
Run with: pytest -m integration
"""
import pytest


@pytest.mark.integration
@pytest.mark.asyncio
async def test_full_pipeline_akindale(akindale_foundation):
    """Full L1-L5 pipeline for The Akindale Foundation (NY)."""
    from agents.grant_writer_v2.orchestrator import run_pipeline
    result = await run_pipeline(akindale_foundation, start_layer=1, end_layer=5)
    assert "layers_run" in result
    assert 1 in result["layers_run"]
    # L1 must accept a URL
    l1_output = result["outputs"].get(1, {})
    assert l1_output.get("url") is not None


@pytest.mark.integration
@pytest.mark.asyncio
async def test_layer_independence_akindale(akindale_foundation):
    """L2 can be called independently if L1 has already run."""
    from agents.grant_writer_v2.orchestrator import run_layer
    # Assumes L1 has already run for this EIN in the test DB
    result = await run_layer(2, akindale_foundation)
    assert result.get("status") in (
        "completed", "rejected_no_programs", "needs_review", "error_no_url"
    )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_missing_prereq_409(stahmer_foundation):
    """L3 on a fresh foundation should return error_no_layer2."""
    from agents.grant_writer_v2.layer3_org_extraction.pipeline import run
    output = await run(stahmer_foundation)
    assert output.status in ("error_no_layer2", "error_no_corpus")
