"""Tests for Layer 3 org extraction."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.mark.asyncio
async def test_pipeline_no_layer2(akindale_foundation):
    from agents.grant_writer_v2.layer3_org_extraction.pipeline import run
    with patch("agents.grant_writer_v2.layer3_org_extraction.pipeline.sql_one",
               new_callable=AsyncMock, return_value=None), \
         patch("agents.grant_writer_v2.layer3_org_extraction.pipeline.write_pipeline_run",
               new_callable=AsyncMock):
        output = await run(akindale_foundation)
    assert output.status == "error_no_layer2"


@pytest.mark.asyncio
async def test_pipeline_no_corpus(akindale_foundation):
    from agents.grant_writer_v2.layer3_org_extraction.pipeline import run
    layer2_row = {"v2_layer2_status": "completed", "v2_layer1_url": "https://example.org"}
    with patch("agents.grant_writer_v2.layer3_org_extraction.pipeline.sql_one",
               new_callable=AsyncMock, return_value=layer2_row), \
         patch("agents.grant_writer_v2.layer3_org_extraction.pipeline.load_corpus",
               return_value=[]), \
         patch("agents.grant_writer_v2.layer3_org_extraction.pipeline.write_pipeline_run",
               new_callable=AsyncMock):
        output = await run(akindale_foundation)
    assert output.status == "error_no_corpus"
