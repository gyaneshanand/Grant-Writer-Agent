# Layer 2 — Grant Detection: Knowledge Transfer

This document is the single source of truth for understanding, maintaining, and
extending Layer 2. Read this before touching any file under
`agents/grant_writer_v2/layer2_grant_detection/`.

---

## What Layer 2 Does

Layer 2 answers the question: **"What grant programs does this foundation run, and
do they pass our eligibility rules?"**

It takes the verified URL produced by Layer 1, crawls the foundation's website
using an LLM-driven agent, identifies distinct grant programs, evaluates each
against 7 rules, and produces a per-program verdict (VALID / NEEDS_REVIEW /
INVALID) plus a foundation-level rollup.

**Prerequisite:** `foundations.v2_layer1_url` must be set. If missing, Layer 2
returns `status: error_no_url` immediately — no crawling happens.

---

## Architecture: LangGraph StateGraph

Layer 2 is the **only layer that uses LangGraph**. Every other layer (L1, L3, L4,
L5) is a plain `async def run()`. LangGraph is used here because this layer is
genuinely stateful with branching, retries, and mid-run cap enforcement.

```
START
  │
  ▼
crawl_agent  ──→  tools (fetch_page / find_links / extract_pdf)
  │  ↑______________↓   (loop until agent stops calling tools or cap hit)
  │
  ▼  (agent returns no tool_calls, or cap hit)
identify_programs   (LLM: corpus → list of distinct programs)
  │
  ▼
evaluate_rules      (LLM × N programs: 7-rule verdict per program)
  │
  ▼
aggregate_verdicts  (pure Python rollup, no LLM)
  │
  ▼
END
```

### Files

| File | Role |
|---|---|
| `pipeline.py` | Entry point `run()` — reads DB, builds state, invokes graph, persists results |
| `graph.py` | `build_graph(state_ref)` — defines all nodes and conditional edges |
| `tools.py` | 3 LangChain tools: `fetch_page`, `find_links`, `extract_pdf` |
| `program_identifier.py` | `identify_programs()` node — LLM call, returns list of program dicts |
| `rule_evaluator.py` | `evaluate_program()` and `evaluate_all_programs()` — 7-rule LLM eval per program |
| `verdict_aggregator.py` | `aggregate()` — pure Python rollup, no LLM |
| `prompts.py` | All LLM prompts for this layer |
| `schemas.py` | `GraphState` TypedDict + `Layer2Output` Pydantic model |

---

## The `state_ref` Pattern (Critical to Understand)

LangGraph's `GraphState` is immutable between nodes — each node returns a dict of
updates, it doesn't mutate in place. But the **tools** (fetch_page, find_links,
extract_pdf) need to increment cap counters (`pages_fetched`, `bytes_fetched`, etc.)
and accumulate the corpus **during tool execution**, before the next node runs.

The solution: a **`state_ref` dict** is created in `pipeline.py` and passed into
`build_graph()`. Tools mutate `state_ref` in-place. After each agent iteration,
`crawl_agent_node` reads back from `state_ref` and includes the updated values in
its return dict so LangGraph state stays in sync.

```
pipeline.py creates state_ref = {"corpus": [], "pages_fetched": 0, ...}
    │
    ├── passed to build_graph(state_ref)  →  tools close over state_ref
    │                                         and mutate it directly
    │
    └── crawl_agent_node returns:
          {"corpus": state_ref["corpus"],          ← syncs to GraphState
           "pages_fetched": state_ref["pages_fetched"], ...}
```

At the end of the graph, `pipeline.py` reads the final corpus from `state_ref`
(not `final_state["corpus"]`) because `identify_programs_node` also reads from
`state_ref` to ensure it sees all tool-accumulated pages.

---

## The 5 Hard Caps

An uncapped agent loop is a runaway-cost risk. Five caps are enforced, all checked
**before** each agent iteration in `crawl_agent_node` and inside each tool.

