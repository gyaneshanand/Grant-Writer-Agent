# TGP Chatbot — FAQ Integration Plan (Final)

## Context

- **Vector store**: Chroma (already in use)
- **Already ingested**: 16 TGP website URLs (pricing, FAQs page, about, policies, blog, etc.)
- **New data**: 81 client-provided FAQ Q&A pairs (more specific than the website FAQ page)
- **Goal**: Ingest FAQs into Chroma → RAG gives precise FAQ answers → fallback to static templates when no good match

---

## 1. The Problem with Naive Ingestion

If you just dump FAQ text into Chroma the same way as website pages, you'll hit two issues:

**Issue 1: Chunking destroys Q&A pairing.** Website pages get chunked at ~500 tokens with overlap. If an FAQ Q&A pair gets split across chunks, the retrieved context loses the precise answer. A chunk might have the question but not the answer, or vice versa.

**Issue 2: Website FAQ page competes with client FAQs.** You've already ingested `thegrantportal.com/faqs`. The client's 81 FAQs are more specific and actionable than that page. When a user asks "how do I cancel", Chroma might retrieve the generic website FAQ page chunk instead of the precise client FAQ entry.

### Solution

1. **Ingest each FAQ as a single atomic document** — never chunk Q&A pairs. Each FAQ becomes one Chroma document with the full question + answer as content.
2. **Use metadata to distinguish source type** — `source_type: "faq"` vs `source_type: "website"`. The RAG prompt can then prioritize FAQ sources.
3. **Tag FAQs with intent** — so intent-filtered retrieval is possible.

---

## 2. Chroma Ingestion Strategy

### 2.1 Document Format Per FAQ

Each FAQ becomes **one document** in Chroma:

```python
{
    "id": "faq-cancel-subscription",
    "content": "Question: I want to cancel my plan; cancel my subscription.\n\nAnswer: To cancel your plan, please follow the instructions in The Grant Portal's Terms of Service. Cancellations must be made through your My Account profile. You will receive a cancellation email. And any subscription fees already paid are non-refundable, as outlined in the Terms of Service.",
    "metadata": {
        "source_type": "faq",           # Distinguishes from "website" docs
        "source": "client_faq_mar2026",
        "intent": "account_support",
        "category": "cancellation_refund",
        "slug": "cancel-subscription",
        "escalation_type": "none",
        "has_links": True,
        "original_answer": "To cancel your plan...",  # Exact client-approved text
    }
}
```

### 2.2 Why `content` = "Question: ...\n\nAnswer: ..."

The embedding captures **both the user intent (question) and the answer semantics**.
This means:
- "I want to stop paying" → embeds close to "cancel my plan; cancel my subscription"
- "how to cancel" → matches the question portion
- "My Account profile" → matches the answer portion (useful when user mentions specific UI)

### 2.3 `original_answer` in Metadata

This is critical for **precise answers**. The RAG pipeline retrieves documents,
but the LLM prompt instructs: "If the retrieved context is a FAQ (`source_type: faq`),
use the answer verbatim. Do NOT paraphrase."

This gives you the best of both worlds:
- Semantic retrieval (finds the right FAQ even with rephrased queries)
- Precise output (returns the exact client-approved answer)

---

## 3. Ingestion Script

### `scripts/ingest_faqs.py`

