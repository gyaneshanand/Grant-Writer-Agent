# The Grant Portal — AI Agent Suite

A production-ready, modular AI-powered backend for **The Grant Portal (TGP)** — combining an intelligent conversational chatbot, automated grant writing pipeline, and specialized data-collection agents into a single, scalable FastAPI application.

**Version:** 1.0.0  
**Status:** Production-ready  
**Last Updated:** May 2026

---

## ✨ Key Features

| Capability | Status | Description |
|---|---|---|
| **Smart Chatbot** | ✅ Fully Implemented | LangGraph state-machine with intent classification, FAQ RAG (ChromaDB), real-time SQL grant search, entity extraction, conversation memory, and multi-turn support |
| **Grant Writer Pipeline** | ✅ Fully Implemented | 4-step end-to-end pipeline — scrape → analyse → generate → enrich metadata with LLM-powered content generation |
| **Organisation Analyser** | ✅ Fully Implemented | Profiles organizations from their websites to enable personalized grant applications |
| **Metadata Generator** | ✅ Fully Implemented | Produces SEO-optimized, structured JSON metadata for every grant with deadline, amount, and eligibility extraction |
| **Real-time Grant Search** | ✅ Fully Implemented | MySQL-backed SQL search with multi-dimensional filtering (interest, location, eligibility) |

---

## 🤖 Chatbot Architecture

The chatbot is built on **LangGraph** with a robust state machine that routes every user message through multiple intelligent processing layers:

```
detect_follow_up → classify_query → [intent router] → 
  ├─ grant_search → entity_extraction → sql_search → response_formatter
  ├─ product_navigation → faq_rag → response_formatter
  ├─ account_support → faq_rag → response_formatter
  ├─ eligibility_assessment → faq_rag → response_formatter
  ├─ application_guidance → faq_rag → response_formatter
  ├─ greeting → static_handler → response_formatter
  └─ other → fallback_handler → response_formatter
       ↓
save_conversation → apply_user_cta → END
```

### Conversation Modes

The chatbot supports **two conversation modes**:

1. **Stateless Mode** (Default)
   - Frontend sends full conversation history with each request
   - Server processes message with provided context
   - Server returns response + updated history
   - No server-side session storage required
   - ✅ Ideal for: Distributed systems, edge deployments, stateless scaling

2. **Stateful Mode** (Database-backed)
   - Frontend sends only session_id + message
   - Server loads conversation history from MySQL
   - Server processes and saves both turns to database
   - ✅ Ideal for: Long-running sessions, multi-device sync, analytics

**Both modes:** Always save conversation to MySQL for audit logs and analytics (when configured).

### Intent Classification Routes

| Intent | Handler | What It Does |
|---|---|---|
| `grant_search` | Entity Extraction → SQL Search → Response Formatter | Extracts interests, locations & eligibility from natural language, runs parameterized SQL against TGP database, formats results with grant count + 2-sentence summary |
| `product_navigation` | FAQ RAG + LLM | Answers questions about TGP pricing, plans, features, and product capabilities |
| `account_support` | FAQ RAG + LLM | Handles login, billing, password reset, and subscription queries |
| `eligibility_assessment` | FAQ RAG + LLM | Answers "Am I eligible?" style questions with FAQ retrieval |
| `application_guidance` | FAQ RAG + LLM | Guides users on application process, required documents, and grant writing tips |
| `greeting` | Static handler | Welcomes the user and sets context |
| `other` | Fallback handler | Graceful fallback for out-of-scope queries with product CTA |

### Key Chatbot Components

- **Intent Classification** — LLM-powered classifier that routes messages to appropriate handlers
- **Follow-up Detection** — Detects conversational context and multi-turn queries
- **FAQ RAG** — 95+ curated Q&A pairs ingested into ChromaDB; semantic search + LLM re-ranking
- **SQL Grant Search** — Async MySQL queries with multi-dimensional filtering (interest, location, eligibility)
- **Entity Extraction** — LLM-powered extraction of search parameters (interests, locations, eligibility) with slug resolution
- **Response Formatting** — Contextual response formatting with user-type-specific CTAs (guest/paid/unpaid)
- **Conversation Persistence** — Stores chat history to MySQL for multi-turn context and analytics
- **User Type CTAs** — Different call-to-action messaging based on user subscription level

