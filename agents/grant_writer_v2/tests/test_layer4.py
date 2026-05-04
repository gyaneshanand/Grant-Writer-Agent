"""Tests for Layer 4 grant writer."""
import pytest
from unittest.mock import AsyncMock, patch

from agents.grant_writer_v2.layer5_metadata_seo.slug_generator import generate_slug
from agents.grant_writer_v2.layer5_metadata_seo.filter_deriver import derive_filters


def test_slug_generation():
    slug = generate_slug("The Akindale Foundation", "Community Arts Grant", "237421854")
    assert "akindale" in slug
    assert "community-arts-grant" in slug
    assert len(slug) <= 120


def test_slug_special_chars():
    slug = generate_slug("O'Brien & Sons Foundation", "Health & Wellness Grant", "123456789")
    assert "&" not in slug
    assert "'" not in slug


@pytest.mark.asyncio
async def test_pipeline_no_layer2(akindale_foundation):
    from agents.grant_writer_v2.layer4_grant_writer.pipeline import run
    with patch("agents.grant_writer_v2.layer4_grant_writer.pipeline.sql_one",
               new_callable=AsyncMock, return_value=None), \
         patch("agents.grant_writer_v2.layer4_grant_writer.pipeline.write_pipeline_run",
               new_callable=AsyncMock):
        output = await run(akindale_foundation)
    assert output.status == "error_no_layer2"
