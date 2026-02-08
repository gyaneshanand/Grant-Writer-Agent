# TGP Chatbot Agent

The TGP Chatbot Agent is a conversational AI system integrated into the Grant Writer Agent project. It uses **LangGraph** for orchestration, **ChromaDB** for RAG (Retrieval-Augmented Generation), and **MySQL** for grant search and conversation persistence.

## 🧠 Architecture

The chatbot is built as a stateful graph with the following nodes:

1.  **Classifier**: Intent classification (greeting, grant_search, product_navigation, support, etc.).
2.  **Entity Extraction**: Extracts interests, locations, and eligibility criteria from user queries.
3.  **Grant Search**: Executes parameterized SQL queries against the TGP database.
4.  **Product Navigation (RAG)**: Answers questions about TGP pricing, features, and policies using ingested website content.
5.  **Handlers**: Template-based responses for greetings, application guidance, and support.
6.  **Conversation**: Handles state persistence and follow-up detection.

## 🚀 Features

-   **Grant Search**: "Find education grants in California" (returns real grant results).
-   **Product Q&A**: "How much does it cost?" (uses RAG over TGP website content).
-   **Entity Extraction**: Identifies interests (e.g., "Arts"), locations (e.g., "New York"), and eligibility.
-   **Context Awareness**: Handles follow-up questions and maintains conversation history.
-   **Modular Vector Store**: Supports ChromaDB (default) and Pinecone.

## 🛠️ Setup

### 1. Dependencies
The chatbot dependencies are included in the main `requirements.txt`.
```bash
pip install -r requirements.txt
```

### 2. Environment Variables
Add the following to your `.env` file:

```ini
# Chatbot Configuration
DATABASE_URL=mysql+aiomysql://user:password@localhost:3306/tgp_db
VECTOR_STORE_PROVIDER=chroma
CHROMA_PATH=agents/chatbot/data/chroma_db
OPENAI_API_KEY=sk-...
```

### 3. Database Initialization
Run the initialization script to create the conversation history table:

```bash
mysql -u user -p tgp_db < scripts/init_chatbot.sql
```

### 4. RAG Ingestion (Optional)
To enable Product Q&A, ingest the TGP website content into ChromaDB:

```bash
python -m agents.chatbot.ingest
```

## 🏃‍♂️ Usage

### Start the Server
```bash
python main.py
```

### API Endpoints

#### POST `/api/v1/chatbot/chat`
Send a message to the chatbot.

**Request:**
```json
{
  "message": "Find grants for women in tech",
  "session_id": "optional-uuid",
  "mode": "stateful" 
}
```

**Response:**
```json
{
  "response": "Here are some grants for women in technology...",
  "query_type": "grant_search",
  "results": [...],
  "session_id": "uuid"
}
```

#### GET `/api/v1/chatbot/health`
Check the status of the chatbot service.

## 📂 Directory Structure

-   `graph/`: Main LangGraph definition (`main_graph.py`).
-   `nodes/`: Individual graph nodes (classifier, search, handlers, etc.).
-   `services/`: External services (LLM, Database, Vector Store).
-   `models/`: Pydantic models and State definitions.
-   `data/`: Static data (slugs) and vector store storage.
