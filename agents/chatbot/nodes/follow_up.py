"""
Follow-up detection node.

Determines if the current message is a continuation of a prior
search. Uses conversation_history provided by the FE.
"""

import json
import logging
from agents.chatbot.models.state import ChatbotState
from agents.chatbot.services.llm import llm
from agents.chatbot.utils.logging import log_node_execution, logger

logger = logging.getLogger(__name__)


@log_node_execution
async def detect_follow_up(state: ChatbotState) -> dict:
    """
    Determine if current message continues a prior search.

    Conversation history comes from the FE (not DB).
    Skips LLM call if:
    - No conversation history (first message)
    - No prior extracted_entities in history (nothing to follow up on)
    """

    history = state.get("conversation_history", [])

    # No history → can't be a follow-up
    if not history:
        return {"is_follow_up": False, "follow_up_context": None}

    # Find the most recent extracted entities from history
    last_entities = None
    for turn in reversed(history):
        entities = turn.get("extracted_entities")
        if entities and isinstance(entities, dict):
            # Check it has at least one non-empty slug list
            has_slugs = any(
                entities.get(k)
                for k in [
                    "interest_slugs",
                    "location_slugs",
                    "eligibility_criteria_slugs",
                ]
            )
            if has_slugs:
                last_entities = entities
                break

    # No prior search entities → nothing to follow up on
    if not last_entities:
        return {"is_follow_up": False, "follow_up_context": None}

    try:
        # Build a concise version of recent history for the prompt
        recent = []
        for turn in history[-6:]:  # Last 6 turns (3 exchanges)
            recent.append(
                {"role": turn["role"], "content": turn["content"][:200]}
            )

        prompt = f"""Determine if this new message is a follow-up to a previous grant search.

Previous search filters: {json.dumps(last_entities)}

Recent conversation:
{json.dumps(recent, indent=2)}

New message: "{state["user_message"]}"

A message IS a follow-up if the user wants to MODIFY the previous search:
- Change location: "what about in Texas?" "show me California ones"
- Change interest: "how about education grants instead?"
- Add/remove filters: "but for nonprofits" "without the location filter"
- See more: "show me more" "any others?"

A message is NOT a follow-up if:
- It's a completely new topic or new search from scratch
- It's a greeting or general question
- It asks about pricing, account, or platform features

Return ONLY valid JSON, no markdown:
{{"is_follow_up": true, "reason": "user wants to change location"}}
or
{{"is_follow_up": false, "reason": "new topic"}}"""

        result = await llm.ainvoke(prompt)
        content = result.content.strip()

        # Clean markdown fences if present
        if content.startswith("```"):
            content = content.split("\n", 1)[1]
        if content.endswith("```"):
            content = content.rsplit("```", 1)[0]

        parsed = json.loads(content.strip())
        is_follow_up = parsed.get("is_follow_up", False)

        logger.info(
            f"Follow-up detection: {is_follow_up} "
            f"(reason: {parsed.get('reason', 'unknown')})"
        )

        return {
            "is_follow_up": is_follow_up,
            "follow_up_context": last_entities if is_follow_up else None,
        }

    except (json.JSONDecodeError, Exception) as e:
        logger.warning(f"Follow-up detection failed: {e}")
        return {"is_follow_up": False, "follow_up_context": None}
