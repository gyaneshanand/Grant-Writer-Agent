"""
LangGraph state definition.

This TypedDict flows through every node in the graph.
Each node reads what it needs and returns a partial dict
that gets merged into the state.
"""

from typing import TypedDict, Optional, Literal


class ChatbotState(TypedDict):
    """The state object that flows through every LangGraph node."""

    # ── Input (set by FastAPI before graph.ainvoke) ─────────
    user_message: str
    session_id: str
    user_id: Optional[int]
    conversation_mode: Literal["stateless", "stateful"]

    # ── Filled by load_conversation ─────────────────────────
    # In stateless mode: populated from request body
    # In stateful mode: loaded from DB
    conversation_history: list[dict]

    # ── Filled by detect_follow_up ──────────────────────────
    is_follow_up: bool
    follow_up_context: Optional[dict]

    # ── Filled by classify_query ────────────────────────────
    query_type: Optional[str]

    # ── Filled by extract_and_resolve_entities ──────────────
    extracted_entities: Optional[dict]

    # ── Filled by build_and_execute_search ──────────────────
    sql_query: Optional[str]
    search_results: Optional[list[dict]]

    # ── Filled by response formatters ───────────────────────
    response: str
