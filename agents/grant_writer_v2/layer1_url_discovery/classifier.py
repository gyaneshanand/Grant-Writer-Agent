"""
Pattern-based classifier for SerpAPI candidates.
Extracts raw candidate records from a SerpAPI response.
"""
from typing import Any
from agents.grant_writer_v2.schemas.common import CandidateRecord
from agents.grant_writer_v2.layer1_url_discovery.blocklist import check as blocklist_check


def extract_candidates(serp_response: dict[str, Any]) -> list[CandidateRecord]:
    """Parse organic results + knowledge-graph into CandidateRecord list."""
    candidates: list[CandidateRecord] = []
    position = 0

    # Knowledge Graph (highest priority source)
    kg = serp_response.get("knowledge_graph", {})
    kg_website = kg.get("website") or kg.get("official_website")
    if kg_website:
        blocked, cat, domain = blocklist_check(kg_website)
        candidates.append(
            CandidateRecord(
                url=kg_website,
                position=position,
                title=kg.get("title", ""),
                snippet="Knowledge Graph result",
                blocklisted=blocked,
                blocklist_category=cat,
                blocklist_domain=domain,
            )
        )
        position += 1

    # Organic results
    for result in serp_response.get("organic_results", []):
        url = result.get("link", "")
        if not url:
            continue
        blocked, cat, domain = blocklist_check(url)
        candidates.append(
            CandidateRecord(
                url=url,
                position=position,
                title=result.get("title", ""),
                snippet=result.get("snippet", ""),
                blocklisted=blocked,
                blocklist_category=cat,
                blocklist_domain=domain,
            )
        )
        position += 1

    return candidates
