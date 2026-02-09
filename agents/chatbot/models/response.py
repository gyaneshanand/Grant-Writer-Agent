"""
Response models for the /chat endpoint.

In stateless mode, the response includes the updated conversation_history
so the FE can store it and send it back on the next request.
"""

from pydantic import BaseModel
from typing import Optional


class GrantResult(BaseModel):
    """A single grant from search results."""

    id: int
    opportunity_title: str
    description: str | None = None
    amount_low: float | None = None
    amount_high: float | None = None
    deadline_at: str | None = None
    url: str | None = None


class ExtractedEntitiesResponse(BaseModel):
    """Entities extracted from the user's query — shown as filter chips in FE."""

    interest_slugs: list[str] = []
    location_slugs: list[str] = []
    eligibility_criteria_slugs: list[str] = []


class ConversationTurnResponse(BaseModel):
    """A turn in the conversation — returned so FE can maintain history."""

    role: str
    content: str
    query_type: str | None = None
    extracted_entities: dict | None = None


class ChatResponse(BaseModel):
    """
    Full response payload for every /chat call.

    The FE uses these fields to:
    - response              → render as the chat bubble
    - query_type            → drive UI mode (search results vs FAQ vs greeting)
    - extracted_entities    → render clickable filter chips
    - total_grants          → grant count for display
    - cta_type              → determine which CTA button to show
    - user_type             → user subscription status
    - is_follow_up          → show "Refined from previous search" badge
    - session_id            → maintain session continuity
    - conversation_history  → FE stores this, sends back on next request (stateless mode)
    """

    response: str
    query_type: str
    extracted_entities: Optional[ExtractedEntitiesResponse] = None
    total_grants: Optional[int] = None
    cta_type: Optional[str] = None  # "signup" / "subscribe" / "view_grants"
    user_type: str = "guest-user"
    is_follow_up: bool = False
    session_id: str

    # In stateless mode, FE stores this and sends it back on next request
    conversation_history: list[ConversationTurnResponse] = []
