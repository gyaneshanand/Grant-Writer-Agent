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
        prompt = f"""You are a query classifier for The Grant Portal chatbot which is a platform/product that helps grant seekers to find grants. 
        Classify this user message into exactly ONE category. 

Categories:
- greeting: Hello, hi, thanks, goodbye, how are you, what can you do for me 
- grant_search: Looking for grants, funding, scholarships, foundations, or any query about searching specific grants ( exclude other grant eligibility and grant application related queries as they are product navigartion query)
- product_navigation: Questions about The Grant Portal platform itself — pricing, features, how to use it, plans, subscriptions, weekly, monthly, quarterly, yearly subscription etc
- account_support: Login issues, password reset, billing problems, account deletion, profile updates, cancellations, refunds, email verification
- eligibility_assessment: "Am I eligible?", "Can my organization apply?", "Do I qualify?", filtering grants by eligibility
- application_guidance: "How do I apply?", "What documents are needed?", "Help me with my application", grant writer questions
- other: Anything that doesn't fit the above categories

Here are some examples:
- "cancel my subscription" → account_support
- "I was charged twice" → account_support
- "I can't log in" → account_support
- "I can't reset my password" → account_support
- "delete my account" → account_support
- "I want a refund" → account_support
- "how do I apply for a grant?" → application_guidance
- "can you apply without subscribing?" → application_guidance
- "how much do grant writers charge?" → application_guidance
- "how to get listed as a grant writer" → application_guidance
- "how can i apply for grants?" → application_guidance
- "our nonprofit is 1 year old, can we apply?" → eligibility_assessment
- "how do I find grants I'm eligible for?" → eligibility_assessment
- "are there guarantees for getting grants?" → eligibility_assessment
- "how does your site work?" → product_navigation
- "what does deadline ongoing mean?" → product_navigation
- "do you offer an API?" → product_navigation
- "can I export to excel?" → product_navigation
- "how often do you update grants?" → product_navigation
- "grants for education in California" → grant_search
- "nonprofit grants in Texas for veterans" → grant_search
- "I would like to talk with someone about a non-profit grant" → other
- "Is there any way I can filter to only see grants for people eligible in one state?" → other
- "Is there a way to filter counties within a state filter; grants for my county?" → other
- "How can I search for a particular funder by name?" → other
- "I need to access my invoice" → account_support
- "do you offer grants?" → other

User message: "{state["user_message"]}"

You need understand the user message and intent and classify it into one of the above categories.

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
