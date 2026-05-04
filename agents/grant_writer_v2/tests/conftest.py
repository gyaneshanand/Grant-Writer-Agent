"""
Shared pytest fixtures for grant_writer_v2 tests.
"""
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from agents.grant_writer_v2.schemas.common import FoundationInput


@pytest.fixture
def akindale_foundation():
    return FoundationInput(
        org_name="The Akindale Foundation",
        ein="237421854",
        state="NY",
        city="New York",
    )


@pytest.fixture
def albatross_foundation():
    return FoundationInput(
        org_name="Albatross Family Foundation",
        ein="123456789",
        state="CA",
    )


@pytest.fixture
def stahmer_foundation():
    return FoundationInput(
        org_name="Stahmer Family Foundation",
        ein="987654321",
        state="TX",
        city="Houston",
    )


@pytest.fixture
def mock_serp_response_akindale():
    """Realistic SerpAPI response fixture for Akindale Foundation."""
    return {
        "search_information": {"total_results": "1,230"},
        "knowledge_graph": {
            "title": "The Akindale Foundation",
            "website": "https://www.akindaleFoundation.org",
        },
        "organic_results": [
            {
                "position": 1,
                "title": "The Akindale Foundation — Grants for NY Nonprofits",
                "link": "https://www.akindaleFoundation.org",
                "snippet": "The Akindale Foundation supports nonprofit organizations in New York State.",
            },
            {
                "position": 2,
                "title": "Akindale Foundation | Candid",
                "link": "https://candid.org/akindale-foundation",
                "snippet": "Grants from The Akindale Foundation.",
            },
        ],
    }


@pytest.fixture
def mock_serp_response_no_results():
    return {"search_information": {"total_results": "0"}, "organic_results": []}


@pytest.fixture
def mock_openai_chat_response():
    """Mock OpenAI ChatCompletion response."""
    choice = MagicMock()
    choice.message.content = json.dumps({"index": 0, "reasoning": "Best match"})
    resp = MagicMock()
    resp.choices = [choice]
    resp.model = "openai/gpt-4o-mini"
    resp.usage.prompt_tokens = 100
    resp.usage.completion_tokens = 50
    return resp


@pytest.fixture
def mock_db_no_layer1():
    """DB row indicating L1 has not run."""
    return None


@pytest.fixture
def mock_db_layer1_done():
    """DB row with L1 completed and URL set."""
    return {
        "v2_layer1_url": "https://www.akindaleFoundation.org",
        "v2_layer1_status": "accepted_verifier",
        "v2_layer2_status": None,
    }