| Cap | Default | Env var | Where enforced |
|---|---|---|---|
| Max agent iterations | 10 | `V2_L2_MAX_ITERATIONS` | `crawl_agent_node` at top of each iteration |
| Max pages fetched | 25 | `V2_L2_MAX_PAGES` | `fetch_page` tool refuses when hit |
| Max PDFs extracted | 5 | `V2_L2_MAX_PDFS` | `extract_pdf` tool refuses when hit |
| Max bytes fetched | 8 MB | `V2_L2_MAX_BYTES` | Both fetch tools check accumulator |
| Per-run cost ceiling | $0.50 | `V2_L2_MAX_COST_USD` | `core/llm.py` raises `BudgetExceeded` |

When any cap is hit:
1. `crawl_agent_node` returns `stop_reason = "max_iterations"` (or whichever cap)
   and **`"messages": []`** — clearing messages is critical (see pitfall below)
2. `should_continue` routes to `identify_programs` instead of `tools`
3. Whatever corpus was collected so far is still processed and persisted

---

## Tools Deep-Dive

### `fetch_page(url)`

- Async — must be `async def` (LangGraph `ToolNode` runs tools in async context)
- Checks: same-domain, already-visited, pages cap, bytes cap
- **403 handling:** returns `[BLOCKED_403]` message with suggested grant subpaths to try — does NOT add to corpus. The pipeline checks `pages_fetched == 0` after the graph to distinguish bot-blocked from genuinely no-programs
- Stores full HTML in corpus (for L3/L4 reuse), returns **stripped text** to the agent
- HTML stripping removes `<script>`, `<style>`, all tags, collapses whitespace

### `find_links(page_url="")`

- Sync (no network call — reads from `state_ref["corpus"]`)
- **Reads the corpus internally** — does NOT accept raw HTML as an argument (that
  was the original design and was unreliable over 30KB of JSON)
- Filters hrefs to same-domain grant-relevant links only (keyword set in `GRANT_LINK_KEYWORDS`)
- Returns newline-separated absolute URLs, or `[NO_GRANT_LINKS_FOUND]`

### `extract_pdf(url)`

- Async — uses `pypdf` to extract text page by page (first 50 pages)
- Returns stripped text to agent; full text stored in corpus with `content_type: application/pdf`

---

## Program Identification

`program_identifier.py` calls `gpt-4o` (configurable via `V2_MODEL_LAYER2_PROGRAM_IDENTIFIER`)
with the stripped corpus text and asks it to list distinct grant programs.

**Key design decisions:**

1. **Prompt uses `{"programs": [...]}` wrapper** — `response_format: json_object`
   requires a top-level JSON object, not an array. The prompt was changed from
   "Return a JSON array" to "Return `{"programs": [...]}`". Without this, the LLM
   returned bare objects or single programs outside an array.

2. **Fallback handler for single-object response** — if the LLM returns a bare
   `{"program_name": ...}` object anyway, it is wrapped in a list rather than
   silently dropped.

3. **HTML stripping in corpus builder** — `_build_corpus_text()` strips HTML tags
   from each page before feeding to the LLM. Without this, 30KB of CSS/JS noise
   dominated the context window.

4. **8000 char cap per page, 40K total corpus** — keeps token cost predictable.

---

## Rule Evaluation

`rule_evaluator.py` calls `gpt-4o-mini` (configurable) once per program.

**The 7 rules:**

| Rule | Meaning |
|---|---|
| `has_grants` | Foundation provides financial grants to external recipients |
| `accepts_applications` | Open application process exists |
| `not_invitation_only` | Not invitation/nomination-only |
| `not_donation_only` | Foundation gives money out, not just receives it |
| `allows_unsolicited` | General pool can apply without prior relationship |
| `geography_valid` | Funds US work or has international scope |
| `active_or_recurring` | Program is current, not a closed past event |

**Verdict logic (in `rule_evaluator.py`):**

