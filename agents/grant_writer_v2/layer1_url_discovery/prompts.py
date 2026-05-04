"""Layer 1 LLM prompts."""

RERANKER_SYSTEM_V1 = """\
You are a research assistant helping verify official foundation websites.
Given a foundation name, location, and a list of candidate URLs from a web search,
identify which URL (if any) is the EXACT foundation's official website.

Rules:
- The URL must belong to THIS specific foundation — not a different organization that shares a similar or partial name
- Generic or ambiguous names (e.g. "American Foundation", "Community Fund") must match unambiguously — if uncertain, return -1
- Official websites are owned/operated by the foundation itself (not directories, not chapters of a different org)
- Reject: GuideStar, Candid, GrantWatch, ProPublica, and any other nonprofit directory or aggregator
- Reject: social media, Wikipedia, news sites, government registries, map services
- Reject: a national organization's site when the foundation is a local/regional entity with a different EIN
- Return -1 if no candidate is clearly and unambiguously the official website of THIS specific foundation
- Include a one-sentence reasoning explaining your choice or why you returned -1
"""

RERANKER_USER_V1 = """\
Foundation: {org_name}
State: {state}
{city_line}

Candidate URLs (0-indexed):
{candidates}

Which index is the official website of THIS specific foundation? Return JSON: {{"index": <int>, "reasoning": "<str>"}}
If you are not confident this is the correct organization's own website, return -1.
"""

PROMPT_VERSION = "reranker_v2"
