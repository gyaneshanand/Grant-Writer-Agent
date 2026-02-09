"""
Grant results formatting node.

Returns count + 2-sentence summary based on user_type.
"""

import json
import logging
from agents.chatbot.models.state import ChatbotState
from agents.chatbot.services.llm import llm
from agents.chatbot.utils.logging import log_node_execution

logger = logging.getLogger(__name__)


# CTA mapping by user type
CTA_CONFIG = {
    "guest-user": {
        "type": "signup",
        "text": "Click to Sign Up & View Full Report",
    },
    "unpaid-user": {
        "type": "subscribe",
        "text": "Subscribe to View Full List",
    },
    "paid-user": {
        "type": "view_grants",
        "text": "View Full List of {count} Grants",
    },
}


@log_node_execution
async def format_grant_results(state: ChatbotState) -> dict:
    """
    Format search results into a count + 2-sentence summary.

    Response varies by user_type:
    - guest-user: Summary + signup nudge
    - unpaid-user: Summary + view link
    - paid-user: Summary + view link
    """

    total_grants = state.get("total_grants", 0)
    results = state.get("search_results", [])
    entities = state.get("extracted_entities", {})
    user_type = state.get("user_type", "guest-user")

    if total_grants == 0:
        return {"response": _suggest_refinement(entities)}

    try:
        # Build context for LLM
        sample_titles = [r.get("opportunity_title", "") for r in results[:5]]
        sample_categories = set()
        for r in results[:10]:
            if r.get("interest_slugs"):
                for slug in r["interest_slugs"].split(","):
                    sample_categories.add(slug.replace("-", " ").strip())

        prompt = f"""Generate a 2-sentence summary for grant search results.

User searched: "{state["user_message"]}"
Total grants found: {total_grants}
Sample grant titles: {sample_titles}
Sample categories: {list(sample_categories)[:5]}

Guidelines:
- First sentence: Confirm what was found (e.g., "I found approximately {total_grants} grants for...")
- Second sentence: Brief overview of what the grants cover
- Be conversational and helpful
- Do NOT list individual grants
- Keep it under 50 words total"""

        result = await llm.ainvoke(prompt)
        summary = result.content.strip()

        # Add CTA nudge based on user_type
        cta = CTA_CONFIG.get(user_type, CTA_CONFIG["guest-user"])

        return {"response": summary}

    except Exception as e:
        logger.error(f"Response formatting failed: {e}")
        # Fallback without LLM
        return {
            "response": f"I found {total_grants} grants matching your search criteria."
        }


def _format_amount(low, high) -> str:
    """Format award range from amount_low / amount_high."""
    if low and high:
        return f"${low:,.0f} – ${high:,.0f}"
    elif high:
        return f"Up to ${high:,.0f}"
    elif low:
        return f"From ${low:,.0f}"
    return ""


def _suggest_refinement(entities: dict) -> str:
    """
    Template response when no results found.
    No LLM call — keeps costs at zero for empty result sets.
    """

    filters = []

    if entities.get("interest_slugs"):
        interests = ", ".join(
            s.replace("-", " ").replace(",", ", ")
            for s in entities["interest_slugs"]
        )
        filters.append(f"interests like **{interests}**")

    if entities.get("location_slugs"):
        locations = ", ".join(
            s.replace("-usa", "")
            .replace("-canada", "")
            .replace("-", " ")
            .title()
            for s in entities["location_slugs"]
        )
        filters.append(f"in **{locations}**")

    if entities.get("eligibility_criteria_slugs"):
        eligibility = ", ".join(
            s.replace("-", " ") for s in entities["eligibility_criteria_slugs"]
        )
        filters.append(f"for **{eligibility}**")

    filter_text = " and ".join(filters) if filters else "those criteria"

    return (
        f"I couldn't find active grants matching {filter_text}. "
        f"Here are some things you can try:\n\n"
        f"• **Broaden the location** — try a neighboring state or remove the location filter\n"
        f"• **Try related interests** — I can suggest similar categories\n"
        f"• **Remove eligibility filter** — some grants have unrestricted eligibility\n\n"
        f"What would you like to adjust?"
    )