```python
if rules.all_pass(confidence_threshold=0.6):
    verdict = "VALID"
elif rules.any_fail_hard(confidence_threshold=0.8):
    verdict = "INVALID"
else:
    verdict = "NEEDS_REVIEW"
```

- `all_pass`: every rule is `True` AND confidence ≥ 0.6
- `any_fail_hard`: any rule is `False` AND confidence ≥ 0.8
- Anything in between → `NEEDS_REVIEW`

**`BudgetExceeded` propagates up** — if the cost cap is hit mid-evaluation,
remaining programs are skipped and whatever verdicts were produced are persisted.

---

## Verdict Aggregation

`verdict_aggregator.py` is pure Python, no LLM.

| Condition | Rollup |
|---|---|
| ≥ 1 program is VALID | `VALID` |
| 0 VALID, ≥ 1 NEEDS_REVIEW | `NEEDS_REVIEW` |
| All INVALID (or empty) | `INVALID` |

---

## Pipeline Status Codes

| Status | Meaning |
|---|---|
| `completed` | Graph ran to end, ≥ 1 valid program found |
| `rejected_no_programs` | Graph ran to end, corpus crawled (≥ 3 pages) but 0 programs identified |
| `needs_review` | Cap hit mid-crawl, bot-protected, or JS-rendered site |
| `error_no_url` | L1 has not completed — `v2_layer1_url` is NULL in DB |
| `error_graph` | `graph.ainvoke()` raised an unhandled exception |

**Bot-protection special case:** When `pages_fetched == 0` after the graph
(Cloudflare/403 on all pages), the pipeline sets:
- `status: needs_review`
- `stop_reason: bot_protected`
- `rollup_verdict: UNKNOWN_BOT_PROTECTED`

**JS-rendered site special case:** When `pages_fetched < 3` and 0 programs found
(site uses JavaScript navigation — pages load but contain no grant content in static HTML),
the pipeline sets:
- `status: needs_review`
- `stop_reason: insufficient_crawl`
- `rollup_verdict: UNKNOWN_JS_RENDERED`

Both cases distinguish "site was inaccessible or JS-only" from "site crawled but genuinely
no programs." Laravel can query `WHERE stop_reason IN ('bot_protected', 'insufficient_crawl')`
to route these to a separate handling queue for manual review or Selenium-based crawling.

---

## Known Pitfalls

### 1. `messages: []` on cap hit is mandatory

When the agent hits a cap, `crawl_agent_node` returns `"messages": []`. This
clears any pending `tool_calls` from the LangGraph message accumulator. Without
it, `should_continue` sees the last message's `tool_calls` as still pending and
routes back to the `tools` node even though the cap was hit — causing an infinite
loop or crash.

### 2. `crawl_agent_node` must be `async def`

The LangGraph graph is invoked with `await graph.ainvoke(...)`. All nodes must be
async-compatible. `llm.invoke()` (sync) blocks the event loop inside FastAPI —
use `await llm.ainvoke(messages)` instead.

### 3. `find_links` must not receive HTML as a tool argument

Early design passed full page HTML as a JSON argument to `find_links`. At 30KB,
this was unreliable and occasionally truncated by the tool-call serializer. The
redesign reads `state_ref["corpus"][-1]["text"]` internally — no argument needed.
The prompt instructs the agent to call `find_links()` with no arguments.

### 4. LangSmith tracing must stay disabled

`LANGSMITH_TRACING=false` in `.env`. An expired LangSmith API key causes a ~2
minute delay per LLM call as the SDK retries. Even with a valid key, tracing
adds latency. Disable it unless actively debugging.

### 5. `response_format: json_object` requires a top-level object

OpenAI's `json_object` response format enforces that the output is a JSON object
(not an array). Prompts that say "return a JSON array" will cause the model to
wrap the array in an object with an arbitrary key. Always design prompts to return
`{"key": [...]}` and handle all wrapper key variants in the parser.

### 6. `lstrip("www.")` bug affects `_is_same_domain` in tools.py

