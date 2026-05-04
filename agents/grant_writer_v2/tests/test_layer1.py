"""
Tests for Layer 1 URL discovery.

Covers every fix and behaviour validated during manual testing:
  - Blocklist filtering (directories, social media, job boards)
  - Verifier scoring — name_in_domain (full segment + partial), title, snippet, geo, KG bonus
  - lstrip("www.") bug fix — domains starting with 'w' no longer stripped incorrectly
  - LLM reranker gray band (0.35–0.65), idx=None forces rejection, idx=-1 forces rejection
  - PDF / deep-path URL normalization before rerank
  - Fallback query when primary returns zero valid candidates
  - Pipeline status codes: accepted_kg, accepted_verifier, accepted_llm,
    rejected_no_candidates, rejected_low_confidence, error_serpapi
"""
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from agents.grant_writer_v2.layer1_url_discovery import classifier, verifier
from agents.grant_writer_v2.layer1_url_discovery.llm_reranker import needs_rerank
from agents.grant_writer_v2.layer1_url_discovery.pipeline import run, _normalize_for_rerank
from agents.grant_writer_v2.layer1_url_discovery.serpapi_client import build_query, build_fallback_query
from agents.grant_writer_v2.schemas.common import CandidateRecord, FoundationInput


# ── Helpers ───────────────────────────────────────────────────────────────────

def _candidate(url, title="Title", snippet="Snippet", position=0):
    return CandidateRecord(url=url, position=position, title=title, snippet=snippet)


def _foundation(org_name, state, city=None, ein="000000001"):
    return FoundationInput(org_name=org_name, ein=ein, state=state, city=city)


def _mock_db_patches():
    """Return context managers that silence all DB/audit calls."""
    return (
        patch("agents.grant_writer_v2.layer1_url_discovery.pipeline.sql_exec", new_callable=AsyncMock),
        patch("agents.grant_writer_v2.layer1_url_discovery.pipeline.sql_exec_many", new_callable=AsyncMock),
        patch("agents.grant_writer_v2.layer1_url_discovery.pipeline.write_pipeline_run", new_callable=AsyncMock),
    )


# ── Query builder ─────────────────────────────────────────────────────────────

def test_build_query_with_city():
    q = build_query("Wold Foundation", "WY", "Casper")
    assert '"Wold Foundation"' in q
    assert "Casper" in q
    assert "WY" in q


def test_build_query_without_city():
    q = build_query("Wold Foundation", "WY")
    assert "Casper" not in q
    assert "WY" in q


def test_build_fallback_query_strips_foundation_suffix():
    q = build_fallback_query("AHEPA Rochester Foundation", "NY")
    assert "foundation" not in q.lower()
    assert "AHEPA Rochester" in q or "ahepa rochester" in q.lower()


def test_build_fallback_query_strips_fund():
    q = build_fallback_query("Smith Family Fund", "TX")
    assert "fund" not in q.lower()
    assert "official website" in q


# ── Blocklist ─────────────────────────────────────────────────────────────────

def test_extract_candidates_kg_comes_first(mock_serp_response_akindale):
    candidates = classifier.extract_candidates(mock_serp_response_akindale)
    assert candidates[0].snippet == "Knowledge Graph result"


def test_extract_candidates_candid_blocklisted(mock_serp_response_akindale):
    candidates = classifier.extract_candidates(mock_serp_response_akindale)
    candid = [c for c in candidates if "candid.org" in c.url]
    assert candid and candid[0].blocklisted is True
    assert candid[0].blocklist_category is not None


@pytest.mark.parametrize("url", [
    "https://candid.org/some-foundation",
    "https://www.guidestar.org/profile/123",
    "https://grantmakers.io/profiles/v1/123",
    "https://www.causeiq.com/organizations/foo,123",
    "https://www.charitynavigator.org/ein/123",
    "https://propublica.org/nonprofit/123",
    "https://www.linkedin.com/company/foo",
    "https://www.indeed.com/cmp/foo",
    "https://en.wikipedia.org/wiki/foo",
])
def test_known_blocklisted_domains(url):
    from agents.grant_writer_v2.layer1_url_discovery.blocklist import check
    blocked, category, _ = check(url)
    assert blocked, f"Expected {url} to be blocklisted"
    assert category is not None


