"""
Query classification node.

Routes user messages to the correct handler based on intent.
"""

import logging
from agents.chatbot.models.state import ChatbotState
from agents.chatbot.services.llm import llm
from agents.chatbot.utils.logging import log_node_execution, logger

logger = logging.getLogger(__name__)

VALID_QUERY_TYPES = {
    "greeting",
    "grant_search",
    "product_navigation",
    "account_support",
    "eligibility_assessment",
    "application_guidance",
    "other",
}


@log_node_execution
async def classify_query(state: ChatbotState) -> dict:
    """
    Classify user intent to route to correct handler.

    Optimization: If follow-up was detected, skip classification
    entirely and route directly to grant_search.
    """

    # Follow-ups always go to grant_search
    if state["is_follow_up"]:
        logger.info("Follow-up detected → auto-routing to grant_search")
        return {"query_type": "grant_search"}

    try:
        prompt = f"""Classify this user message into exactly ONE category.

Categories:
- greeting: Hello, hi, thanks, goodbye, how are you
- grant_search: Looking for grants, funding, scholarships, foundations, or any query about finding/discovering specific grants
- product_navigation: Questions about The Grant Portal platform itself — pricing, features, how to use it, plans, subscriptions
- account_support: Login issues, password reset, billing problems, account deletion, profile updates
- eligibility_assessment: "Am I eligible?", "Can my organization apply?", "Do I qualify?"
- application_guidance: "How do I apply?", "What documents are needed?", "Help me with my application"
- other: Anything that doesn't fit the above categories

User message: "{state["user_message"]}"

Return ONLY the category name, nothing else."""

        result = await llm.ainvoke(prompt)
        query_type = result.content.strip().strip('"').strip("'").lower()

        if query_type not in VALID_QUERY_TYPES:
            logger.warning(
                f"LLM returned invalid query_type '{query_type}', "
                "defaulting to 'other'"
            )
            query_type = "other"

        logger.info(f"🧠 Classification Result: {query_type}")
        return {"query_type": query_type}

    except Exception as e:
        logger.error(f"Classification failed: {e}")
        return {"query_type": "other"}


def route_by_type(state: ChatbotState) -> str:
    """Conditional edge function for LangGraph routing."""
    return state["query_type"]
