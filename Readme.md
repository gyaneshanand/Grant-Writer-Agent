# The Grant Portal — AI Agent Suite

A modular, AI-powered backend for **The Grant Portal (TGP)** — combining an intelligent chatbot, a grant writing pipeline, and specialised data-collection agents into a single FastAPI application.

---

## ✨ Highlights

| Capability | Description |
|---|---|
| **Smart Chatbot** | LangGraph state-machine with intent classification, FAQ RAG (ChromaDB), real-time SQL grant search, entity extraction, and conversation memory |
| **Grant Writer Pipeline** | 4-step pipeline — scrape → analyse → generate → enrich metadata |
| **Organisation Analyser** | Profiles organisations from their website to personalise grant applications |
| **Metadata Generator** | Produces SEO-optimised, structured JSON metadata for every grant |

---

## 🤖 Chatbot Architecture

The chatbot is built on **LangGraph** and routes every user message through an intent-classification layer powered by OpenAI GPT, then dispatches to specialised handler nodes:

```
detect_follow_up → classify_query → [route] → handler → save_conversation → END
```

### Intent Routes

| Intent | Handler | What It Does |
|---|---|---|
| `greeting` | Static handler | Welcomes the user |
| `grant_search` | Entity Extraction → SQL Search → Response Formatter | Extracts interests, locations & eligibility from natural language, runs parameterised SQL against the TGP MySQL database, and formats results |
| `product_navigation` | FAQ RAG + LLM | Answers questions about TGP pricing, plans, features using ChromaDB vector search over curated FAQs |
| `account_support` | FAQ RAG + LLM | Handles login, billing, password, cancellation queries |
| `eligibility_assessment` | FAQ RAG + LLM | Answers "Am I eligible?" style questions |
| `application_guidance` | FAQ RAG + LLM | Guides users on how to apply, required documents, grant writer directory |
| `other` | Fallback handler | Graceful fallback for out-of-scope queries |

### Key Chatbot Components

- **FAQ RAG** — 95+ curated Q&A pairs ingested into ChromaDB; semantic search + LLM re-ranking for precise answers
- **SQL Grant Search** — Async MySQL queries against the live TGP database with multi-dimensional filtering (interest, location, eligibility)
- **Entity Extraction** — LLM-powered extraction of grant search entities (interests, locations, eligibility criteria) with slug resolution
- **Follow-up Detection** — Detects conversational follow-ups and carries context forward
- **Conversation History** — Persists chat history to MySQL for multi-turn context

---

## 🔧 Grant Writer Pipeline

A 4-step AI pipeline for automated grant content generation:

1. **Grant Data Collection** (`grant_data_collector.py`) — Scrapes foundation websites using Trafilatura & BeautifulSoup to extract grant details
2. **Organisation Analysis** (`organisation_data_collector.py`) — Profiles the applicant organisation from its website
3. **Content Generation** (`grant_writer.py`) — Generates compelling, tailored grant application narratives using GPT
4. **Metadata Generation** (`grant_metadata_writer.py`) — Extracts structured metadata (deadlines, amounts, eligibility, contact info) as JSON

### Additional Agents

- **Organisation URL Finder** (`organisation_url_finder_agent.py`) — Discovers and validates organisation URLs for downstream analysis

---

## 🏗️ Project Structure

```
Grant-Writer-Agent/
├── main.py                                  # FastAPI entry point & lifespan
├── requirements.txt                         # Python dependencies
├── .env.example                             # Environment variable template
│
├── agents/                                  # All AI agents
│   ├── chatbot/                             # ── Chatbot Agent ──
│   │   ├── config.py                        #    Settings (model, DB, vector store)
│   │   ├── ingest.py                        #    Document ingestion for RAG
│   │   ├── ingest_faqs.py                   #    FAQ ingestion into ChromaDB
│   │   ├── graph/
│   │   │   └── main_graph.py                #    LangGraph state machine
│   │   ├── models/
│   │   │   ├── state.py                     #    Graph state schema
│   │   │   ├── request.py                   #    API request models
│   │   │   └── response.py                  #    API response models
│   │   ├── nodes/
│   │   │   ├── classifier.py                #    Intent classification
│   │   │   ├── follow_up.py                 #    Follow-up detection
│   │   │   ├── entity_extraction.py         #    Entity extraction & slug resolution
│   │   │   ├── search.py                    #    SQL grant search
│   │   │   ├── faq_rag.py                   #    FAQ RAG retrieval
│   │   │   ├── handlers.py                  #    Intent handlers
│   │   │   ├── product_navigation.py        #    Product/pricing handler
│   │   │   ├── response.py                  #    Response formatter
│   │   │   └── conversation.py              #    Conversation persistence
│   │   ├── services/
│   │   │   ├── llm.py                       #    OpenAI LLM client
│   │   │   ├── database.py                  #    Async MySQL connection
│   │   │   └── vector_store.py              #    ChromaDB / Pinecone store
│   │   └── data/
│   │       └── faqs.json                    #    Curated FAQ dataset
│   │
│   ├── grant_writer.py                      # ── Grant Writer Agent ──
│   ├── grant_data_collector.py              # ── Grant Data Collector ──
│   ├── grant_metadata_writer.py             # ── Metadata Writer Agent ──
│   ├── organisation_data_collector.py       # ── Org Data Collector ──
│   └── organisation_url_finder_agent.py     # ── Org URL Finder Agent ──
│
├── api/                                     # FastAPI layer
│   ├── config/
│   │   ├── settings.py                      #    App settings
│   │   └── langsmith_setup.py               #    LangSmith tracing setup
│   ├── controllers/
│   │   ├── chatbot_controller.py            #    /api/v1/chatbot/*
│   │   ├── data_collection_controller.py    #    /api/v1/data-collection/*
│   │   ├── content_generation_controller.py #    /api/v1/content-generation/*
│   │   └── pipeline_controller.py           #    /api/v1/pipeline/*
│   ├── services/                            #    Business logic layer
│   └── models/
│       └── schemas.py                       #    Pydantic schemas
│
├── ui/                                      # Frontend assets
├── docs/                                    # Documentation
├── scripts/                                 # Utility scripts
└── logs/                                    # Application logs
```