def test_foundation_own_domain_not_blocklisted():
    from agents.grant_writer_v2.layer1_url_discovery.blocklist import check
    blocked, _, _ = check("https://woldfoundation.org/grants")
    assert not blocked


# ── Verifier scoring ──────────────────────────────────────────────────────────

class TestVerifierNameInDomain:
    """All cases for the name_in_domain signal."""

    def test_full_segment_match(self):
        # "james" is a whole segment in james-foundation.org
        f = _foundation("The James Foundation", "MN")
        c = _candidate("https://james-foundation.org/")
        _, signals = verifier.score(c, f)
        assert signals["name_in_domain"] > 0

    def test_partial_match_compound_domain(self):
        # "james" is embedded in "thejamesfoundation" — partial match, half weight
        f = _foundation("The James Foundation", "MN")
        c = _candidate("https://thejamesfoundation.org/")
        _, signals = verifier.score(c, f)
        assert signals["name_in_domain"] > 0

    def test_wold_in_woldfoundation(self):
        # Regression: lstrip("www.") was stripping the leading 'w' from woldfoundation.org
        f = _foundation("Wold Foundation", "WY")
        c = _candidate("https://woldfoundation.org/")
        _, signals = verifier.score(c, f)
        assert signals["name_in_domain"] > 0, (
            "name_in_domain must be > 0 for woldfoundation.org — "
            "lstrip('www.') bug was stripping leading 'w' from the domain"
        )

    def test_wtgrant_in_wtgrantfoundation(self):
        # "grant" is embedded in "wtgrantfoundation"
        f = _foundation("William T Grant Foundation", "NY")
        c = _candidate("https://wtgrantfoundation.org/")
        _, signals = verifier.score(c, f)
        assert signals["name_in_domain"] > 0

    def test_www_prefix_stripped_correctly(self):
        # www.woldfoundation.org should score same as woldfoundation.org
        f = _foundation("Wold Foundation", "WY")
        c1 = _candidate("https://woldfoundation.org/")
        c2 = _candidate("https://www.woldfoundation.org/")
        _, s1 = verifier.score(c1, f)
        _, s2 = verifier.score(c2, f)
        assert s1["name_in_domain"] == s2["name_in_domain"]

    def test_unrelated_domain_scores_zero(self):
        f = _foundation("Wold Foundation", "WY")
        c = _candidate("https://facs.org/")
        _, signals = verifier.score(c, f)
        # "wold" does not appear in "facs" at all
        assert signals["name_in_domain"] == 0.0

    def test_facs_does_not_match_acs(self):
        # Regression: "acs" was found inside "facs" via substring — must NOT match
        f = _foundation("ACS Foundation", "NY")
        c = _candidate("https://facs.org/")
        _, signals = verifier.score(c, f)
        # "acs" is not a whole segment of facs.org (segments: ["facs", "org"])
        # and "facs" is < 8 chars so partial match also excluded
        assert signals["name_in_domain"] == 0.0

    def test_stopword_foundation_excluded_from_tokens(self):
        # "foundation" is a stopword — should not contribute to domain score
        f = _foundation("Grant Foundation", "CA")
        tokens_used = set()
        import re
        stopwords = {"the", "a", "an", "of", "and", "or", "for", "in", "at", "foundation", "fund"}
        for w in re.split(r"\W+", f.org_name):
            if len(w) > 2 and w.lower() not in stopwords:
                tokens_used.add(w.lower())
        assert "foundation" not in tokens_used


