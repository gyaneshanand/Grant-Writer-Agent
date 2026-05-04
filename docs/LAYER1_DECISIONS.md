# Layer 1 — URL Discovery: Design Decisions & Known Pitfalls

This document records every non-obvious decision, bug fix, and validated behaviour
from Layer 1's development and testing. Read this before modifying any file under
`agents/grant_writer_v2/layer1_url_discovery/` or `agents/grant_writer_v2/tests/test_layer1.py`.

---

## 1. `lstrip("www.")` — Critical Bug (Fixed)

**Files affected:** `verifier.py`, `layer2_grant_detection/tools.py`

`str.lstrip(chars)` strips individual characters, not a prefix string. Calling
`.lstrip("www.")` strips any leading character that is in the set `{'w', '.'}`.

```python
# BUG — strips the leading 'w' from woldfoundation:
"www.woldfoundation.org".lstrip("www.")  # → "oldfoundation.org"

# FIX — strip the literal prefix "www." only:
netloc = "www.woldfoundation.org"
domain = netloc[4:] if netloc.startswith("www.") else netloc  # → "woldfoundation.org"
```

**Impact:** Any foundation whose domain starts with `w` (wold, wells, wood, wright, …)
would have `name_in_domain = 0.0` in the verifier, silently pushing confidence into the
gray band and forcing an unnecessary LLM reranker call — or worse, a false rejection.

**Test coverage:** `TestVerifierNameInDomain::test_wold_in_woldfoundation`,
`test_www_prefix_stripped_correctly`.

---

## 2. Whole-Segment vs Partial Domain Matching

**File:** `verifier.py` — `name_in_domain` signal (max 0.4)

Foundation name tokens are matched against domain segments using two tiers:

| Match type | Weight | Example |
|---|---|---|
| **Full segment** — token equals a `-` or `.` delimited part | 1.0 × | `james` in `james-foundation.org` |
| **Partial** — token is a substring of a long segment (≥ 8 chars) | 0.5 × | `wold` inside `woldfoundation` |

The ≥ 8 char guard prevents short noise segments from triggering false partials.
For example `"acs"` inside `"facs.org"` — `"facs"` is only 4 chars, so no partial
match fires. Without this guard, searching `"ACS Foundation"` would falsely score
`facs.org` as a domain match.

**Test coverage:** `test_facs_does_not_match_acs`, `test_partial_match_compound_domain`.

---

## 3. LLM Reranker — Only for Gray Band (0.35–0.65)

**File:** `llm_reranker.py`, `pipeline.py`

The LLM reranker fires **only** when `0.35 ≤ best_confidence ≤ 0.65`. It is never
called for clear accepts (> 0.65) or clear rejects (< 0.35). This keeps L1 cheap —
most foundations are resolved deterministically.

### `idx = -1` or `idx = None` must force rejection

Early versions kept the verifier score when the LLM returned `-1` (no match).
This caused foundations with a gray-band verifier score to be accidentally accepted
with the wrong URL.

```python
# pipeline.py — after rerank():
if idx is not None:
    best_candidate = rerank_candidates[idx]
    best_conf = max(verifier_score, 0.55)
else:
    best_conf = 0.0  # ← MUST be 0.0, not the original verifier score
```

**Test coverage:** `test_pipeline_llm_returns_none_forces_rejection`.

### Prompt strictness

The system prompt (`RERANKER_SYSTEM_V1`, `prompts.py`) requires:
- Exact match to THIS foundation, not a similarly-named national org
- Return `-1` for ambiguous/generic names ("American Foundation", "Community Fund")
- Reject a national org's site when the foundation is a local/regional entity

Do not soften the prompt. The "closely relates to" wording was removed because it
caused AFSP (American Foundation for Suicide Prevention) to be accepted when
searching "American Foundation".

---

## 4. PDF / Deep-Path URL Normalization Before Rerank

**File:** `pipeline.py` — `_normalize_for_rerank()`

SerpAPI sometimes surfaces PDF files or deep sub-pages as the top result
(e.g. `wtgrantfoundation.org/files/2023-annual-report.pdf`). Passing a PDF path
to the LLM reranker is ambiguous — the LLM should evaluate the domain, not a
specific file.

Rule: if the URL path ends in `.pdf` OR is longer than 60 characters, strip to
`scheme://netloc/` before passing to the reranker. The root-domain URL is stored
as the accepted URL.