```python
"""
Ingest client FAQ Q&A pairs into Chroma.

Each FAQ becomes a single document (no chunking).
Sits alongside the already-ingested website page documents.

Usage:
    python -m scripts.ingest_faqs
    python -m scripts.ingest_faqs --clear-existing  # Remove old FAQ docs first
"""

import json
import argparse
import logging
from pathlib import Path

from langchain_openai import OpenAIEmbeddings
from langchain_chroma import Chroma

from app.config import settings

logger = logging.getLogger(__name__)

# Intent mapping: FAQ category → classifier intent
CATEGORY_TO_INTENT = {
    "account_login": "account_support",
    "cancellation_refund": "account_support",
    "technical_issues": "account_support",
    "subscription_pricing": "product_navigation",
    "grant_search_usage": "product_navigation",
    "grant_application": "application_guidance",
    "grant_writer": "application_guidance",
    "contact_support": "other",
    "general_info": "product_navigation",
    "spam_rejection": "other",
}

# Override specific FAQs where category→intent mapping is wrong
SLUG_INTENT_OVERRIDES = {
    # Eligibility-related
    "is-there-any-way-i": "eligibility_assessment",
    "our-nonprofit-organization-has": "eligibility_assessment",
    "how-do-i-find-the": "eligibility_assessment",
    "are-there-any-guarantees": "eligibility_assessment",
    # Grant writer directory as a product feature
    "is-the-grant-writer": "product_navigation",
}


def load_faqs(filepath: str = "data/faqs.json") -> list[dict]:
    with open(filepath) as f:
        return json.load(f)


def determine_intent(faq: dict) -> str:
    if faq["slug"] in SLUG_INTENT_OVERRIDES:
        return SLUG_INTENT_OVERRIDES[faq["slug"]]
    if faq.get("intent"):
        return faq["intent"]
    return CATEGORY_TO_INTENT.get(faq["category"], "other")


def build_document_content(faq: dict) -> str:
    """
    Build the text content that gets embedded.

    Format: "Question: {q}\n\nAnswer: {a}"

    This captures both user intent and answer semantics in a single embedding.
    """
    return f"Question: {faq['question']}\n\nAnswer: {faq['answer']}"


def build_metadata(faq: dict) -> dict:
    """Build Chroma metadata for a FAQ document."""
    return {
        "source_type": "faq",
        "source": "client_faq_mar2026",
        "intent": determine_intent(faq),
        "category": faq["category"],
        "slug": faq["slug"],
        "escalation_type": faq.get("escalation_type", "none"),
        "has_links": bool(faq.get("links")),
        "original_answer": faq["answer"],  # Exact text for precise responses
    }


def ingest(filepath: str = "data/faqs.json", clear_existing: bool = False):
    faqs = load_faqs(filepath)
    logger.info(f"Loaded {len(faqs)} FAQs from {filepath}")

    embeddings = OpenAIEmbeddings(
        openai_api_key=settings.openai_api_key,
        model="text-embedding-3-small",
    )

    vectorstore = Chroma(
        collection_name=settings.chroma_collection_name,
        embedding_function=embeddings,
        persist_directory=settings.chroma_persist_directory,
    )

    # Optionally clear old FAQ documents before re-ingesting
    if clear_existing:
        existing = vectorstore.get(where={"source_type": "faq"})
        if existing and existing["ids"]:
            vectorstore.delete(ids=existing["ids"])
            logger.info(f"Deleted {len(existing['ids'])} existing FAQ documents")

    # Build documents
    ids = []
    documents = []
    metadatas = []

    for faq in faqs:
        doc_id = f"faq-{faq['slug']}"
        content = build_document_content(faq)
        metadata = build_metadata(faq)

        ids.append(doc_id)
        documents.append(content)
        metadatas.append(metadata)

    # Upsert to Chroma
    vectorstore.add_texts(
        texts=documents,
        metadatas=metadatas,
        ids=ids,
    )

    # Log distribution
    intent_counts = {}
    for m in metadatas:
        intent_counts[m["intent"]] = intent_counts.get(m["intent"], 0) + 1

    logger.info(
        f"Ingested {len(ids)} FAQ documents into Chroma. "
        f"Distribution: {intent_counts}"
    )


def main():
    parser = argparse.ArgumentParser(description="Ingest FAQs into Chroma")
    parser.add_argument("--file", default="data/faqs.json")
    parser.add_argument("--clear-existing", action="store_true",
                        help="Remove old FAQ docs before ingesting")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)
    ingest(filepath=args.file, clear_existing=args.clear_existing)


if __name__ == "__main__":
    main()
```

---

