"""
Product navigation handler with RAG.

Handles questions about The Grant Portal platform:
- Pricing → Uses PRICING_CONTEXT (no RAG needed)
- Other questions → Uses vector store RAG
"""

import logging
from agents.chatbot.models.state import ChatbotState
from agents.chatbot.services.llm import llm
from agents.chatbot.services.vector_store import get_vector_store
from agents.chatbot.config import PRICING_CONTEXT, chatbot_settings
from agents.chatbot.utils.logging import log_node_execution, logger


@log_node_execution
async def handle_product_navigation(state: ChatbotState) -> dict:
    """
    Handle product/platform questions.

    Two paths:
    1. Pricing questions → Use PRICING_CONTEXT directly
    2. Other questions → RAG from vector store
    """

    user_message = state["user_message"].lower()

    # Check if it's a pricing question
    pricing_keywords = ["price", "pricing", "cost", "plan", "subscription", "pay", "fee", "free", "weekly", "monthly", "quarterly", "yearly", "subscribe"]
    is_pricing_question = any(kw in user_message for kw in pricing_keywords)

    if is_pricing_question:
        return await _handle_pricing_question(state)

    # Otherwise, use RAG
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
- Mention the free trial for paid plans
- Ask the users to visit the pricing page for full details https://www.thegrantportal.com/pricing-and-plans
- Nudge them to subscribe to the paid plan"""

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
    """Answer product questions using RAG from vector store."""

    try:
        # from agents.chatbot.services.vector_store import get_retriever, get_vector_store # Removed, now imported at top

        # Check if vector store is initialized
        vs = get_vector_store()
        if hasattr(vs, 'is_initialized') and not vs.is_initialized():
            logger.warning("Vector store not initialized - using fallback")
            return {
                "response": (
                    "I can help with questions about The Grant Portal! "
                    "For detailed information, please visit our website at thegrantportal.com "
                    "or ask me about pricing, features, or how to find grants."
                )
            }

        # Use RAG
        retriever = vs.get_retriever(k=4)
        docs = retriever.invoke(state["user_message"])

        if not docs:
            return {
                "response": (
                    "I don't have specific information about that. "
                    "For detailed help, please visit thegrantportal.com or contact support."
                )
            }

        # Build context from retrieved docs
        context_parts = []
        sources = set()
        for doc in docs:
            context_parts.append(doc.page_content)
            source = doc.metadata.get("source", "")
            if source:
                sources.add(source)

        # Log retrieval for visibility
        user_message = state["user_message"]
        logger.info(f"📚 RAG Retrieval: Found {len(docs)} documents for query: '{user_message}'")
        
        context = "\n\n".join(context_parts)

        prompt = f"""You are a helpful assistant for The Grant Portal.
Answer the user's question based on this context:

{context}

User question: "{state["user_message"]}"

Guidelines:
- Be concise and friendly
- Only use information from the context
- If the context doesn't fully answer the question, say so
- At the end, cite the source(s) you used"""

        result = await llm.ainvoke(prompt)

        # Append sources if available
        response = result.content
        if sources:
            source_list = "\n".join(f"- {s}" for s in sources)
            response += f"\n\n**Sources:**\n{source_list}"

        return {"response": response}

    except Exception as e:
        logger.error(f"RAG question failed: {e}")
        return {
            "response": (
                "I had trouble looking that up. For detailed help, please visit "
                "thegrantportal.com or contact support@thegrantportal.com."
            )
        }