---

## 📚 API Endpoints

### Chatbot

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/v1/chatbot/chat` | Send a message and receive an AI-powered response |

### Grant Data Collection

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/v1/data-collection/grants` | Extract grant data from a foundation URL |
| `POST` | `/api/v1/data-collection/organization` | Analyse an organisation's website |

### Content Generation

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/v1/content-generation/grant-description` | Generate a consolidated grant description |
| `POST` | `/api/v1/content-generation/metadata` | Extract structured metadata from grant text |

### Full Pipeline

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/v1/pipeline/complete` | Run the end-to-end 4-step grant pipeline |

### Health

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/` | Quick health check |
| `GET` | `/health` | Detailed health & configuration status |

> Interactive API docs are available at `/docs` (Swagger UI) and `/redoc` (ReDoc).

---

## 🚀 Quick Start

### Prerequisites

- Python 3.12+
- OpenAI API key
- *(Optional)* MySQL database for live grant search
- *(Optional)* LangSmith API key for tracing

### Setup

```bash
# Clone
git clone https://github.com/gyaneshanand/Grant-Writer-Agent.git
cd Grant-Writer-Agent

# Virtual environment
python -m venv venv
source venv/bin/activate      # macOS / Linux
# venv\Scripts\activate       # Windows

# Dependencies
pip install -r requirements.txt

# Environment
cp .env.example .env
# Edit .env with your API keys
```

### Run

```bash
python main.py
# or
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

The API will be available at `http://localhost:8000` — docs at `http://localhost:8000/docs`.

---

## ⚙️ Configuration

All configuration is managed via environment variables (`.env`).

| Variable | Required | Default | Description |
|---|---|---|---|
| `OPENAI_API_KEY` | **Yes** | — | OpenAI API key |
| `DATABASE_URL` | No | — | MySQL connection string for grant search |
| `VECTOR_STORE_PROVIDER` | No | `chroma` | `chroma` or `pinecone` |
| `CHROMA_PATH` | No | `agents/chatbot/data/chroma_db` | Path to ChromaDB store |
| `LANGSMITH_TRACING` | No | `false` | Enable LangSmith tracing |
| `LANGSMITH_API_KEY` | No | — | LangSmith API key |
| `LANGSMITH_PROJECT` | No | `grant-writer-agent` | LangSmith project name |
| `APP_ENV` | No | `development` | Environment |
| `APP_HOST` | No | `0.0.0.0` | Server host |
| `APP_PORT` | No | `8000` | Server port |
| `MAX_CONVERSATION_HISTORY` | No | `10` | Chat history turns retained |
| `MAX_SEARCH_RESULTS` | No | `10` | Max grants returned per search |

---

## 🛠️ Tech Stack

| Layer | Technology |
|---|---|
| Framework | FastAPI, Uvicorn |
| AI / LLM | OpenAI GPT, LangChain, LangGraph |
| Vector Store | ChromaDB (default), Pinecone (optional) |
| Database | MySQL (async via `aiomysql` + `databases`) |
| Web Scraping | Trafilatura, BeautifulSoup, Requests |
| Monitoring | LangSmith |
| Validation | Pydantic v2 |

---

## 🔍 Monitoring

Built-in **LangSmith** integration provides:

- Full trace visibility for every LLM call
- Token usage and cost tracking
- Latency profiling per node
- Debug-level inspection of prompts and completions

Enable by setting `LANGSMITH_TRACING=true` in `.env`.

---

## 🛡️ Security

- All API keys loaded from environment variables — never hardcoded
- `.gitignore` configured to exclude `.env`, `venv/`, logs, and data stores
- CORS middleware configurable for production

---

## 🙏 Acknowledgements

- [FastAPI](https://fastapi.tiangolo.com/) — Web framework
- [LangChain](https://langchain.com/) & [LangGraph](https://langchain-ai.github.io/langgraph/) — AI orchestration
- [OpenAI](https://openai.com/) — Language models
- [ChromaDB](https://www.trychroma.com/) — Vector database
- [LangSmith](https://smith.langchain.com/) — Observability

---

**Built for [The Grant Portal](https://thegrantportal.com)**