"""
Request models for the /chat endpoint.

Supports two modes:
1. STATELESS (default): FE sends full conversation_history + message
   - No DB reads for conversation loading
   - FE is the source of truth for conversation state

2. STATEFUL: Server loads conversation from DB using session_id
   - Session survives page refresh, device switch
   - Server is the source of truth

Toggle via: conversation_mode in request (defaults to "stateless")
Both modes ALWAYS save to DB (for analytics/audit).
"""

import uuid
from pydantic import BaseModel, Field
from typing import Optional


class ConversationTurn(BaseModel):
    """A single turn in the conversation history (sent by FE in stateless mode)."""

    role: str = Field(..., pattern="^(user|assistant)$")
    content: str
    query_type: Optional[str] = None
    extracted_entities: Optional[dict] = None


class ChatRequest(BaseModel):
    """
    Incoming chat request.

    STATELESS mode (default):
        FE sends conversation_history + message.
        Server doesn't read from DB for context.

    STATEFUL mode:
        FE sends only session_id + message.
        Server loads history from DB.
    """

    # ── Always required ────────────────────────────────────
    message: str = Field(
        ...,
        min_length=1,
        max_length=1000,
        description="User's current chat message",
    )

    session_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Session UUID — persists across page refreshes",
    )

    user_id: int | None = Field(
        default=None,
        description="Injected by auth layer. Not sent by browser.",
    )

    # ── Mode toggle ────────────────────────────────────────
    conversation_mode: str = Field(
        default="stateless",
        pattern="^(stateless|stateful)$",
        description="'stateless' = FE sends history, 'stateful' = server loads from DB",
    )

    # ── Stateless mode fields ──────────────────────────────
    conversation_history: list[ConversationTurn] = Field(
        default_factory=list,
        description="Full conversation history (stateless mode). Empty in stateful mode.",
    )