---

## 🔧 Grant Writer Pipeline

A 4-step AI pipeline for automated grant content generation. Each step is powered by targeted LLM prompts with strict JSON schemas to keep outputs structured and consistent.

### AI Steps (What Each Model Does)

1. **Grant Data Collection AI** (`grant_data_collector.py`)
  - Scrapes foundation pages with Trafilatura + BeautifulSoup
  - Uses GPT (`gpt-4o-mini`) to extract **active** grants only
  - Returns structured JSON fields (name, eligibility, amount, deadline, contact, summary)

2. **Organisation Analysis AI** (`organisation_data_collector.py`)
  - Crawls mission/about/contact pages
  - Uses GPT (`gpt-4o-mini`) to extract org name, mission, background, contact info
  - Consolidates multi-page data into a single org profile

3. **Grant Writer AI** (`grant_writer.py`)
  - Filters expired grants based on deadline signals
  - Generates **one 500-word consolidated opportunity description**
  - Adds sectioned, professional formatting for directory publication

4. **Metadata AI** (`grant_metadata_writer.py`)
  - Single GPT call to produce **6 SEO fields**
  - Enforces character/word limits and returns pure JSON

### End-to-End Pipeline (`/api/v1/pipeline/complete`)

This endpoint runs all four AI steps in sequence and returns a full, ready-to-publish package.

**Request Example:**
```json
{
  "foundation_url": "https://example.org/grants",
  "max_grants": 10,
  "include_org_data": true
}
```

**Response Shape:**
```json
{
  "grants_data": [ { "grant_name": "...", "proposal_deadline": "..." } ],
  "organization_data": { "org_name": "...", "mission": "..." },
  "consolidated_description": "...",
  "metadata": {
   "opportunity_title": "...",
   "meta_title": "...",
   "opportunity_teaser": "..."
  }
}
```

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
│   │   ├── data_collection_controller.py    #    /api/v1/grant-data-collection/*
│   │   ├── content_generation_controller.py #    /api/v1/grant-content-generation/*
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

All endpoints are versioned (`/api/v1`) and return JSON responses.

### Chatbot Endpoints

| Method | Endpoint | Status | Description |
|---|---|---|---|
| `POST` | `/api/v1/chatbot/chat` | ✅ Live | Send a message and receive AI-powered response (supports both stateless and stateful modes) |

**Request Format:**
```json
{
  "message": "Find education grants in California",
  "session_id": "user-123-session",
  "user_id": "user-123",
  "user_type": "paid",  // "guest", "unpaid", or "paid"
  "conversation_mode": "stateless",  // "stateless" or "stateful"
  "conversation_history": [  // Only for stateless mode
    {
      "role": "assistant",
      "content": "Welcome to TGP!",
      "query_type": "greeting",
      "extracted_entities": null
    }
  ]
}
```

**Response Format:**
```json
{
  "session_id": "user-123-session",
  "response": "I found 5 education grants available in California...",
  "query_type": "grant_search",
  "extracted_entities": {
    "interests": ["education"],
    "locations": ["california"],
    "eligibility": null
  },
  "conversation_history": [
    {
      "role": "assistant",
      "content": "I found 5 education grants...",
      "query_type": "grant_search",
      "extracted_entities": { ... }
    }
  ]
}
```

### Grant Data Collection Endpoints

| Method | Endpoint | Status | Description |
|---|---|---|---|
| `POST` | `/api/v1/grant-data-collection/grants` | ✅ Live | Extract grant data from a foundation URL |
| `POST` | `/api/v1/grant-data-collection/organization` | ✅ Live | Analyze an organization's website and extract mission/values |
| `POST` | `/api/v1/grant-data-collection/find-url` | ✅ Live | Find an official organization URL using the AI URL Finder |

### Content Generation Endpoints

