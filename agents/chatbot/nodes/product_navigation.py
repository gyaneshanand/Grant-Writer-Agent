"""
Product navigation handler with RAG.

Handles questions about The Grant Portal platform:
- Pricing → Uses PRICING_CONTEXT (no RAG needed)
- Other questions → Uses FAQ-aware RAG from vector store
"""

import logging
from agents.chatbot.models.state import ChatbotState
from agents.chatbot.services.llm import llm
from agents.chatbot.config import PRICING_CONTEXT, chatbot_settings
from agents.chatbot.nodes.faq_rag import query_faq
from agents.chatbot.utils.logging import log_node_execution, logger

SUPPORT_EMAIL = chatbot_settings.support_email

PRODUCT_NAVIGATION_FALLBACK = (
    "I don't have specific information about that. "
    "Please use the Contact Us page at "
    "https://www.thegrantportal.com/contact-us "
    f"or email **{SUPPORT_EMAIL}** for assistance."
)


@log_node_execution
async def handle_product_navigation(state: ChatbotState) -> dict:
    """
    Handle product/platform questions.

    Two paths:
    1. Pricing questions → Use PRICING_CONTEXT directly
    2. Other questions → FAQ-aware RAG from vector store
    """

    user_message = state["user_message"].lower()

    # Check if it's a pricing question
    pricing_keywords = ["price", "pricing", "cost", "plan", "subscription", "pay", "fee", "free", "weekly", "monthly", "quarterly", "yearly", "subscribe"]
    is_pricing_question = any(kw in user_message for kw in pricing_keywords)

    if is_pricing_question:
        return await _handle_pricing_question(state)

    # Otherwise, use FAQ-aware RAG
    return await _handle_rag_question(state)


@log_node_execution
async def _handle_pricing_question(state: ChatbotState) -> dict:
    """Answer pricing questions using static context."""

    try:
        prompt = f"""You are a helpful assistant for The Grant Portal.
Answer the user's question about pricing based on this context:

{PRICING_CONTEXT}

User question: "{state["user_message"]}"

Guidelines:
- Be concise and friendly
- Highlight the plan that seems most relevant to their needs
- Ask the users to visit the pricing page for full details https://www.thegrantportal.com/pricing-and-plans
- Nudge them to subscribe to the paid plan
- Keep it brief and concise (under 50 words)
- Ask the user if they need details on any specific plan
"""

        result = await llm.ainvoke(prompt)
        return {"response": result.content}

    except Exception as e:
        logger.error(f"Pricing question failed: {e}")
        return {
            "response": (
                "We offer Free, Starter ($29/mo), Pro ($79/mo), and Enterprise plans. "
                "Visit our pricing page for full details, or ask me about a specific plan!"
            )
        }


@log_node_execution
async def _handle_rag_question(state: ChatbotState) -> dict:
    """Answer product questions using FAQ-aware RAG."""

    result = await query_faq(
        user_message=state["user_message"],
        intent="product_navigation",
    )

    if result["matched"]:
        logger.info(f"Product navigation answered from FAQ: {result['faq_slug']}")
        return {"response": result["response"]}

    return {"response": PRODUCT_NAVIGATION_FALLBACK}