## 4. Updated RAG Pipeline

### 4.1 Vector Store Search with Intent Filter

```python
# app/services/vector_store.py

from langchain_openai import OpenAIEmbeddings
from langchain_chroma import Chroma
from app.config import settings

embeddings = OpenAIEmbeddings(
    openai_api_key=settings.openai_api_key,
    model="text-embedding-3-small",
)

vectorstore = Chroma(
    collection_name=settings.chroma_collection_name,
    embedding_function=embeddings,
    persist_directory=settings.chroma_persist_directory,
)


async def search_product_docs(query: str, top_k: int = 5) -> list[dict]:
    """
    Search all documents (website pages + FAQs).
    Used by product_navigation and other intents.
    """
    results = vectorstore.similarity_search_with_score(query, k=top_k)

    return [
        {
            "content": doc.page_content,
            "metadata": doc.metadata,
            "score": score,
        }
        for doc, score in results
    ]


async def search_with_intent_filter(
    query: str,
    intent: str,
    top_k: int = 5,
) -> list[dict]:
    """
    Search documents filtered by intent.

    Retrieves both FAQ docs (tagged with intent) and general website docs.
    The `where` filter scopes FAQ results, but we also want website context,
    so we do TWO searches and merge.
    """
    # Search 1: FAQ documents filtered by intent
    faq_results = vectorstore.similarity_search_with_score(
        query,
        k=top_k,
        filter={"source_type": "faq", "intent": intent},
    )

    # Search 2: Website documents (no intent filter — all pages are relevant)
    web_results = vectorstore.similarity_search_with_score(
        query,
        k=3,
        filter={"source_type": "website"},
    )

    # Merge and sort by score (lower = better in Chroma's L2 distance)
    all_results = []
    seen_ids = set()

    for doc, score in faq_results + web_results:
        doc_id = doc.metadata.get("slug") or doc.metadata.get("source", "")
        if doc_id not in seen_ids:
            seen_ids.add(doc_id)
            all_results.append({
                "content": doc.page_content,
                "metadata": doc.metadata,
                "score": score,
            })

    # Sort by score (ascending for L2 distance, descending for cosine)
    # Adjust based on your Chroma distance metric
    all_results.sort(key=lambda x: x["score"])

    return all_results[:top_k]
```

### 4.2 RAG Response Generator with FAQ Precision

