# Schema Reference v3

**Purpose:** Authoritative Pydantic schemas for every layer.
**Primary unit:** Grant Program (not Foundation). One foundation → N programs.

---

## 1. Common Components (`schemas/common.py`)

- `ContactInfo` — email, phone, address, contact_person, etc.
- `DeadlineSlot` — cycle_label, deadline_iso, deadline_type, is_recurring, raw_text
- `RuleEvaluation` — value (bool), confidence (float), evidence_quote, source_url
- `CrawledPage` — url, title, http_status, bytes_fetched, keyword_matches, page_type
- `CandidateRecord` — url, position, title, snippet, blocklisted, verifier_score, selected

---

## 2. Layer 1 Output (`layer1_url_discovery/schemas.py`)

```
Layer1Status: accepted_kg | accepted_verifier | accepted_llm |
              rejected_no_candidates | rejected_shell_address |
              rejected_low_confidence | needs_review |
              error_serpapi | error_blocked | error_timeout

Layer1Output:
  ein, status, url, confidence, method, evidence
  knowledge_graph_present, serpapi_query, candidates_seen (ALL candidates)
  verifier_score, llm_rerank_used, processed_at, cost_usd
```

---

## 3. Layer 2 Output (`layer2_grant_detection/schemas.py`)

```
SixRuleResult:
  has_grants, accepts_applications, not_invitation_only,
  not_donation_only, allows_unsolicited, geography_valid,
  active_or_recurring  — each a RuleEvaluation

GrantProgramVerdict:
  program_id (UUID), ein, program_name, program_url
  verdict: VALID | NEEDS_REVIEW | INVALID | ERROR
  verdict_confidence, verdict_reasoning
  rules: SixRuleResult
  override_applied: geography_excluded | past_only | ...

Layer2Output:
  ein, rollup (verdict + counts), program_verdicts[]
  pages_crawled[], corpus_cache_key, agent_iterations
  stop_reason: completed | max_iterations | max_pages | max_bytes | max_cost | error
  cost_usd, processed_at
```

---

## 4. Org Profile (`schemas/org_profile.py` / `layer3_org_extraction/schemas.py`)

```
OrgProfile:
  ein, org_name, mission, background, about, contact
  foundation_type, ntee_code, website_url
  focus_areas (controlled vocab), geography_served (ISO codes)
  total_assets_usd, annual_giving_usd, grants_paid_3yr_avg_usd
  accepts_unsolicited_proposals, is_invitation_only
  application_methods_offered
  source_pages, extraction_model, evidence_quotes
```

---

## 5. Grant Program Record — PRIMARY UNIT (`schemas/grant_program.py`)

```
GrantProgramRecord:
  # Identity
  program_id, ein, program_name, program_slug, program_url, verdict

  # Funding
  funding_priorities, types_of_grant
  grant_amount_freeform, grant_amount_min_usd, grant_amount_max_usd
  funding_match_required, funding_match_percent

  # Eligibility (freeform + structured)
  eligibility_criteria
  eligible_applicants_freeform, eligible_applicant_types (controlled vocab)
  eligible_geographies (ISO), excluded_geographies
  eligible_focus_areas (controlled vocab), excluded_uses
  minimum_org_age_years, minimum_budget_usd, requires_501c3

  # Deadlines
  proposal_deadline_freeform, deadlines[], deadline_type (controlled vocab)
  next_deadline_iso, is_currently_open, loi_required

  # Application
  application_method (controlled vocab), application_portal_url
  application_steps[], required_documents[], review_timeline_weeks

  # Flags
  is_invitation_only, accepts_unsolicited, is_recurring, recurrence

  # Provenance (mandatory)
  source_pages[], extraction_model, extraction_prompt_version
  extraction_confidence, evidence_quotes {field → verbatim quote}
  completeness_score
```

---

## 6. SEO Metadata (`schemas/seo.py`)

```
SeoMetadata (6 LLM-generated fields, strict char limits):
  opportunity_title (max 70)
  h1_tag (max 60)
  meta_title (max 60)
  meta_description (max 160)
  opportunity_teaser (~500 words, anonymized)
  opportunity_title_for_subscriber (max 150)

GrantProgramMetadata (Layer 5 enrichment — appended to GrantProgramRecord):
  + slug, canonical_url
  + categories, primary_category, tags
  + filter_funding_range, filter_eligibility, filter_geography_*
  + filter_deadline_type, filter_currently_open, filter_next_deadline_iso
  + search_blob (FULLTEXT), search_keywords
  + duplicate_of_program_id, similarity_score_to_duplicate
  + publish_status: draft | review | published | archived
```

---

## 7. Audit Schemas (`schemas/audit.py`)

```
PipelineRun — run_id, ein, layer, status, output_snapshot JSON,
              model, prompt_version, cost_usd, duration_ms

LLMCallRecord — ein, layer, provider, model, prompt_hash,
                input_tokens, output_tokens, cost_usd, latency_ms
```

---

## Controlled Vocabulary Fields

| Field | Vocabulary file |
|---|---|
| `focus_areas` | `vocabularies/focus_areas.yaml` |
| `eligible_applicant_types` | `vocabularies/applicant_types.yaml` |
| `application_method` | `vocabularies/application_methods.yaml` |
| `deadline_type` | `vocabularies/deadline_types.yaml` |
| `filter_funding_range` | `vocabularies/funding_buckets.yaml` |
| `foundation_type` | `vocabularies/foundation_types.yaml` |
| `administrative_address_pattern` | `vocabularies/shell_address_patterns.yaml` |

LLM hallucinations in these fields are rejected at Pydantic boundary → record flagged `needs_review`.
