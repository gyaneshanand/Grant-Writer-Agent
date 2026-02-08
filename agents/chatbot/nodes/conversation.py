"""
Conversation persistence nodes.

Supports two modes:

STATELESS (default):
  load_conversation → history already in state from FE request, pass through
  save_conversation → always saves to DB (analytics/audit)

STATEFUL:
  load_conversation → fetches last N turns from MySQL
  save_conversation → always saves to DB (session continuity)

Both modes always write to DB. The difference is only in how
conversation context is LOADED for the current request.

NOTE: If DATABASE_URL is not configured, save operations are skipped.
"""

import json
import logging
from agents.chatbot.models.state import ChatbotState
from agents.chatbot.config import chatbot_settings
from agents.chatbot.utils.logging import log_node_execution, logger

logger = logging.getLogger(__name__)


# ── Load ───────────────────────────────────────────────────


async def load_conversation(state: ChatbotState) -> dict:
    """
    Node 1: Load conversation history.

    STATELESS mode:
        History was already placed in state by FastAPI from the
        request body. We just pass through — no DB call.

    STATEFUL mode:
        Fetch last N turns from MySQL for this session_id.
    """

    mode = state.get("conversation_mode", "stateless")

    # ── Stateless: FE already sent history ─────────────────
    if mode == "stateless":
        history = state.get("conversation_history", [])
        logger.info(
            f"[stateless] Using {len(history)} turns from FE "
            f"(session: {state['session_id']})"
        )
        return {"conversation_history": history}

    # ── Stateful: load from DB ─────────────────────────────
    if not chatbot_settings.database_url:
        logger.warning("Database not configured - stateful mode unavailable")
        return {"conversation_history": []}

    try:
        from agents.chatbot.services.database import ensure_database
        database = await ensure_database()

        if database is None:
            return {"conversation_history": []}

        rows = await database.fetch_all(
            """
            SELECT role, content, query_type, extracted_entities, created_at
            FROM chatbot_conversations
            WHERE session_id = :sid
            ORDER BY created_at DESC
            LIMIT :limit
            """,
            {
                "sid": state["session_id"],
                "limit": chatbot_settings.max_conversation_history,
            },
        )

        # Reverse to chronological order (query was DESC for LIMIT efficiency)
        history = [
            {
                "role": dict(r)["role"],
                "content": dict(r)["content"],
                "query_type": dict(r)["query_type"],
                "extracted_entities": json.loads(
                    dict(r)["extracted_entities"] or "null"
                ),
            }
            for r in reversed(rows)
        ]

        logger.info(
            f"[stateful] Loaded {len(history)} turns from DB "
            f"(session: {state['session_id']})"
        )
        return {"conversation_history": history}

    except Exception as e:
        logger.error(f"Failed to load conversation: {e}")
        return {"conversation_history": []}


# ── Save ───────────────────────────────────────────────────


@log_node_execution
async def save_conversation(state: ChatbotState) -> dict:
    """
    Final node: Persist user message + bot response to MySQL.

    ALWAYS runs regardless of mode — provides:
    - Analytics (query_type distribution, search result counts)
    - Audit trail
    - Stateful fallback (if FE loses state, server has history)

    If database is not configured, this is a no-op.
    """

    if not chatbot_settings.database_url:
        logger.debug("Database not configured - skipping conversation save")
        return state

    try:
        from agents.chatbot.services.database import ensure_database
        database = await ensure_database()

        if database is None:
            return state

        # Save user turn
        await database.execute(
            """
            INSERT INTO chatbot_conversations
                (session_id, user_id, role, content, query_type,
                 extracted_entities, created_at)
            VALUES
                (:sid, :uid, 'user', :content, :qt, :entities, NOW())
            """,
            {
                "sid": state["session_id"],
                "uid": state.get("user_id"),
                "content": state["user_message"],
                "qt": state["query_type"],
                "entities": json.dumps(state.get("extracted_entities")),
            },
        )

        # Save assistant turn
        await database.execute(
            """
            INSERT INTO chatbot_conversations
                (session_id, user_id, role, content, query_type,
                 search_results_count, created_at)
            VALUES
                (:sid, :uid, 'assistant', :content, :qt, :count, NOW())
            """,
            {
                "sid": state["session_id"],
                "uid": state.get("user_id"),
                "content": state["response"],
                "qt": state["query_type"],
                "count": len(state.get("search_results") or []),
            },
        )

        logger.info(
            f"[{state.get('conversation_mode', 'stateless')}] "
            f"Saved conversation (session: {state['session_id']})"
        )

    except Exception as e:
        logger.error(f"Failed to save conversation: {e}")
        # Don't fail the response if save fails

    return state  # Pass through unchanged
