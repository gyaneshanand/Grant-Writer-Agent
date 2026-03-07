"""
Template-based handler nodes with FAQ RAG.

These nodes first try to answer from FAQ/website docs via RAG,
then fall back to static/template responses if no match is found.
"""

import random
import logging
from agents.chatbot.models.state import ChatbotState
from agents.chatbot.config import chatbot_settings
from agents.chatbot.nodes.faq_rag import query_faq
from agents.chatbot.utils.logging import log_node_execution

logger = logging.getLogger(__name__)

SUPPORT_EMAIL = chatbot_settings.support_email


# ── Static Fallback Templates ──────────────────────────────
# Used when FAQ RAG returns no match.

ACCOUNT_SUPPORT_FALLBACK = (
    f"For account-related issues like login, password reset, or "
    f"billing, please reach out to our support team at "
    f"**{SUPPORT_EMAIL}** — they'll be able to help you directly.\n\n"
    f"In the meantime, I can help you search for grants or answer "
    f"questions about the platform!"
)

ELIGIBILITY_FALLBACK = (
    "I can show you the **eligibility criteria listed on any grant** "
    "(like required organization type, location requirements, etc.), "
    "but I'm not able to assess whether you or your organization "
    "would qualify — that depends on details only you and the "
    "funder would know.\n\n"
    "If you'd like, I can **search for grants and include their "
    "eligibility details** so you can evaluate the fit yourself. "
    "Just tell me what you're looking for!"
)

APPLICATION_GUIDANCE_FALLBACK = (
    "The Grant Portal is a **grant directory** — we help you "
    "discover grants and foundations, but we don't handle "
    "applications directly.\n\n"
    "For application support, we have **professional grant writers** "
    f"who can help. Reach out to **{SUPPORT_EMAIL}** to get "
    "connected with one.\n\n"
    "In the meantime, I can help you **find grants** that match "
    "your needs — just tell me what you're looking for!"
)

FALLBACK_RESPONSE = (
    "I'm not sure I understood that. Here's what I can help with:\n\n"
    "• **Finding grants** — tell me your interests, location, "
    "or organization type\n"
    "• **Platform questions** — pricing, features, how things work\n\n"
    f"For account issues or application help, please reach out "
    f"to **{SUPPORT_EMAIL}**."
)


# ── Greeting ───────────────────────────────────────────────


@log_node_execution
async def handle_greeting(state: ChatbotState) -> dict:
    """
    Welcome message. Randomized for variety.
    No LLM call — instant response.
    """

    greetings = [
        (
            "Hi there! 👋 I can help you find grants or answer questions "
            "about The Grant Portal. What are you looking for?"
        ),
        (
            "Hello! Welcome to The Grant Portal. Tell me what kind of "
            "grants you're interested in — I can search by topic, "
            "location, or eligibility."
        ),
        (
            "Hey! Ready to find some funding? Just describe what you're "
            "looking for and I'll search our grant directory."
        ),
    ]

    return {"response": random.choice(greetings)}


# ── Account Support ────────────────────────────────────────


@log_node_execution
async def handle_account_support(state: ChatbotState) -> dict:
    """Account support — FAQ RAG first, static fallback."""

    result = await query_faq(
        user_message=state["user_message"],
        intent="account_support",
    )

    if result["matched"]:
        logger.info(f"Account support answered from FAQ: {result['faq_slug']}")
        return {"response": result["response"]}

    return {"response": ACCOUNT_SUPPORT_FALLBACK}


# ── Eligibility Assessment ─────────────────────────────────


@log_node_execution
async def handle_eligibility_assessment(state: ChatbotState) -> dict:
    """Eligibility questions — FAQ RAG first, static fallback."""

    result = await query_faq(
        user_message=state["user_message"],
        intent="eligibility_assessment",
    )

    if result["matched"]:
        logger.info(f"Eligibility answered from FAQ: {result['faq_slug']}")
        return {"response": result["response"]}

    return {"response": ELIGIBILITY_FALLBACK}


# ── Application Guidance ───────────────────────────────────


@log_node_execution
async def handle_application_guidance(state: ChatbotState) -> dict:
    """Application guidance — FAQ RAG first, static fallback."""

    result = await query_faq(
        user_message=state["user_message"],
        intent="application_guidance",
    )

    if result["matched"]:
        logger.info(f"Application guidance answered from FAQ: {result['faq_slug']}")
        return {"response": result["response"]}

    return {"response": APPLICATION_GUIDANCE_FALLBACK}


# ── Fallback ───────────────────────────────────────────────


@log_node_execution
async def handle_fallback(state: ChatbotState) -> dict:
    """Catch-all — broad FAQ RAG search, then static fallback."""

    result = await query_faq(
        user_message=state["user_message"],
        intent=None,  # No filter → search everything
    )

    if result["matched"]:
        logger.info(f"Fallback answered from FAQ: {result['faq_slug']}")
        return {"response": result["response"]}

    return {"response": FALLBACK_RESPONSE}