| Method | Endpoint | Status | Description |
|---|---|---|---|
| `POST` | `/api/v1/grant-content-generation/grant-description` | ✅ Live | Generate consolidated grant descriptions using OpenAI |
| `POST` | `/api/v1/grant-content-generation/metadata` | ✅ Live | Extract structured metadata (deadlines, amounts, eligibility) from grant text |

### End-to-End Pipeline

| Method | Endpoint | Status | Description |
|---|---|---|---|
| `POST` | `/api/v1/pipeline/complete` | ✅ Live | Run the full 4-step pipeline (collect → analyze → generate → enrich) |

### Health & Status Endpoints

| Method | Endpoint | Status | Description |
|---|---|---|---|
| `GET` | `/` | ✅ Live | Quick health check with endpoint directory |
| `GET` | `/health` | ✅ Live | Detailed health status + configuration info |

### Interactive Documentation

- **Swagger UI:** `http://localhost:8000/docs`
- **ReDoc:** `http://localhost:8000/redoc`

Both provide live testing of all endpoints with request/response schemas.

---

## 🚀 Quick Start

### Prerequisites

- **Python 3.12+** — [Download](https://www.python.org/downloads/)
- **OpenAI API key** — [Get one](https://platform.openai.com/api-keys)
- *(Optional)* **MySQL database** — For live grant search (configure via `DATABASE_URL`)
- *(Optional)* **LangSmith API key** — For observability ([smith.langchain.com](https://smith.langchain.com))

### Installation (5 minutes)

```bash
# 1. Clone the repository
git clone https://github.com/gyaneshanand/Grant-Writer-Agent.git
cd Grant-Writer-Agent

# 2. Create virtual environment
python3.12 -m venv venv
source venv/bin/activate      # macOS / Linux
# or: venv\Scripts\activate   # Windows

# 3. Install dependencies
pip install --upgrade pip
pip install -r requirements.txt

# 4. Configure environment
cp .env.example .env
# Edit .env and add your API keys (OPENAI_API_KEY is required)
nano .env
```

### Running the API

**Option 1: Direct Python (Development)**
```bash
python main.py
# Runs at http://localhost:8000
```

**Option 2: Uvicorn (Recommended for development)**
```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
# Runs at http://localhost:8000
```

**Option 3: Gunicorn (Production)**
```bash
gunicorn -c gunicorn.conf.py main:app
# Runs with production workers
```

**Option 4: Provided Scripts**
```bash
# Development server with auto-reload
./start_api.sh

# Production with Gunicorn
./start_production.sh

# Background service (for cPanel/VPS)
./start_background.sh

# Check server status
./start_server.sh status
```

### First Request

```bash
# Health check
curl http://localhost:8000/health

# Chat with the chatbot
curl -X POST http://localhost:8000/api/v1/chatbot/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Find education grants in California",
    "session_id": "demo-123",
    "user_id": "user-456",
    "user_type": "paid",
    "conversation_mode": "stateless",
    "conversation_history": []
  }'

# Interactive docs
open http://localhost:8000/docs
```

---

## ⚙️ Configuration

All configuration is managed via environment variables in `.env` (see `.env.example` for template).

### Core Configuration

| Variable | Required | Default | Description |
|---|---|---|---|
| `OPENAI_API_KEY` | **Yes** | — | OpenAI API key for LLM functionality (GPT-4 / GPT-3.5-turbo) |
| `APP_ENV` | No | `development` | Environment: `development`, `staging`, `production` |
| `APP_HOST` | No | `0.0.0.0` | Server host binding |
| `APP_PORT` | No | `8000` | Server port |
| `APP_DEBUG` | No | `true` | Enable debug mode (disable in production) |
| `APP_RELOAD` | No | `true` | Auto-reload on file changes (development only) |

### Chatbot Configuration

| Variable | Required | Default | Description |
|---|---|---|---|
| `DATABASE_URL` | No | — | MySQL connection for grant search (e.g., `mysql+aiomysql://user:pass@localhost:3306/tgp`) |
| `VECTOR_STORE_PROVIDER` | No | `chroma` | Vector store: `chroma` (recommended) or `pinecone` |
| `CHROMA_PATH` | No | `agents/chatbot/data/chroma_db` | Path to ChromaDB persistent storage |
| `MAX_CONVERSATION_HISTORY` | No | `10` | Maximum conversation turns to retain in context |
| `MAX_SEARCH_RESULTS` | No | `10` | Maximum grant results per search query |
| `SUPPORT_EMAIL` | No | `support@thegrantportal.com` | Support email for error messages |

### Optional Services

| Variable | Required | Default | Description |
|---|---|---|---|
| `TAVILY_API_KEY` | No | — | Tavily API key for enhanced web search capability |
| `PINECONE_API_KEY` | No | — | Pinecone API key (for Pinecone vector store) |
| `PINECONE_INDEX_NAME` | No | `tgp-product-docs` | Pinecone index name |

### Observability & Tracing

| Variable | Required | Default | Description |
|---|---|---|---|
| `LANGSMITH_TRACING` | No | `false` | Enable LangSmith tracing (set to `true` for tracing) |
| `LANGSMITH_ENDPOINT` | No | `https://api.smith.langchain.com` | LangSmith endpoint |
| `LANGSMITH_API_KEY` | No | — | LangSmith API key |
| `LANGSMITH_PROJECT` | No | `grant-writer-agent` | LangSmith project name |

### Quick Setup

```bash
# Copy the example environment file
cp .env.example .env

# Edit with your keys
nano .env

# Key variables to update:
# - OPENAI_API_KEY (required)
# - DATABASE_URL (optional, for grant search)
# - LANGSMITH_TRACING (optional, for monitoring)
```

---

## 🛠️ Tech Stack

| Layer | Technology | Version |
|---|---|---|
| **Framework** | FastAPI, Uvicorn | 0.104.1, 0.24.0 |
| **AI / LLM** | OpenAI GPT, LangChain, LangGraph | 0.3.25, 0.4.5 |
| **State Machine** | LangGraph | 0.4.5 |
| **Vector Store** | ChromaDB (default), Pinecone (optional) | 1.0.9+ |
| **Database** | MySQL | Via `aiomysql` 0.2.0 + `databases` 0.9.0 |
| **Web Scraping** | Trafilatura, BeautifulSoup4, Requests | 1.12.0+, 4.12.0+, 2.31.0 |
| **Validation** | Pydantic v2 | 2.9.2 |
| **Monitoring** | LangSmith | 0.3.45 |
| **Server** | Gunicorn | (Production) |

### Architecture Overview

```
┌─────────────────────────────────────────────────┐
│         FastAPI Application (main.py)           │
├─────────────────────────────────────────────────┤
│                 API Routers                     │
│  ┌──────────────────────────────────────────┐  │
│  │ • Chatbot Router                         │  │
│  │ • Data Collection Router                 │  │
│  │ • Content Generation Router              │  │
│  │ • Pipeline Router                        │  │
│  └──────────────────────────────────────────┘  │
├─────────────────────────────────────────────────┤
│              AI Agents Layer                    │
│  ┌──────────────────────────────────────────┐  │
│  │ • Chatbot (LangGraph)                   │  │
│  │ • Grant Writer Agent                    │  │
│  │ • Data Collection Agent                 │  │
│  │ • Metadata Generator                    │  │
│  │ • Organization Analyzer                 │  │
│  └──────────────────────────────────────────┘  │
├─────────────────────────────────────────────────┤
│           External Services                     │
│  ┌──────────────────────────────────────────┐  │
│  │ • OpenAI API (LLM)                       │  │
│  │ • MySQL Database (Grant Search)          │  │
│  │ • ChromaDB (Vector Store)                │  │
│  │ • LangSmith (Tracing)                    │  │
│  └──────────────────────────────────────────┘  │
└─────────────────────────────────────────────────┘
```

---

## 🚢 Deployment

### Local Development

```bash
./start_api.sh
# Starts with auto-reload at http://localhost:8000
```

### Staging / Production

```bash
# Using Gunicorn (production-grade)
./start_production.sh

# Or manually
gunicorn -c gunicorn.conf.py main:app
```

**Gunicorn Configuration** (`gunicorn.conf.py`):
- Workers: Auto-calculated based on CPU cores
- Worker class: `uvicorn.workers.UvicornWorker`
- Bind: `0.0.0.0:8000`
- Access logs: Enabled
- Reload: Disabled (production)

### Docker (Future)

A `docker-compose.yml` can be added for containerized deployment with MySQL + API:

```yaml
version: '3.8'
services:
  api:
    build: .
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=mysql+aiomysql://user:pass@db:3306/tgp
    depends_on:
      - db
  db:
    image: mysql:8.0
    environment:
      - MYSQL_ROOT_PASSWORD=root
      - MYSQL_DATABASE=tgp
```

### Background Service (VPS / cPanel)

```bash
# Start as background process
./start_background.sh

# Check status
./start_server.sh status

# Stop the service
./stop_server.sh
```

### Environment for Production

Before deploying to production:

```bash
# 1. Update .env to production settings
APP_ENV=production
APP_DEBUG=false
APP_RELOAD=false
LANGSMITH_TRACING=true  # Enable monitoring

# 2. Ensure all required variables are set
# OPENAI_API_KEY, DATABASE_URL, etc.

# 3. Start the production server
./start_production.sh
```

---

## 🔍 Monitoring & Observability

### Built-in LangSmith Integration

Enable tracing by setting `LANGSMITH_TRACING=true` in `.env`:

```bash
LANGSMITH_TRACING=true
LANGSMITH_API_KEY=your-api-key
LANGSMITH_PROJECT=grant-writer-agent
```

LangSmith provides:
- 📊 Full trace visibility for every LLM call
- 💰 Token usage and cost tracking
- ⏱️ Latency profiling per node
- 🔍 Debug-level inspection of prompts and completions
- 📈 Performance analytics and trends

### Logs

Application logs are stored in `logs/` directory with automatic rotation:

```bash
tail -f logs/app.log
```

Log levels controlled via `APP_DEBUG`:
- `development` → DEBUG level
- `production` → INFO level

---

## 🛡️ Security

- ✅ **No Hardcoded Credentials** — All API keys loaded from environment variables
- ✅ **Protected `.env`** — Added to `.gitignore` to prevent accidental commits
- ✅ **CORS Configured** — Configurable for production with specific allowed origins
- ✅ **Sensitive Data** — Logs filtered to avoid exposing API keys or user data
- ✅ **Database Connections** — Async connections pooled for efficiency and security
- ✅ **Input Validation** — All API inputs validated via Pydantic schemas

### Best Practices for Production

1. **Restrict CORS Origins** — Update `main.py` to allow only your domain:
   ```python
   allow_origins=["https://thegrantportal.com", "https://admin.thegrantportal.com"]
   ```

2. **Enable HTTPS** — Use a reverse proxy (Nginx) or load balancer (AWS ALB)

3. **Rate Limiting** — Consider adding rate limiting middleware (future enhancement)

4. **API Key Rotation** — Rotate OpenAI API keys periodically

5. **Database Security** — Use strong passwords and restrict MySQL access to API subnet only

---

## 🐛 Troubleshooting

### API Won't Start

```bash
# Check Python version
python --version  # Should be 3.12+

# Check dependencies
pip list | grep fastapi

# Verify .env is set up
cat .env | grep OPENAI_API_KEY

# Try verbose logging
APP_DEBUG=true python main.py
```

### Chatbot Returns Empty Results

```bash
# 1. Verify database connectivity
mysql -u user -p -h localhost tgp -e "SELECT COUNT(*) FROM grants;"

# 2. Check ChromaDB initialization
ls -la agents/chatbot/data/chroma_db/

# 3. Ensure FAQ ingestion completed
python -m agents.chatbot.ingest_faqs
```

### LangSmith Tracing Not Working

```bash
# Verify LangSmith variables
grep LANGSMITH .env

# Test API key
curl -X POST https://api.smith.langchain.com/api/sessions \
  -H "X-API-Key: $LANGSMITH_API_KEY"
```

### Performance Issues

- Increase `MAX_CONVERSATION_HISTORY` for better context
- Enable `LANGSMITH_TRACING` to identify slow nodes
- Check MySQL indexes on `grants` table: `interests`, `location`, `eligibility`
- Consider using Pinecone for vector store at scale

---

## 📖 Development

### Adding a New Endpoint

1. **Create the agent logic** in `agents/`
2. **Create a service** in `api/services/`
3. **Create a controller** in `api/controllers/`
4. **Register the router** in `main.py`

Example: Adding a `/grant-review` endpoint

```python
# agents/grant_reviewer.py
async def review_grant(grant_text: str) -> dict:
    """Review grant for quality and completeness"""
    # Implementation here
    pass

# api/services/grant_review_service.py
async def review_grant_application(grant_text: str):
    return await agents.grant_reviewer.review_grant(grant_text)

# api/controllers/grant_review_controller.py
@router.post("/grant-review")
async def review_grant(request: GrantReviewRequest):
    result = await grant_review_service.review_grant_application(request.grant_text)
    return GrantReviewResponse(**result)

# main.py
from api.controllers.grant_review_controller import router as grant_review_router
app.include_router(grant_review_router, prefix="/api/v1")
```

### Running Tests

```bash
# Create tests in tests/ directory
pytest tests/ -v

# With coverage
pytest tests/ --cov=agents --cov=api
```

### LangGraph Debugging

The chatbot's LangGraph state machine can be debugged:

```python
# In agents/chatbot/graph/main_graph.py
graph.invoke(state, debug=True)
```

This prints all node transitions and state updates.

---

## 🤝 Contributing

We welcome contributions! To contribute:

1. **Fork** the repository
2. **Create a feature branch**: `git checkout -b feature/amazing-feature`
3. **Make your changes** and test thoroughly
4. **Commit**: `git commit -m 'Add amazing feature'`
5. **Push**: `git push origin feature/amazing-feature`
6. **Open a Pull Request** with a clear description

### Contribution Guidelines

- Follow PEP 8 for Python code style
- Add docstrings to all functions and classes
- Test new features with `pytest`
- Update README if adding new features
- Keep commits atomic and focused

### Reporting Issues

Found a bug? Please open an issue with:
- Clear description of the problem
- Steps to reproduce
- Expected vs. actual behavior
- Environment details (Python version, OS, etc.)

---

## 📄 License

This project is part of **The Grant Portal** ecosystem.

---

## 🙏 Acknowledgements

Built with ❤️ using:

- [**FastAPI**](https://fastapi.tiangolo.com/) — Modern, fast web framework
- [**LangChain**](https://www.langchain.com/) & [**LangGraph**](https://langchain-ai.github.io/langgraph/) — AI orchestration
- [**OpenAI**](https://openai.com/) — Advanced language models (GPT-4, GPT-3.5-turbo)
- [**ChromaDB**](https://www.trychroma.com/) — Vector database for RAG
- [**LangSmith**](https://smith.langchain.com/) — AI observability & debugging
- [**MySQL**](https://www.mysql.com/) — Reliable database
- [**Trafilatura**](https://trafilatura.readthedocs.io/) & [**BeautifulSoup**](https://www.crummy.com/software/BeautifulSoup/) — Web scraping

---

## 📞 Support

- 📖 **Documentation** — See `/docs` endpoint or `.md` files in `docs/`
- 🐛 **Issues** — Report bugs on GitHub
- 💬 **Discussions** — Join our community discussions
- 📧 **Email** — Contact `support@thegrantportal.com`

---

## 🎯 Roadmap

- [ ] **Real-time Updates** — WebSocket support for live grant feeds
- [ ] **Advanced Filtering** — Multi-criteria grant matching with ML
- [ ] **Multi-language Support** — Translate grants and FAQs
- [ ] **Grant Timeline AI** — Predict funding cycles and deadlines
- [ ] **Application Analytics** — Track success rates by grant type
- [ ] **Integration with LMS** — Connect with educational platforms

---

**Built for [The Grant Portal](https://thegrantportal.com) — Empowering organizations to find and win grants.**

---

**Last Updated:** May 2026 | **Version:** 1.0.0 | **Status:** ✅ Production-Ready