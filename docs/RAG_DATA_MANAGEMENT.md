# RAG Pipeline — Data Management Guide

> How to manage, update, and re-ingest the chatbot's knowledge base.

---

## Architecture Overview

The chatbot's RAG pipeline uses **ChromaDB** as a vector store with two types of documents:

| Source Type | Count | Ingestion Method | Chunking |
|-------------|-------|-----------------|----------|
| **Website pages** | ~1,350 chunks | `python -m agents.chatbot.ingest` | Chunked (500 tokens, 200 overlap) |
| **FAQ entries** | 95 docs | `python -m agents.chatbot.ingest_faqs` | Atomic (1 doc per FAQ, no chunking) |

Both coexist in the same Chroma collection. They are distinguished by the `source_type` metadata field (`"faq"` vs no tag for website docs).

**Storage location:** `agents/chatbot/data/chroma_db/` (configurable via `chroma_path` in `.env`)

---

## 1. FAQ Data (`faqs.json`)

### File Location

```
agents/chatbot/data/faqs.json
```

### JSON Format

Each FAQ entry must follow this schema:

```json
{
  "id": 1,
  "slug": "unique-slug-for-this-faq",
  "category": "account_login",
  "question": "The user's question or multiple phrasings separated by semicolons",
  "answer": "Plain text answer (used as fallback)",
  "answer_raw": "Markdown answer with [links](https://example.com) and <email@example.com>",
  "links": [
    {
      "text": "Link Label",
      "url": "https://example.com"
    }
  ],
  "escalation_type": "none",
  "alternate_phrasings": [],
  "keywords": [],
  "intent": "account_support"
}
```

### Required Fields

| Field | Type | Description |
|-------|------|-------------|
| `slug` | string | Unique identifier (used as Chroma doc ID: `faq-{slug}`) |
| `question` | string | The question text — multiple phrasings separated by `;` |
| `answer` | string | Plain text answer (fallback if `answer_raw` is empty) |
| `intent` | string | Must be one of: `product_navigation`, `account_support`, `eligibility_assessment`, `application_guidance`, `other` |

### Optional Fields

| Field | Type | Description |
|-------|------|-------------|
| `answer_raw` | string | Markdown-formatted answer with links (preferred — used for ingestion) |
| `links` | array | Link objects with `text` and `url` (stored as metadata) |
| `category` | string | Finer-grained category (e.g., `cancellation_refund`, `grant_search_usage`) |
| `escalation_type` | string | `none`, `email`, `live_agent`, `contact_form` |
| `id` | number | Numeric ID (not used by ingestion, only for human reference) |

### Intent Mapping

Choose the correct `intent` for each FAQ:

| Intent | Use When |
|--------|----------|
| `product_navigation` | Questions about how the platform works, pricing, features, IRS 990, subscriptions |
| `account_support` | Login, password, billing, cancellations, refunds, email issues, account deletion |
| `eligibility_assessment` | "Am I eligible?", filtering by state/eligibility, organization qualifications |
| `application_guidance` | "How do I apply?", grant writer questions, application process |
| `other` | Spam, live agent requests, contact support, terms/privacy questions |

### Adding a New FAQ

1. Open `agents/chatbot/data/faqs.json`
2. Add a new entry at the end of the array:

```json
{
  "id": 96,
  "slug": "your-unique-slug-here",
  "category": "subscription_pricing",
  "question": "Can I pause my subscription?",
  "answer": "Subscriptions cannot be paused. You can cancel and re-subscribe later.",
  "answer_raw": "Subscriptions cannot be paused. You can cancel and re-subscribe later. See [Terms of Service](https://www.thegrantportal.com/terms-service).",
  "links": [
    { "text": "Terms of Service", "url": "https://www.thegrantportal.com/terms-service" }
  ],
  "escalation_type": "none",
  "intent": "product_navigation"
}
```

3. Re-ingest (see next section)

> **Important:** The `slug` must be unique across all FAQs. It becomes the Chroma document ID as `faq-{slug}`.

### Editing an Existing FAQ

1. Find the entry by `slug` or `id` in `faqs.json`
2. Edit the `answer`, `answer_raw`, `links`, or `intent` fields
3. Re-ingest with `--clear-existing` to replace the old version

---

## 2. Re-ingesting FAQs

### Standard Re-ingest (Recommended)

Clears old FAQ docs and re-ingests all entries:

```bash
python -m agents.chatbot.ingest_faqs --clear-existing
```

**What happens:**
1. Deletes all documents where `source_type = "faq"` from Chroma
2. Reads `agents/chatbot/data/faqs.json`
3. Creates one Chroma document per FAQ entry
4. Prints the count and intent distribution

**Expected output:**
```
============================================================
TGP Chatbot — FAQ Ingestion
============================================================
🗑️  Deleted 95 existing FAQ documents

✅ Ingested 95 FAQ documents into Chroma
📊 Distribution by intent:
   account_support: 27
   application_guidance: 10
   eligibility_assessment: 4
   other: 8
   product_navigation: 46
```