`str.lstrip(chars)` strips individual characters, not a prefix. Any domain
starting with `w` (e.g. `woldfoundation.org`) has its leading `w` stripped,
breaking same-domain checks. Fixed — see `_strip_www()` helper in `tools.py`.

### 7. `CRAWL_AGENT_SYSTEM` prompt must be formatted with `base_url`

`CRAWL_AGENT_SYSTEM` contains `{base_url}` placeholders in the CRITICAL section
listing fallback grant paths. In `graph.py`, the system prompt must be formatted
before passing to `SystemMessage`:

```python
system_prompt = CRAWL_AGENT_SYSTEM.replace("{base_url}", state["base_url"])
messages = [SystemMessage(content=system_prompt), ...]
```

Without this, the LLM sees the literal string `{base_url}grants/` and cannot
substitute the actual domain — defeating the entire JS-site fallback strategy.

### 8. `find_links` keyword "fund" matches news/article URLs

`GRANT_LINK_KEYWORDS` originally included the bare word `"fund"`, which matches
path segments like `/global-fund-impact-stories/` (a news article on gatesfoundation.org).
The agent would then fetch the news article, fail to find grant programs, and stop.

Two-part fix:
1. Removed bare `"fund"` from `GRANT_LINK_KEYWORDS` (kept `"funding"`, `"grantmaking"`).
2. Added `NON_GRANT_PATH_SEGMENTS` set (`news`, `blog`, `articles`, `ideas`, etc.) —
   any URL whose path contains one of these segments is excluded from `find_links`
   results even if another segment matches a keyword.

---

## Data Flow Into Later Layers

- **Corpus** is saved to disk cache after the graph: `core/corpus_cache.py` writes
  `agents/grant_writer_v2/.cache/corpus/{ein}.json`. L3 and L4 read from this
  cache — they do not re-crawl.
- **Program verdicts** are persisted to `v2_grant_programs` table with verdict,
  confidence, and full 7-rule JSON. L4 reads VALID rows from this table and
  enriches them with full structured fields.
- **Rollup** is written to `foundations.v2_layer2_*` columns for Laravel to
  query without joining `v2_grant_programs`.

---

## Running Layer 2

```bash
# Via API (normal path)
curl -X POST http://localhost:8001/api/v1/grant-writer-v2/layer/2/run \
  -H "Content-Type: application/json" \
  -d '{"org_name": "The James Foundation", "ein": "411498659", "state": "MN"}'

# Run tests
pytest agents/grant_writer_v2/tests/test_layer2.py -v

# Key env vars
V2_L2_MAX_ITERATIONS=10     # how many agent loop rounds
V2_L2_MAX_PAGES=25          # max pages the agent can fetch
V2_L2_MAX_COST_USD=0.50     # per-foundation cost ceiling
V2_MODEL_LAYER2_AGENT=openai/gpt-4o          # crawl agent model
V2_MODEL_LAYER2_PROGRAM_IDENTIFIER=openai/gpt-4o
V2_MODEL_LAYER2_RULE_EVALUATOR=openai/gpt-4o-mini
LANGSMITH_TRACING=false     # keep this off — expired key causes 2min delays
```

---

## Validated Test Foundations

| Foundation | EIN | Result | Notes |
|---|---|---|---|
| The James Foundation | 411498659 | `completed / VALID / 3 programs` | Spring/Fall cycles, Arts |
| Wold Foundation | 742406069 | `completed / VALID / 2 programs` | Spring + Fall grant cycles |
| William T Grant Foundation | 131624021 | `needs_review / UNKNOWN_BOT_PROTECTED` | Cloudflare 403 blocks all crawling |
| Ford Foundation | 131684331 | `completed / VALID / 4 programs` | Large site; 1 program INVALID (closed fellowship) |
| Bill & Melinda Gates Foundation | 562618866 | `needs_review / UNKNOWN_JS_RENDERED` | JS-rendered SPA; static HTML has no grant content |