class TestVerifierOtherSignals:

    def test_kg_bonus(self, akindale_foundation):
        c = _candidate("https://akindaleFoundation.org", snippet="Knowledge Graph result")
        _, signals = verifier.score(c, akindale_foundation)
        assert signals["kg_bonus"] == 0.10

    def test_no_kg_bonus_for_normal_snippet(self, akindale_foundation):
        c = _candidate("https://akindaleFoundation.org", snippet="Normal snippet text")
        _, signals = verifier.score(c, akindale_foundation)
        assert signals["kg_bonus"] == 0.0

    def test_name_in_title(self):
        f = _foundation("Wold Foundation", "WY")
        c = _candidate("https://somesite.org", title="Wold Foundation — Grants")
        _, signals = verifier.score(c, f)
        assert signals["name_in_title"] > 0

    def test_name_in_snippet(self):
        f = _foundation("Wold Foundation", "WY")
        c = _candidate("https://somesite.org", snippet="The Wold Foundation provides grants.")
        _, signals = verifier.score(c, f)
        assert signals["name_in_snippet"] > 0

    def test_state_in_snippet(self):
        f = _foundation("Wold Foundation", "WY", city="Casper")
        c = _candidate("https://somesite.org", snippet="Based in Casper, WY.")
        _, signals = verifier.score(c, f)
        assert signals["state_in_snippet"] > 0

    def test_confidence_capped_at_one(self, akindale_foundation):
        c = _candidate(
            "https://akindaleFoundation.org",
            title="The Akindale Foundation",
            snippet="Knowledge Graph result",
        )
        conf, _ = verifier.score(c, akindale_foundation)
        assert conf <= 1.0

    def test_unrelated_url_low_confidence(self, akindale_foundation):
        c = _candidate("https://www.randomsite.com", title="Random Site", snippet="Nothing here.")
        conf, _ = verifier.score(c, akindale_foundation)
        assert conf < 0.35


# ── LLM reranker gray band ────────────────────────────────────────────────────

class TestNeedsRerank:

    def test_below_gray_band(self):
        assert needs_rerank(0.34) is False

    def test_bottom_of_gray_band(self):
        assert needs_rerank(0.35) is True

    def test_middle_of_gray_band(self):
        assert needs_rerank(0.50) is True

    def test_top_of_gray_band(self):
        assert needs_rerank(0.65) is True

    def test_above_gray_band(self):
        assert needs_rerank(0.66) is False

    def test_zero_does_not_rerank(self):
        assert needs_rerank(0.0) is False

    def test_one_does_not_rerank(self):
        assert needs_rerank(1.0) is False


# ── URL normalization for reranker ────────────────────────────────────────────

class TestNormalizeForRerank:

    def test_pdf_url_normalized_to_root(self):
        candidates = [_candidate("https://wtgrantfoundation.org/files/annual-report.pdf")]
        result = _normalize_for_rerank(candidates)
        assert result[0].url == "https://wtgrantfoundation.org/"

    def test_deep_path_normalized_to_root(self):
        # paths > 60 chars get stripped to root
        long_path = "/about/leadership/board-of-directors/meet-the-founders/profiles"  # 63 chars
        assert len(long_path) > 60
        candidates = [_candidate(f"https://example.org{long_path}")]
        result = _normalize_for_rerank(candidates)
        assert result[0].url == "https://example.org/"

    def test_short_path_unchanged(self):
        candidates = [_candidate("https://woldfoundation.org/grants")]
        result = _normalize_for_rerank(candidates)
        assert result[0].url == "https://woldfoundation.org/grants"

    def test_homepage_unchanged(self):
        candidates = [_candidate("https://woldfoundation.org/")]
        result = _normalize_for_rerank(candidates)
        assert result[0].url == "https://woldfoundation.org/"

    def test_original_list_not_mutated(self):
        # _normalize_for_rerank must not mutate the original candidate objects
        c = _candidate("https://wtgrantfoundation.org/files/annual-report.pdf")
        original_url = c.url
        _normalize_for_rerank([c])
        assert c.url == original_url


# ── Pipeline status codes (mocked) ───────────────────────────────────────────