```python
# app/nodes/faq_rag.py

"""
RAG handler that gives precise FAQ answers.

Key behavior:
- If retrieved context includes FAQ docs → instruct LLM to use FAQ answer as-is
- If only website docs → generate from context normally
- If nothing relevant → return None (caller uses static fallback)
"""

import logging
from app.services.vector_store import search_with_intent_filter, search_product_docs
from app.services.llm import get_llm_client
from app.config import settings

logger = logging.getLogger(__name__)


def _build_context_block(results: list[dict]) -> str:
    """
    Format retrieved documents as context for the LLM.

    FAQ docs are formatted differently from website docs to help
    the LLM distinguish them and use FAQ answers precisely.
    """
    blocks = []

    for i, r in enumerate(results, 1):
        meta = r["metadata"]
        source_type = meta.get("source_type", "website")

        if source_type == "faq":
            # FAQ: clearly labeled so LLM knows to use the answer precisely
            blocks.append(
                f"[SOURCE {i}: FAQ — slug: {meta.get('slug', 'unknown')}]\n"
                f"{r['content']}\n"
                f"[END SOURCE {i}]"
            )
        else:
            # Website page: general context
            source = meta.get("source", "unknown")
            blocks.append(
                f"[SOURCE {i}: Website page — {source}]\n"
                f"{r['content']}\n"
                f"[END SOURCE {i}]"
            )

    return "\n\n".join(blocks)


def _has_faq_results(results: list[dict]) -> bool:
    """Check if any FAQ documents are in the results."""
    return any(r["metadata"].get("source_type") == "faq" for r in results)


SYSTEM_PROMPT_TEMPLATE = """You are The Grant Portal's support assistant.

You have been given relevant context from our FAQ database and website.
Use ONLY the provided context to answer the user's question.

CRITICAL RULES FOR FAQ SOURCES:
- If the context includes a FAQ source (marked as [SOURCE N: FAQ]), use the FAQ's Answer
  section as closely as possible. The FAQ answers are pre-approved by our team.
- Preserve ALL links, URLs, and email addresses exactly as they appear in the FAQ.
- Preserve specific step-by-step instructions exactly (e.g., "Select 'My Account Settings'").
- You may lightly rephrase for natural conversation, but do NOT change the substance,
  omit steps, or add information not in the FAQ.

RULES FOR WEBSITE SOURCES:
- Use website content to supplement if no FAQ directly answers the question.
- Summarize website content naturally.

GENERAL RULES:
- If the context does not contain a satisfactory answer, respond with exactly: NO_FAQ_MATCH
- Do NOT make up information. Do NOT answer from general knowledge.
- Be concise and conversational.
- Support email: {support_email}

══ CONTEXT ══
{context}
══ END CONTEXT ══"""


async def rag_with_faqs(
    query: str,
    intent: str | None = None,
    conversation_history: list[dict] | None = None,
) -> dict:
    """
    RAG pipeline that prioritizes precise FAQ answers.

    Args:
        query: User's message
        intent: Classified intent (for filtered retrieval). None = broad search.
        conversation_history: Prior messages for multi-turn context

    Returns:
        {
            "matched": bool,       # True if LLM found a relevant answer
            "response": str,       # The response text (empty if not matched)
            "faq_slug": str|None,  # Slug of matched FAQ if from FAQ source
            "sources": list[dict], # Retrieved documents (for logging/analytics)
        }
    """

    # ── Step 1: Retrieve ──
    if intent and intent not in ("product_navigation", "other"):
        # Filtered search for specific intents
        results = await search_with_intent_filter(query, intent=intent, top_k=5)
    else:
        # Broad search for product_navigation and other
        results = await search_product_docs(query, top_k=5)

    if not results:
        logger.info(f"RAG: No results for query='{query[:50]}' intent={intent}")
        return {"matched": False, "response": "", "faq_slug": None, "sources": []}

    # ── Step 2: Build context ──
    context = _build_context_block(results)

    system_prompt = SYSTEM_PROMPT_TEMPLATE.format(
        context=context,
        support_email=settings.SUPPORT_EMAIL,
    )

    # ── Step 3: Generate ──
    messages = [{"role": "system", "content": system_prompt}]

    if conversation_history:
        for msg in conversation_history[-6:]:
            messages.append({"role": msg["role"], "content": msg["content"]})

    messages.append({"role": "user", "content": query})

    client = get_llm_client()
    response = await client.chat.completions.create(
        model=settings.llm_model,
        messages=messages,
        temperature=0.2,
        max_tokens=500,
    )

    result_text = response.choices[0].message.content.strip()

    # ── Step 4: Check if matched ──
    if "NO_FAQ_MATCH" in result_text:
        logger.info(f"RAG: LLM returned NO_FAQ_MATCH for intent={intent}")
        return {"matched": False, "response": "", "faq_slug": None, "sources": results}

    # ── Step 5: Extract FAQ slug if a FAQ was used ──
    faq_slug = None
    if _has_faq_results(results):
        # Find the top FAQ result — likely the one the LLM used
        for r in results:
            if r["metadata"].get("source_type") == "faq":
                faq_slug = r["metadata"].get("slug")
                break

    logger.info(f"RAG: Matched. faq_slug={faq_slug} intent={intent}")
    return {
        "matched": True,
        "response": result_text,
        "faq_slug": faq_slug,
        "sources": results,
    }
```

---

## 5. Updated Intent Handlers

All handlers now follow the same pattern: **RAG first → static fallback**.

