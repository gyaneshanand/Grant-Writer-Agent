"""
Chatbot API Controller.

Provides the /chat endpoint for the chatbot.
"""

import logging
from fastapi import APIRouter, HTTPException

from agents.chatbot.models.request import ChatRequest
from agents.chatbot.models.response import (
    ChatResponse,
    ConversationTurnResponse,
    ExtractedEntitiesResponse,
)
from agents.chatbot.graph.main_graph import chatbot_graph
from agents.chatbot.config import chatbot_settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chatbot", tags=["Chatbot"])


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Main chat endpoint.

    STATELESS MODE (default):
      1. FE sends full conversation_history + message
      2. Server uses that history as context (no DB read)
      3. Server processes and returns response + updated history
      4. FE stores the returned history, sends it again next time

    STATEFUL MODE:
      1. FE sends session_id + message only
      2. Server loads history from DB
      3. Server processes and returns response
      4. Server saves both turns to DB

    Both modes ALWAYS save to DB for analytics/audit (if DB configured).
    """

    logger.info(
        f"Chat request: mode={request.conversation_mode}, "
        f"session={request.session_id}, "
        f"user={request.user_id}, "
        f"user_type={request.user_type}, "
        f"history_turns={len(request.conversation_history)}, "
        f"message='{request.message[:50]}...'"
    )

    try:
        # ── Build initial state ────────────────────────────

        # Convert FE history to state format (stateless mode)
        fe_history = []
        if request.conversation_mode == "stateless":
            fe_history = [
                {
                    "role": turn.role,
                    "content": turn.content,
                    "query_type": turn.query_type,
                    "extracted_entities": turn.extracted_entities,
                }
                for turn in request.conversation_history
            ]

        initial_state = {
            "user_message": request.message,
            "session_id": request.session_id,
            "user_id": request.user_id,
            "user_type": request.user_type,
            "conversation_mode": request.conversation_mode,
            # In stateless: pre-populated from FE
            # In stateful: will be loaded by load_conversation node
            "conversation_history": fe_history,
            # Everything below gets filled by graph nodes
            "is_follow_up": False,
            "follow_up_context": None,
            "query_type": None,
            "extracted_entities": None,
            "sql_query": None,
            "search_results": None,
            "total_grants": None,
            "response": "",
        }

        # ── Run the graph ──────────────────────────────────
        final_state = await chatbot_graph.ainvoke(initial_state)

        # ── Build entities response ────────────────────────
        entities_resp = None
        if final_state.get("extracted_entities"):
            entities_resp = ExtractedEntitiesResponse(
                **final_state["extracted_entities"]
            )

        # ── Determine CTA type based on user_type ───────────
        user_type = request.user_type
        cta_type = {
            "guest-user": "signup",
            "unpaid-user": "view_grants",
            "paid-user": "view_grants",
        }.get(user_type, "signup")

        # ── Build updated conversation history ─────────────
        # Append the current user + assistant turns to history
        # FE stores this and sends it back on next request
        updated_history = [
            ConversationTurnResponse(
                role=t["role"],
                content=t["content"],
                query_type=t.get("query_type"),
                extracted_entities=t.get("extracted_entities"),
            )
            for t in final_state.get("conversation_history", [])
        ]

        # Add current user turn
        updated_history.append(
            ConversationTurnResponse(
                role="user",
                content=request.message,
                query_type=final_state["query_type"],
                extracted_entities=final_state.get("extracted_entities"),
            )
        )

        # Add current assistant turn
        updated_history.append(
            ConversationTurnResponse(
                role="assistant",
                content=final_state["response"],
                query_type=final_state["query_type"],
                extracted_entities=final_state.get("extracted_entities"),
            )
        )

        # Trim to last N turns to prevent unbounded growth
        max_turns = chatbot_settings.max_conversation_history * 2  # pairs
        if len(updated_history) > max_turns:
            updated_history = updated_history[-max_turns:]

        # ── Build response ─────────────────────────────────
        response = ChatResponse(
            response=final_state["response"],
            query_type=final_state["query_type"] or "other",
            extracted_entities=entities_resp,
            total_grants=final_state.get("total_grants"),
            cta_type=cta_type if final_state.get("total_grants") else None,
            user_type=user_type,
            is_follow_up=final_state.get("is_follow_up", False),
            session_id=request.session_id,
            conversation_history=updated_history,
        )

        logger.info(
            f"Response: query_type={response.query_type}, "
            f"total_grants={response.total_grants}, "
            f"cta_type={response.cta_type}, "
            f"follow_up={response.is_follow_up}, "
            f"history_turns={len(updated_history)}"
        )


        return response

    except Exception as e:
        logger.exception(f"Chat endpoint failed: {e}")
        raise HTTPException(
            status_code=500,
            detail="An error occurred processing your message. Please try again.",
        )


@router.get("/health")
async def chatbot_health():
    """Chatbot-specific health check."""
    from agents.chatbot.services.vector_store import get_vector_store

    vs = get_vector_store()
    vs_initialized = hasattr(vs, 'is_initialized') and vs.is_initialized()

    return {
        "status": "ok",
        "service": "chatbot",
        "database_configured": bool(chatbot_settings.database_url),
        "vector_store_provider": chatbot_settings.vector_store_provider,
        "vector_store_initialized": vs_initialized,
    }