```python
if parsed.path.lower().endswith(".pdf") or len(parsed.path) > 60:
    c2.url = f"{parsed.scheme}://{parsed.netloc}/"
```

The original candidate list is **not mutated** — `copy.copy()` is used.

**Test coverage:** `TestNormalizeForRerank`.

---

## 5. Fallback Query

**File:** `pipeline.py`, `serpapi_client.py` — `build_fallback_query()`

When the primary SerpAPI query returns zero non-blocklisted candidates, a broader
fallback query is tried automatically. The fallback:
- Removes quotes around the org name
- Drops the word "foundation" / "fund" / "trust" / "group" / "inc" / "corp"
- Adds "official website" instead of "foundation official site"

```python
# Primary:  '"AHEPA Rochester Foundation" foundation official site NY'
# Fallback: 'AHEPA Rochester official website NY'
```

This handles foundations whose name in SerpAPI results doesn't include the word
"foundation", causing the primary query to return only directory listings.

**Test coverage:** `test_pipeline_fallback_query_used_when_primary_all_blocklisted`,
`test_build_fallback_query_strips_foundation_suffix`.

---

## 6. Blocklist

**File:** `vocabularies/url_blocklist.yaml`, `layer1_url_discovery/blocklist.py`

The blocklist is loaded from YAML at import time in `core/vocab.py`.
**Restart the server after editing the YAML** — the loaded vocab is module-level
and is not refreshed on hot-reload.

Domains confirmed as correctly blocklisted during testing:

| Domain | Category |
|---|---|
| `candid.org`, `guidestar.org` | foundation_directories |
| `grantmakers.io`, `hinchilla.com` | foundation_directories |
| `causeiq.com`, `charitynavigator.org` | foundation_directories |
| `propublica.org`, `grantwatch.com` | foundation_directories |
| `linkedin.com`, `indeed.com` | job_boards |
| `wikipedia.org`, `facebook.com` | social_media |
| `foundationcenter.org` | foundation_directories |

A foundation's own domain (e.g. `woldfoundation.org`) must never appear in the
blocklist.

---

## 7. Verifier Signal Weights (Must Sum to 1.0)

| Signal | Max | Source |
|---|---|---|
| `name_in_domain` | 0.40 | Org name tokens in URL domain |
| `name_in_title` | 0.25 | Org name tokens in SERP title |
| `name_in_snippet` | 0.15 | Org name tokens in SERP snippet |
| `state_in_snippet` | 0.10 | State code or city in snippet |
| `kg_bonus` | 0.10 | Result sourced from Knowledge Graph |

Thresholds in `pipeline.py`:
- `HIGH_CONFIDENCE = 0.65` — accept immediately, skip LLM
- `MIN_CONFIDENCE = 0.35` — reject if below this after reranker
- `0.35–0.65` — gray band, triggers LLM reranker

---

## 8. Verifier Scores Must Be Written Back to Candidates

**File:** `pipeline.py`

Early versions scored candidates but never stored the result back on the
`CandidateRecord` objects, so `v2_layer1_candidates` rows had `verifier_score = NULL`.

The fix — after calling `verifier.score()`, assign back:

```python
conf, signals = verifier.score(c, foundation)
c.verifier_score = conf        # ← required
c.verifier_signals = signals   # ← required
```

**Test coverage:** `test_verifier_scores_written_to_candidates`.

---

## 9. Status Codes Reference

| Status | Meaning |
|---|---|
| `accepted_kg` | Top result came from Knowledge Graph |
| `accepted_verifier` | Verifier confidence ≥ 0.65, no LLM needed |
| `accepted_llm` | Gray-band confidence; LLM reranker confirmed the URL |
| `rejected_no_candidates` | SerpAPI returned 0 non-blocklisted results (even after fallback) |
| `rejected_low_confidence` | Best candidate scored < 0.35 (or LLM returned -1) |
| `error_serpapi` | SerpAPI raised an exception |

---

## 10. Test File Location

All Layer 1 tests live in:
```
agents/grant_writer_v2/tests/test_layer1.py
```

Run with:
```bash
pytest agents/grant_writer_v2/tests/test_layer1.py -v
```

Tests use `unittest.mock` to patch `search`, `sql_exec`, `sql_exec_many`,
`write_pipeline_run`, and `core.llm._client`. No real network calls are made.