```python
# app/nodes/handlers.py

import random
import logging
from app.nodes.faq_rag import rag_with_faqs
from app.config import settings

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════
#  Static Fallback Templates (existing responses)
# ═══════════════════════════════════════════════════════

GREETING_RESPONSES = [
    "Hi there! I can help you find grants or answer questions about "
    "The Grant Portal. What are you looking for?",
    "Hello! Welcome to The Grant Portal. Tell me what kind of grants "
    "you're interested in — I can search by topic, location, or eligibility.",
    "Hey! Ready to find some funding? Just describe what you're looking "
    "for and I'll search our grant directory.",
]

ACCOUNT_SUPPORT_FALLBACK = (
    f"For account-related issues like login, password reset, or billing, "
    f"please reach out to our support team at {settings.SUPPORT_EMAIL} — "
    f"they'll be able to help you directly.\n\n"
    f"In the meantime, I can help you search for grants or answer "
    f"questions about the platform!"
)

ELIGIBILITY_FALLBACK = (
    "I can show you the eligibility criteria listed on any grant "
    "(like required organization type, location requirements, etc.), "
    "but I'm not able to assess whether you or your organization would "
    "qualify — that depends on details only you and the funder would know.\n\n"
    "If you'd like, I can search for grants and include their eligibility "
    "details so you can evaluate the fit yourself. Just tell me what "
    "you're looking for!"
)

APPLICATION_GUIDANCE_FALLBACK = (
    "The Grant Portal is a grant directory — we help you discover grants "
    "and foundations, but we don't handle applications directly.\n\n"
    "For application support, we have professional grant writers who can help. "
    f"Reach out to {settings.SUPPORT_EMAIL} to get connected with one.\n\n"
    "In the meantime, I can help you find grants that match your needs — "
    "just tell me what you're looking for!"
)

PRODUCT_NAVIGATION_FALLBACK = (
    "I don't have a specific answer for that question. "
    "Please use the Contact Us page at "
    "https://www.thegrantportal.com/contact-us "
    f"or email {settings.SUPPORT_EMAIL} for assistance."
)


# ═══════════════════════════════════════════════════════
#  Handlers
# ═══════════════════════════════════════════════════════

async def handle_greeting(state: dict) -> dict:
    """Greeting — random template, no RAG needed."""
    state["messages"].append({
        "role": "assistant",
        "content": random.choice(GREETING_RESPONSES),
        "query_type": "greeting",
    })
    return state


async def handle_account_support(state: dict) -> dict:
    """Account support — RAG from Chroma (FAQ + website), fallback to static."""
    query = state["messages"][-1]["content"]
    history = state.get("messages", [])[:-1]

    result = await rag_with_faqs(
        query=query,
        intent="account_support",
        conversation_history=history,
    )

    state["messages"].append({
        "role": "assistant",
        "content": result["response"] if result["matched"] else ACCOUNT_SUPPORT_FALLBACK,
        "query_type": "account_support",
        "faq_slug": result.get("faq_slug"),
    })
    return state


async def handle_eligibility_assessment(state: dict) -> dict:
    """Eligibility — RAG first, static fallback."""
    query = state["messages"][-1]["content"]
    history = state.get("messages", [])[:-1]

    result = await rag_with_faqs(
        query=query,
        intent="eligibility_assessment",
        conversation_history=history,
    )

    state["messages"].append({
        "role": "assistant",
        "content": result["response"] if result["matched"] else ELIGIBILITY_FALLBACK,
        "query_type": "eligibility_assessment",
        "faq_slug": result.get("faq_slug"),
    })
    return state


async def handle_application_guidance(state: dict) -> dict:
    """Application guidance — RAG first, static fallback."""
    query = state["messages"][-1]["content"]
    history = state.get("messages", [])[:-1]

    result = await rag_with_faqs(
        query=query,
        intent="application_guidance",
        conversation_history=history,
    )

    state["messages"].append({
        "role": "assistant",
        "content": result["response"] if result["matched"] else APPLICATION_GUIDANCE_FALLBACK,
        "query_type": "application_guidance",
        "faq_slug": result.get("faq_slug"),
    })
    return state


async def handle_product_navigation(state: dict) -> dict:
    """Product navigation — RAG (broad search, FAQ + website docs), fallback."""
    query = state["messages"][-1]["content"]
    history = state.get("messages", [])[:-1]

    result = await rag_with_faqs(
        query=query,
        intent="product_navigation",
        conversation_history=history,
    )

    state["messages"].append({
        "role": "assistant",
        "content": result["response"] if result["matched"] else PRODUCT_NAVIGATION_FALLBACK,
        "query_type": "product_navigation",
        "faq_slug": result.get("faq_slug"),
    })
    return state


async def handle_other(state: dict) -> dict:
    """Catch-all — broad RAG search, fallback."""
    query = state["messages"][-1]["content"]
    history = state.get("messages", [])[:-1]

    result = await rag_with_faqs(
        query=query,
        intent=None,  # No filter — search everything
        conversation_history=history,
    )

    state["messages"].append({
        "role": "assistant",
        "content": result["response"] if result["matched"] else PRODUCT_NAVIGATION_FALLBACK,
        "query_type": "other",
        "faq_slug": result.get("faq_slug"),
    })
    return state
```