### Additive Ingest (No Clear)

Adds new FAQ docs without removing existing ones:

```bash
python -m agents.chatbot.ingest_faqs
```

> **Use case:** You've added new FAQs but haven't changed existing ones. Since document IDs are based on `slug`, re-ingesting an unchanged FAQ is safe (Chroma upserts by ID).

### Ingest from a Different File

```bash
python -m agents.chatbot.ingest_faqs --file /path/to/custom_faqs.json
```

### After Re-ingesting

- **No server restart required** — Chroma reads from disk, and the vector store is re-initialized on next query
- **Verify the count** to make sure all FAQs were ingested:

```bash
python -c "
from dotenv import load_dotenv; load_dotenv()
from langchain_openai import OpenAIEmbeddings
from langchain_chroma import Chroma
from agents.chatbot.config import chatbot_settings
vs = Chroma(persist_directory=chatbot_settings.chroma_path, embedding_function=OpenAIEmbeddings())
faq_docs = vs.get(where={'source_type': 'faq'})
print(f'FAQ documents in Chroma: {len(faq_docs[\"ids\"])}')
"
```

---

## 3. Re-ingesting Website Pages

Website pages are ingested separately using a different script.

### Full Re-ingest

Clears ALL Chroma data (website + FAQ) and re-ingests website pages:

```bash
python -m agents.chatbot.ingest
```

> **⚠️ Warning:** This clears the entire Chroma store including FAQ documents. After running this, you must also re-ingest FAQs:

```bash
python -m agents.chatbot.ingest              # Re-ingest website pages
python -m agents.chatbot.ingest_faqs         # Re-ingest FAQs on top
```

### Reset Only (Clear Without Re-ingesting)

```bash
python -m agents.chatbot.ingest --reset
```

### Currently Indexed Website Pages

These 16 URLs are fetched, chunked, and stored:

| URL | Content |
|-----|---------|
| `/pricing-and-plans` | Pricing tiers and features |
| `/faqs` | Website FAQ page (general) |
| `/about-us` | Company info |
| `/contact-us` | Contact information |
| `/hire-a-grant-writer` | Grant writer marketplace info |
| `/i-am-a-grant-provider` | Grant provider listing |
| `/grant-writer-application` | Grant writer signup |
| `/privacy-policy` | Privacy policy |
| `/cookie-policy` | Cookie policy |
| `/terms-service` | Terms of service |
| `/terms-and-conditions-grant-writers` | Grant writer T&C |
| `blog.thegrantportal.com/` | Blog homepage |
| `/grants-for-nonprofits` | Nonprofit grants overview |
| `/grants-for-small-business` | Small business grants overview |
| `/grants-for-individuals` | Individual grants overview |
| `/irs-990-private-foundations/profile-search` | IRS 990 PF search info |

To add or remove URLs, edit the `URLS_TO_INGEST` list in `agents/chatbot/ingest.py`.

---

## 4. Full Rebuild from Scratch

If you need to completely rebuild the vector store:

```bash
# Step 1: Clear everything
python -m agents.chatbot.ingest --reset

# Step 2: Re-ingest website pages
python -m agents.chatbot.ingest

# Step 3: Ingest FAQ data
python -m agents.chatbot.ingest_faqs
```

**Total documents expected:** ~1,450 (varies based on website page sizes)
- ~1,350 website page chunks
- 95 FAQ documents

---

## 5. Troubleshooting

### "No FAQ results returned"

1. **Check FAQs are ingested:** Run the verification command from section 2
2. **Check intent tags:** The FAQ's `intent` field must match the handler's intent exactly
3. **Check Chroma path:** Ensure `chroma_path` in `.env` or `config.py` matches where you ingested

### "Wrong FAQ being returned"

1. **Check the question field:** Chroma matches by semantic similarity to the `question` + `answer` combined text
2. **Add alternate phrasings:** Include multiple question variants separated by `;` in the `question` field
3. **Check intent filter:** If a FAQ is tagged with the wrong `intent`, it won't be found by the right handler

### "Old FAQ answers still showing"

Re-ingest with `--clear-existing` to remove stale documents:

```bash
python -m agents.chatbot.ingest_faqs --clear-existing
```

### "Website pages seem outdated"

Re-ingest website pages (note: this clears ALL data):

```bash
python -m agents.chatbot.ingest              # Clears + re-fetches all pages
python -m agents.chatbot.ingest_faqs         # Re-add FAQ data
```

---

## 6. Configuration Reference

| Setting | Location | Default | Description |
|---------|----------|---------|-------------|
| `chroma_path` | `.env` / `config.py` | `agents/chatbot/data/chroma_db` | Chroma storage directory |
| `support_email` | `config.py` | `tech@promero.com` | Email used in fallback templates |
| `llm_model` | `.env` / `config.py` | `gpt-4o-mini` | LLM used for FAQ response generation |
| `OPENAI_API_KEY` | `.env` | — | Required for embeddings and LLM |
