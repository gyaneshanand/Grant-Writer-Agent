"""
FAQ-aware RAG handler.

Core pipeline that gives precise FAQ answers:
1. Retrieve — searches Chroma with optional intent filter
2. Build context — labels FAQ vs website sources clearly
3. Generate — LLM uses FAQ answers as closely as possible
4. Check match — returns matched=False if no relevant answer found

Used by handlers.py and product_navigation.py as:
    result = await query_faq(user_message, intent="account_support")
    if result["matched"]:
        use result["response"]
    else:
        use static fallback
"""

import logging
from agents.chatbot.services.vector_store import get_vector_store
from agents.chatbot.services.llm import llm
from agents.chatbot.config import chatbot_settings

logger = logging.getLogger(__name__)

SUPPORT_EMAIL = chatbot_settings.support_email

# ── System prompt for FAQ-aware generation ──────────────────

SYSTEM_PROMPT = """You are The Grant Portal's support assistant.

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


def _build_context_block(results: list[dict]) -> str:
    """
    Format retrieved documents as context for the LLM.

    FAQ docs are clearly labeled so the LLM knows to use
    their answers precisely. Website docs are labeled separately.
    """
    blocks = []

    for i, r in enumerate(results, 1):
        meta = r["metadata"]
        source_type = meta.get("source_type", "website")

        if source_type == "faq":
            blocks.append(
                f"[SOURCE {i}: FAQ — slug: {meta.get('slug', 'unknown')}]\n"
                f"{r['content']}\n"
                f"[END SOURCE {i}]"
            )
        else:
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


async def query_faq(
    user_message: str,
    intent: str = None,
) -> dict:
    """
    RAG pipeline that prioritizes precise FAQ answers.

    Args:
        user_message: The user's message text
        intent: Classified intent for filtered retrieval.
                None = broad search (for product_navigation and other).

    Returns:
        {
            "matched": bool,       # True if LLM found a relevant answer
            "response": str,       # The response text (empty if not matched)
            "faq_slug": str|None,  # Slug of matched FAQ if from FAQ source
        }
    """
    vs = get_vector_store()

    # Check if vector store is initialized
    if hasattr(vs, "is_initialized") and not vs.is_initialized():
        logger.warning("Vector store not initialized — skipping FAQ RAG")
        return {"matched": False, "response": "", "faq_slug": None}

    # ── Step 1: Retrieve ──────────────────────────────────
    try:
        if intent and intent not in ("product_navigation", "other"):
            # Filtered search for specific intents
            results = vs.search_faqs(user_message, intent=intent, top_k=5)
        else:
            # Broad search for product_navigation and other
            results = vs.search_all(user_message, top_k=5)
    except Exception as e:
        logger.error(f"FAQ RAG retrieval failed: {e}")
        return {"matched": False, "response": "", "faq_slug": None}

    if not results:
        logger.info(f"FAQ RAG: No results for query='{user_message[:50]}' intent={intent}")
        return {"matched": False, "response": "", "faq_slug": None}

    # ── Step 2: Build context ─────────────────────────────
    context = _build_context_block(results)

    system_prompt = SYSTEM_PROMPT.format(
        context=context,
        support_email=SUPPORT_EMAIL,
    )

    # ── Step 3: Generate ──────────────────────────────────
    try:
        prompt = f"{system_prompt}\n\nUser question: \"{user_message}\""
        result = await llm.ainvoke(prompt)
        result_text = result.content.strip()
    except Exception as e:
        logger.error(f"FAQ RAG generation failed: {e}")
        return {"matched": False, "response": "", "faq_slug": None}

    # ── Step 4: Check if matched ──────────────────────────
    if "NO_FAQ_MATCH" in result_text:
        logger.info(f"FAQ RAG: LLM returned NO_FAQ_MATCH for intent={intent}")
        return {"matched": False, "response": "", "faq_slug": None}

    # ── Step 5: Extract FAQ slug if a FAQ was used ────────
    faq_slug = None
    if _has_faq_results(results):
        for r in results:
            if r["metadata"].get("source_type") == "faq":
                faq_slug = r["metadata"].get("slug")
                break

    logger.info(f"FAQ RAG: Matched. faq_slug={faq_slug} intent={intent}")
    return {
        "matched": True,
        "response": result_text,
        "faq_slug": faq_slug,
    }