---

## 6. Flow Diagram

```
User message
    │
    ▼
┌──────────────────┐
│ load_conversation │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ detect_follow_up │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│  classify_query  │
└────────┬─────────┘
         │
         ├── greeting ──────────────────► Static template (random)
         │
         ├── grant_search ──────────────► Entity extraction → SQL → results
         │
         ├── account_support ───────────► Chroma RAG (intent-filtered)
         │                                    │
         │                                    ├── FAQ/website match → LLM generates
         │                                    │   (precise FAQ answer preserved)
         │                                    │
         │                                    └── NO_FAQ_MATCH → Static template:
         │                                        "Contact tech@promero.com..."
         │
         ├── eligibility_assessment ────► Chroma RAG (intent-filtered)
         │                                    ├── match → LLM generates
         │                                    └── no match → Static template
         │
         ├── application_guidance ──────► Chroma RAG (intent-filtered)
         │                                    ├── match → LLM generates
         │                                    └── no match → Static template
         │
         ├── product_navigation ────────► Chroma RAG (broad search)
         │                                    ├── match → LLM generates
         │                                    └── no match → "Contact us..."
         │
         └── other ────────────────────► Chroma RAG (no filter)
                                              ├── match → LLM generates
                                              └── no match → "Contact us..."
         │
         ▼
┌──────────────────┐
│ save_conversation │
└──────────────────┘
```

---

## 7. Handling the Overlap: Website FAQ Page vs Client FAQs

You already have `thegrantportal.com/faqs` ingested. The client's 81 FAQs
are more specific. To handle this cleanly:

### Option A: Keep Both (Recommended)

The website FAQ page provides general context. The client FAQs provide specific Q&A.
The system prompt tells the LLM: **"Prefer FAQ sources over website sources."**

The `_build_context_block` function already labels sources as `[SOURCE N: FAQ]` vs
`[SOURCE N: Website page]`, and the system prompt says to prefer FAQs.

### Option B: Remove Website FAQ Page

If you find the website FAQ page is creating noise:

```python
# One-time cleanup: remove the website FAQ page from Chroma
results = vectorstore.get(
    where={"source": "https://www.thegrantportal.com/faqs"}
)
if results and results["ids"]:
    vectorstore.delete(ids=results["ids"])
```

I'd start with **Option A** and switch to B only if testing shows confusion.

---

## 8. Classifier Prompt Update

Add these examples so the classifier correctly routes FAQ-type questions:

```python
FAQ_CLASSIFICATION_EXAMPLES = """
# account_support:
"how can we find out login info" → account_support
"I can't log in" → account_support
"cancel my subscription" → account_support
"I was charged twice" → account_support
"delete my account" → account_support
"I can't reset my password" → account_support
"I paid but still shows free" → account_support
"how do I update my password" → account_support

# application_guidance:
"how can I apply for these grants" → application_guidance
"can you apply without subscribing" → application_guidance
"how much do grant writers charge" → application_guidance
"how to get listed as a grant writer" → application_guidance

# eligibility_assessment:
"our nonprofit is 1 year old, can we apply" → eligibility_assessment
"how do I find grants I'm eligible for" → eligibility_assessment
"are there guarantees for getting grants" → eligibility_assessment

# product_navigation:
"how much does a subscription cost" → product_navigation
"what does deadline ongoing mean" → product_navigation
"can I export to excel" → product_navigation
"how often do you update grants" → product_navigation
"do you offer an API" → product_navigation
"how does your site work" → product_navigation
"grant view is blurred" → product_navigation

# grant_search (NOT FAQ — actual grant searching):
"grants for education in California" → grant_search
"nonprofit grants in Texas for veterans" → grant_search
"show me grants under $50,000" → grant_search
"""
```

---

## 9. Updated Project Structure

```
tgp-chatbot/
├── app/
│   ├── main.py
│   ├── config.py
│   ├── models/
│   ├── graph/
│   │   └── main_graph.py
│   ├── nodes/
│   │   ├── conversation.py
│   │   ├── follow_up.py
│   │   ├── classifier.py          ← Updated with FAQ examples
│   │   ├── entity_extraction.py
│   │   ├── search.py
│   │   ├── response.py
│   │   ├── faq_rag.py             ← NEW: RAG handler with FAQ precision
│   │   └── handlers.py            ← UPDATED: RAG first, static fallback
│   ├── services/
│   │   ├── database.py
│   │   ├── llm.py
│   │   └── vector_store.py        ← UPDATED: intent-filtered search
│   └── data/
│       └── slugs.py
├── scripts/
│   ├── ingest_product_docs.py     (existing — website pages)
│   └── ingest_faqs.py             ← NEW: FAQ ingestion to Chroma
├── data/
│   ├── faqs.json                  ← NEW: client FAQ data
│   └── product_docs/              (existing)
└── tests/
    ├── test_faq_rag.py            ← NEW
    └── ...
```

---

## 10. Implementation Sequence

| Step | Task | Effort |
|------|------|--------|
| 1 | Place `faqs_with_intents.json` as `data/faqs.json` | 5 min |
| 2 | Write `scripts/ingest_faqs.py` | 1 hr |
| 3 | Run ingestion: `python -m scripts.ingest_faqs` | 10 min |
| 4 | Add `search_with_intent_filter()` to vector_store.py | 30 min |
| 5 | Create `app/nodes/faq_rag.py` | 1-2 hrs |
| 6 | Update all handlers in `handlers.py` | 1 hr |
| 7 | Update classifier prompt | 30 min |
| 8 | Test all 81 FAQ questions end-to-end | 2-3 hrs |
| 9 | Tune: compare FAQ precision vs website doc noise | 1 hr |

**Total: ~2-3 days**

---

## 11. Testing

### Test All 81 FAQs

For each of the 81 client FAQs, verify:

| Check | Pass Criteria |
|-------|---------------|
| Correct classification | FAQ routes to expected intent |
| FAQ retrieved | Chroma returns the matching FAQ document |
| Precise answer | Response contains the key information from client FAQ |
| Links preserved | URLs and emails appear in response |
| No hallucination | Response doesn't invent information |

### Test Static Fallback

Verify these queries get the static template (not a bad FAQ match):

```
"tell me about quantum computing"     → other → NO_FAQ_MATCH → fallback
"what's the weather today"            → other → NO_FAQ_MATCH → fallback
"help me write a grant proposal"      → application_guidance → NO_FAQ_MATCH → fallback
```

### Test Grant Search Isn't Affected

```
"grants for education in California"  → grant_search → SQL (NOT FAQ)
"nonprofit grants under $50,000"      → grant_search → SQL (NOT FAQ)
```
