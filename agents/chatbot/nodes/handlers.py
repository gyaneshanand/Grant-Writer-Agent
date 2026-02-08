"""
Template-based handler nodes.

These nodes return static/template responses without LLM calls.
They handle intents where the response should be consistent.
"""

import random
from agents.chatbot.models.state import ChatbotState
from agents.chatbot.config import chatbot_settings

SUPPORT_EMAIL = chatbot_settings.support_email


# ── Greeting ───────────────────────────────────────────────


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


async def handle_account_support(state: ChatbotState) -> dict:
    """Account issues — redirect to support email."""

    return {
        "response": (
            f"For account-related issues like login, password reset, or "
            f"billing, please reach out to our support team at "
            f"**{SUPPORT_EMAIL}** — they'll be able to help you directly.\n\n"
            f"In the meantime, I can help you search for grants or answer "
            f"questions about the platform!"
        )
    }


# ── Eligibility Assessment ─────────────────────────────────


async def handle_eligibility_assessment(state: ChatbotState) -> dict:
    """Eligibility questions — explain what we can/can't do."""

    return {
        "response": (
            "I can show you the **eligibility criteria listed on any grant** "
            "(like required organization type, location requirements, etc.), "
            "but I'm not able to assess whether you or your organization "
            "would qualify — that depends on details only you and the "
            "funder would know.\n\n"
            "If you'd like, I can **search for grants and include their "
            "eligibility details** so you can evaluate the fit yourself. "
            "Just tell me what you're looking for!"
        )
    }


# ── Application Guidance ───────────────────────────────────


async def handle_application_guidance(state: ChatbotState) -> dict:
    """Application help — redirect to grant writers."""

    return {
        "response": (
            "The Grant Portal is a **grant directory** — we help you "
            "discover grants and foundations, but we don't handle "
            "applications directly.\n\n"
            "For application support, we have **professional grant writers** "
            f"who can help. Reach out to **{SUPPORT_EMAIL}** to get "
            "connected with one.\n\n"
            "In the meantime, I can help you **find grants** that match "
            "your needs — just tell me what you're looking for!"
        )
    }


# ── Fallback ───────────────────────────────────────────────


async def handle_fallback(state: ChatbotState) -> dict:
    """Catch-all for unrecognized intents."""

    return {
        "response": (
            "I'm not sure I understood that. Here's what I can help with:\n\n"
            "• **Finding grants** — tell me your interests, location, "
            "or organization type\n"
            "• **Platform questions** — pricing, features, how things work\n\n"
            f"For account issues or application help, please reach out "
            f"to **{SUPPORT_EMAIL}**."
        )
    }