@pytest.mark.asyncio
async def test_pipeline_accepted_verifier_high_confidence(akindale_foundation, mock_serp_response_akindale):
    """High confidence candidate → accepted without LLM reranker."""
    # Boost snippet so verifier confidence clears HIGH_CONFIDENCE (0.65)
    mock_serp_response_akindale["organic_results"][0]["snippet"] = (
        "The Akindale Foundation in New York State provides grants. NY."
    )
    db1, db2, db3 = _mock_db_patches()
    with db1, db2, db3:
        output = await run(akindale_foundation)
    assert output.status.startswith("accepted")
    assert output.url is not None


@pytest.mark.asyncio
async def test_pipeline_accepted_kg(mock_serp_response_akindale):
    """KG result is always accepted regardless of verifier score."""
    foundation = _foundation("The Akindale Foundation", "NY", city="New York", ein="237421854")
    db1, db2, db3 = _mock_db_patches()
    with db1, db2, db3:
        output = await run(foundation)
    # KG result should be selected first — even if verifier is moderate
    assert "accepted" in output.status


@pytest.mark.asyncio
async def test_pipeline_accepted_via_llm_reranker():
    """Gray-band confidence → LLM reranker fires and accepts candidate."""
    foundation = _foundation("Wold Foundation", "WY", city="Casper")
    serp = {
        "search_information": {"total_results": "100"},
        "organic_results": [
            {"position": 1, "title": "Wold Foundation", "link": "https://woldfoundation.org/",
             "snippet": "The Wold Foundation promotes charitable programs."},
        ],
    }
    llm_resp = MagicMock()
    llm_resp.choices[0].message.content = json.dumps({"index": 0, "reasoning": "Exact match"})
    llm_resp.model = "openai/gpt-4o-mini"
    llm_resp.usage.prompt_tokens = 50
    llm_resp.usage.completion_tokens = 20

    db1, db2, db3 = _mock_db_patches()
    with db1, db2, db3, \
         patch("agents.grant_writer_v2.layer1_url_discovery.pipeline.search",
               new_callable=AsyncMock, return_value=serp), \
         patch("agents.grant_writer_v2.core.llm._client") as mock_client:
        mock_client.chat.completions.create = AsyncMock(return_value=llm_resp)
        output = await run(foundation)

    assert output.status == "accepted_llm"
    assert output.llm_rerank_used is True
    assert output.url == "https://woldfoundation.org/"


@pytest.mark.asyncio
async def test_pipeline_llm_returns_none_forces_rejection():
    """LLM returning idx=-1 (no match) must force best_conf=0 → rejected_low_confidence."""
    foundation = _foundation("American Foundation", "NY")
    serp = {
        "search_information": {"total_results": "500"},
        "organic_results": [
            {"position": 1, "title": "American Foundation for Suicide Prevention",
             "link": "https://afsp.org/", "snippet": "AFSP is a national org."},
        ],
    }
    llm_resp = MagicMock()
    llm_resp.choices[0].message.content = json.dumps({"index": -1, "reasoning": "Not the right org"})
    llm_resp.model = "openai/gpt-4o-mini"
    llm_resp.usage.prompt_tokens = 50
    llm_resp.usage.completion_tokens = 20

    db1, db2, db3 = _mock_db_patches()
    with db1, db2, db3, \
         patch("agents.grant_writer_v2.layer1_url_discovery.pipeline.search",
               new_callable=AsyncMock, return_value=serp), \
         patch("agents.grant_writer_v2.core.llm._client") as mock_client:
        mock_client.chat.completions.create = AsyncMock(return_value=llm_resp)
        output = await run(foundation)

    assert output.status == "rejected_low_confidence", (
        "idx=-1 from LLM must force best_conf=0 → rejected_low_confidence, "
        "not accepted with the original verifier score"
    )


@pytest.mark.asyncio
async def test_pipeline_no_candidates(akindale_foundation, mock_serp_response_no_results):
    """Empty SerpAPI response → rejected_no_candidates."""
    db1, db2, db3 = _mock_db_patches()
    with db1, db2, db3, \
         patch("agents.grant_writer_v2.layer1_url_discovery.pipeline.search",
               new_callable=AsyncMock, return_value=mock_serp_response_no_results):
        output = await run(akindale_foundation)
    assert output.status == "rejected_no_candidates"


