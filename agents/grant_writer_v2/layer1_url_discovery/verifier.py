"""
Deterministic confidence scorer for Layer 1 URL candidates.
Scores each non-blocklisted candidate against foundation identity signals.
"""
import re
from typing import Optional
from agents.grant_writer_v2.schemas.common import CandidateRecord, FoundationInput


def _name_tokens(name: str) -> set[str]:
    """Lowercase words from org name, excluding stopwords."""
    stopwords = {"the", "a", "an", "of", "and", "or", "for", "in", "at", "foundation", "fund"}
    return {w.lower() for w in re.split(r"\W+", name) if len(w) > 2 and w.lower() not in stopwords}


def score(candidate: CandidateRecord, foundation: FoundationInput) -> tuple[float, dict[str, float]]:
    """
    Returns (confidence 0–1, signals dict).
    Signals:
      name_in_domain   0.4  — org name tokens appear in the URL domain
      name_in_title    0.25 — org name tokens appear in result title
      name_in_snippet  0.15 — org name tokens appear in snippet
      state_in_snippet 0.10 — state/city appear in snippet
      kg_bonus         0.10 — result came from Knowledge Graph
    """
    signals: dict[str, float] = {}
    url_lower = candidate.url.lower()
    title_lower = candidate.title.lower()
    snippet_lower = candidate.snippet.lower()

    name_tokens = _name_tokens(foundation.org_name)

    # name in domain
    # Primary: token matches a whole segment (split on . and -)
    # Secondary (half weight): token appears inside a long concatenated segment (e.g. "wtgrantfoundation")
    try:
        from urllib.parse import urlparse
        netloc = urlparse(url_lower).netloc
        domain = netloc[4:] if netloc.startswith("www.") else netloc
        domain_parts = set(re.split(r"[.\-]", domain))
        full_matched = sum(1 for t in name_tokens if t in domain_parts)
        # partial: token is a substring of a single segment that is long (>=8 chars, avoids short noise)
        partial_matched = sum(
            1 for t in name_tokens
            if t not in domain_parts and any(t in p and len(p) >= 8 for p in domain_parts)
        )
        raw = full_matched + 0.5 * partial_matched
        signals["name_in_domain"] = min(0.4, 0.4 * raw / max(len(name_tokens), 1))
    except Exception:
        signals["name_in_domain"] = 0.0

    # name in title
    matched_title = sum(1 for t in name_tokens if t in title_lower)
    signals["name_in_title"] = min(0.25, 0.25 * matched_title / max(len(name_tokens), 1))

    # name in snippet
    matched_snippet = sum(1 for t in name_tokens if t in snippet_lower)
    signals["name_in_snippet"] = min(0.15, 0.15 * matched_snippet / max(len(name_tokens), 1))

    # state/city in snippet
    geo_match = 0.0
    if foundation.state.lower() in snippet_lower:
        geo_match += 0.05
    if foundation.city and foundation.city.lower() in snippet_lower:
        geo_match += 0.05
    signals["state_in_snippet"] = min(0.10, geo_match)

    # Knowledge Graph bonus
    signals["kg_bonus"] = 0.10 if candidate.snippet == "Knowledge Graph result" else 0.0

    confidence = sum(signals.values())
    return round(min(confidence, 1.0), 3), signals
