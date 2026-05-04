# Grant Writer v2

AI-powered foundation intelligence pipeline. Produces structured, SEO-ready grant program listings from raw foundation data.

## Pipeline

```
Layer 0  →  Laravel-side prescreening (priority scoring — NOT built here)
Layer 1  →  URL Discovery          (SerpAPI + deterministic verifier + LLM reranker)
Layer 2  →  Grant Detection        (LangGraph agentic crawl + 6-rule evaluation)
Layer 3  →  Org Profile Extraction (LLM extraction from L2 corpus + about/contact pages)
Layer 4  →  Grant Writer           (per-program structured extraction + consolidator)
Layer 5  →  Metadata & SEO         (6 SEO fields + filter derivation + slug + dedup)
```

## Execution Model

**This service is API-driven.** Laravel is the orchestrator — it calls endpoints per foundation, per layer, in priority order. There is no Python-side scheduler.

Each layer is **independently runnable**: `POST /api/v1/grant-writer-v2/layer/{N}/run` with a `FoundationInput` body. The layer reads its prerequisites from the DB and returns a structured response.

## API Endpoints

| Method | Endpoint | Purpose |
|---|---|---|
| POST | `/api/v1/grant-writer-v2/layer/{1-5}/run` | Run one layer for one foundation |
| POST | `/api/v1/grant-writer-v2/pipeline/run` | Run a range of layers in one call |

## Setup

```bash
# 1. Install new dependencies
pip install -r requirements.txt

# 2. Set environment variables (copy .env.example → .env, fill in)
OPENROUTER_API_KEY=...
SERPAPI_API_KEY=...

# 3. Apply DB migrations
python -m agents.grant_writer_v2.scripts.apply_migrations

# 4. Start the API
uvicorn main:app --reload
```

## Directory Structure

```
agents/grant_writer_v2/
├── config.py                  # Settings (pydantic-settings, reads .env)
├── vocabularies/              # 9 controlled-vocabulary YAML files
├── core/                      # Shared infra: DB, HTTP, LLM (OpenRouter), audit
├── schemas/                   # Cross-cutting Pydantic models
├── layer1_url_discovery/      # async def run(foundation) → Layer1Output
├── layer2_grant_detection/    # LangGraph StateGraph → Layer2Output
├── layer3_org_extraction/     # async def run(foundation) → OrgProfile
├── layer4_grant_writer/       # async def run(foundation) → Layer4Output
├── layer5_metadata_seo/       # async def run(foundation) → Layer5Output
├── orchestrator.py            # Sequences layers; called by API service
├── db/migrations/             # 3 SQL migration files
├── scripts/apply_migrations.py
├── tests/
└── docs/                      # Rules_Reference.md, Schema_Reference.md
```

## Model Selection

Every LLM call reads its model from `core/models.py` MODEL_REGISTRY. Override per use-case via env:

```bash
V2_MODEL_LAYER2_AGENT=anthropic/claude-sonnet-4     # strong reasoning for crawl agent
V2_MODEL_LAYER4_PER_PROGRAM=openai/gpt-4o           # structured extraction
V2_MODEL_LAYER1_RERANKER=openai/gpt-4o-mini         # cheap rerank
```

All models route through OpenRouter — swap any provider without code changes.

## L2 Cost Safeguards

Layer 2 is agentic. Hard caps prevent runaway costs:

| Cap | Default | Override |
|---|---|---|
| Max iterations | 12 | `V2_L2_MAX_ITERATIONS` |
| Max pages | 25 | `V2_L2_MAX_PAGES` |
| Max PDFs | 5 | `V2_L2_MAX_PDFS` |
| Max bytes | 8 MB | `V2_L2_MAX_BYTES` |
| Cost ceiling | $0.50 | `V2_L2_MAX_COST_USD` |

## Docs

- [Implementation Plan](../../docs/plans/grant_writer_v2_implementation_plan.md)
- [Rules Reference](docs/Rules_Reference.md)
- [Schema Reference](docs/Schema_Reference.md)
