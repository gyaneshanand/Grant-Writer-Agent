"""
Grant results formatting node.

Converts raw SQL results into a conversational response.
Uses LLM when there are results, templates when empty.
"""

import json
import logging
from agents.chatbot.models.state import ChatbotState
from agents.chatbot.services.llm import llm
from agents.chatbot.utils.logging import log_node_execution

logger = logging.getLogger(__name__)


@log_node_execution
async def format_grant_results(state: ChatbotState) -> dict:
    """
    Format search results into a conversational response.

    Two paths:
    1. Has results → LLM summarizes conversationally
    2. No results  → Template suggests refinement (no LLM cost)
    """

    results = state.get("search_results", [])
    entities = state.get("extracted_entities", {})

    if not results:
        return {"response": _suggest_refinement(entities)}

    try:
        # Prepare results summary for the prompt
        results_summary = []
        for r in results:
            entry = {
                "title": r.get("opportunity_title", "Untitled"),
                "amount_range": _format_amount(r.get("amount_low"), r.get("amount_high")),
                "deadline": r.get("deadline_at", "Not specified"),
                "categories": r.get("interest_slugs", ""),
                "locations": r.get("province_slugs", ""),
                "eligibility": r.get("eligibility_slugs", ""),
            }
            results_summary.append(entry)

        prompt = f"""You are a friendly grant advisor for The Grant Portal.
Present these {len(results)} grants in a helpful, conversational way.

For each grant include:
- Grant name (bold it)
- Award range if available
- Deadline if available
- One sentence on why it matches their search

User asked: "{state["user_message"]}"
Their search filters: {json.dumps(entities)}

Results:
{json.dumps(results_summary, indent=2, default=str)}

Guidelines:
- Be concise but warm
- Use a numbered list, not a table
- If there are many results, briefly summarize the range
- End with a helpful suggestion (e.g., "Want me to narrow these down?")
- Don't mention SQL or technical details"""

        result = await llm.ainvoke(prompt)
        return {"response": result.content}

    except Exception as e:
        logger.error(f"Response formatting failed: {e}")
        # Fallback: simple list without LLM
        lines = [f"I found {len(results)} grants:\n"]
        for r in results[:5]:
            title = r.get("opportunity_title", "Untitled")
            lines.append(f"• **{title}**")
            amount = _format_amount(r.get("amount_low"), r.get("amount_high"))
            if amount:
                lines.append(f"  {amount}")
        return {"response": "\n".join(lines)}


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