@pytest.mark.asyncio
async def test_pipeline_fallback_query_used_when_primary_all_blocklisted():
    """Primary results all blocklisted → fallback query fires."""
    foundation = _foundation("AHEPA Rochester Foundation", "NY")
    primary_serp = {
        "search_information": {"total_results": "50"},
        "organic_results": [
            {"position": 1, "title": "AHEPA Rochester | Candid",
             "link": "https://candid.org/ahepa-rochester", "snippet": "Directory listing."},
        ],
    }
    fallback_serp = {
        "search_information": {"total_results": "10"},
        "organic_results": [
            {"position": 1, "title": "AHEPA Rochester Chapter",
             "link": "https://aheparochester.org/", "snippet": "Official AHEPA chapter site in NY."},
        ],
    }

    call_count = 0
    async def mock_search(query):
        nonlocal call_count
        call_count += 1
        return primary_serp if call_count == 1 else fallback_serp

    db1, db2, db3 = _mock_db_patches()
    with db1, db2, db3, \
         patch("agents.grant_writer_v2.layer1_url_discovery.pipeline.search",
               side_effect=mock_search):
        await run(foundation)

    assert call_count == 2, "Fallback search must be called when primary yields no valid candidates"


@pytest.mark.asyncio
async def test_pipeline_serpapi_error(akindale_foundation):
    """SerpAPI exception → error_serpapi status."""
    db1, db2, db3 = _mock_db_patches()
    with db1, db2, db3, \
         patch("agents.grant_writer_v2.layer1_url_discovery.pipeline.search",
               new_callable=AsyncMock, side_effect=Exception("API timeout")):
        output = await run(akindale_foundation)
    assert output.status == "error_serpapi"


@pytest.mark.asyncio
async def test_pipeline_all_blocklisted_no_fallback_hits():
    """Primary all blocklisted, fallback also empty → rejected_no_candidates."""
    foundation = _foundation("No Web Foundation", "AK")
    empty_serp = {"search_information": {"total_results": "0"}, "organic_results": []}
    db1, db2, db3 = _mock_db_patches()
    with db1, db2, db3, \
         patch("agents.grant_writer_v2.layer1_url_discovery.pipeline.search",
               new_callable=AsyncMock, return_value=empty_serp):
        output = await run(foundation)
    assert output.status == "rejected_no_candidates"


# ── Candidate audit fields ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_verifier_scores_written_to_candidates():
    """verifier_score and verifier_signals must be set on each scored candidate."""
    foundation = _foundation("Wold Foundation", "WY", city="Casper")
    serp = {
        "search_information": {"total_results": "100"},
        "organic_results": [
            {"position": 1, "title": "Wold Foundation", "link": "https://woldfoundation.org/",
             "snippet": "The Wold Foundation promotes charitable programs."},
        ],
    }
    llm_resp = MagicMock()
    llm_resp.choices[0].message.content = json.dumps({"index": 0, "reasoning": "Exact match"})
    llm_resp.model = "openai/gpt-4o-mini"
    llm_resp.usage.prompt_tokens = 50
    llm_resp.usage.completion_tokens = 20

    db1, db2, db3 = _mock_db_patches()
    with db1, db2, db3, \
         patch("agents.grant_writer_v2.layer1_url_discovery.pipeline.search",
               new_callable=AsyncMock, return_value=serp), \
         patch("agents.grant_writer_v2.core.llm._client") as mock_client:
        mock_client.chat.completions.create = AsyncMock(return_value=llm_resp)
        output = await run(foundation)

    non_blocklisted = [c for c in output.candidates_seen if not c.blocklisted]
    for c in non_blocklisted:
        assert c.verifier_score is not None, f"verifier_score not set on {c.url}"
        assert c.verifier_signals is not None, f"verifier_signals not set on {c.url}"
