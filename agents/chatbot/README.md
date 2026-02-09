# TGP Chatbot Agent

Conversational AI for grant discovery using **LangGraph**, **ChromaDB (RAG)**, and **MySQL**.

## 🧠 Architecture

```
User Message → Classifier → Entity Extraction → Grant Search / RAG → Response
```

**Nodes:**
- **Classifier**: Intent detection (greeting, grant_search, product_navigation, etc.)
- **Entity Extraction**: Parses interests, locations, eligibility from queries
- **Grant Search**: SQL-based search returning grant count + 2-sentence summary
- **Product Navigation**: RAG over TGP website content
- **Handlers**: Template responses for greetings, support, guidance

## 🚀 Features

- **Grant Search**: "Find education grants in California" → Returns count + summary
- **User Type CTA**: Different CTAs for guest/unpaid/paid users
- **RAG Q&A**: Answers about TGP pricing, features, policies
- **Conversation Memory**: Follow-up detection and context awareness
- **Comprehensive Logging**: Node execution, entities, SQL queries

## 🛠️ Setup

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Environment Variables
```ini
DATABASE_URL=mysql+aiomysql://user:password@localhost:3306/tgp_db
VECTOR_STORE_PROVIDER=chroma
CHROMA_PATH=agents/chatbot/data/chroma_db
OPENAI_API_KEY=sk-...
```

### 3. RAG Ingestion (Optional)
```bash
python -m agents.chatbot.ingest
```

## 🏃‍♂️ Usage

### Start Server
```bash
python main.py
```

### API Endpoint

**POST `/api/v1/chatbot/chat`**

```bash
curl -X POST http://localhost:8000/api/v1/chatbot/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Find arts grants in New York",
    "user_type": "paid-user"
  }'
```

**Response:**
```json
{
  "response": "I found 31 grants for arts in New York...",
  "query_type": "grant_search",
  "total_grants": 31,
  "cta_type": "view_grants",
  "user_type": "paid-user",
  "extracted_entities": {
    "interest_slugs": ["arts,culture,history-&-humanities"],
    "location_slugs": ["new-york-usa"]
  }
}
```

### User Types & CTAs

| User Type | CTA Type | Button Text |
|-----------|----------|-------------|
| `guest-user` | `signup` | "Sign Up & View Full Report" |
| `unpaid-user` | `subscribe` | "Subscribe to View Full List" |
| `paid-user` | `view_grants` | "View Full List of N Grants" |

## 📖 Documentation

- **FE Integration Guide**: [`docs/CHATBOT_API_INTEGRATION.md`](docs/CHATBOT_API_INTEGRATION.md)

## 📂 Directory Structure

```
agents/chatbot/
├── graph/         # LangGraph definition
├── nodes/         # Graph nodes (classifier, search, handlers)
├── services/      # LLM, Database, Vector Store
├── models/        # Pydantic request/response/state
├── data/          # Slugs, ChromaDB storage
└── utils/         # Logging utilities
```
