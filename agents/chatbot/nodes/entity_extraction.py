"""
Entity extraction and resolution node.

Combines extract + validate + merge in a single step.
LLM extracts structured data, Pydantic strips invalid slugs.
"""

import json
import logging
from pydantic import BaseModel, field_validator
from langchain.prompts import ChatPromptTemplate
from agents.chatbot.models.state import ChatbotState
from agents.chatbot.services.llm import llm
from agents.chatbot.data.slugs import (
    VALID_INTEREST_SLUGS,
    VALID_LOCATION_SLUGS,
    VALID_ELIGIBILITY_SLUGS,
)

logger = logging.getLogger(__name__)


class ExtractedEntities(BaseModel):
    """Validated entity extraction result. Strips invalid slugs."""

    interest_slugs: list[str] = []
    location_slugs: list[str] = []
    eligibility_criteria_slugs: list[str] = []

    @field_validator("interest_slugs")
    @classmethod
    def validate_interests(cls, v):
        valid = [s for s in v if s in VALID_INTEREST_SLUGS]
        if len(valid) != len(v):
            dropped = set(v) - set(valid)
            logger.warning(f"Dropped invalid interest slugs: {dropped}")
        return valid

    @field_validator("location_slugs")
    @classmethod
    def validate_locations(cls, v):
        valid = [s for s in v if s in VALID_LOCATION_SLUGS]
        if len(valid) != len(v):
            dropped = set(v) - set(valid)
            logger.warning(f"Dropped invalid location slugs: {dropped}")
        return valid

    @field_validator("eligibility_criteria_slugs")
    @classmethod
    def validate_eligibility(cls, v):
        valid = [s for s in v if s in VALID_ELIGIBILITY_SLUGS]
        if len(valid) != len(v):
            dropped = set(v) - set(valid)
            logger.warning(f"Dropped invalid eligibility slugs: {dropped}")
        return valid


ENTITY_PROMPT = ChatPromptTemplate.from_template(
    """You are an expert at extracting structured grant search parameters from natural language queries.

Map the user's query to the EXACT slugs from the lists below. Only use slugs that appear in these lists.

**INTERESTS** (pick the most relevant ones):
{interest_slugs}

**LOCATIONS** (map to province/state slugs):
{location_slugs}

**ELIGIBILITY CRITERIA** (who is applying):
{eligibility_slugs}

User query: "{query}"

Instructions:
- For interests: identify the grant topic/category. Map creatively but accurately.
  Example: "temples" → "faith-based", "elderly" → "aging/seniors"
- For locations: map city/state/province names to their slugs.
  Example: "California" → "california-usa", "Toronto" → "ontario-canada"
- For eligibility: identify who the applicant is.
  Example: "nonprofit" → "non-profit-organizations-with-501-c-3-designation"
  Example: "old age people" → "individuals"
  Example: "small business" → "small-businesses"
- If something doesn't clearly map to any slug, omit it.
- Return empty lists for dimensions not mentioned in the query.

Return ONLY valid JSON, no markdown fences, no explanation:
{{"interest_slugs": [], "location_slugs": [], "eligibility_criteria_slugs": []}}"""
)


async def extract_and_resolve_entities(state: ChatbotState) -> dict:
    """
    Combined extraction + validation + merge node.

    1. LLM extracts entities from user message → raw slugs
    2. Pydantic validates against known DB slugs → clean slugs
    3. If follow-up, merges new entities with prior context
    """

    try:
        prompt = ENTITY_PROMPT.format(
            query=state["user_message"],
            interest_slugs="\n".join(sorted(VALID_INTEREST_SLUGS)),
            location_slugs="\n".join(sorted(VALID_LOCATION_SLUGS)),
            eligibility_slugs="\n".join(sorted(VALID_ELIGIBILITY_SLUGS)),
        )

        result = await llm.ainvoke(prompt)

        content = result.content.strip()
        if content.startswith("```"):
            content = content.split("\n", 1)[1]
        if content.endswith("```"):
            content = content.rsplit("```", 1)[0]
        content = content.strip()

        parsed = json.loads(content)
        entities = ExtractedEntities(**parsed)

    except (json.JSONDecodeError, Exception) as e:
        logger.error(f"Entity extraction failed: {e}")
        entities = ExtractedEntities()

    # Merge with follow-up context
    if state["is_follow_up"] and state["follow_up_context"]:
        prior = state["follow_up_context"]
        merged = {
            "interest_slugs": (
                entities.interest_slugs
                or prior.get("interest_slugs", [])
            ),
            "location_slugs": (
                entities.location_slugs
                or prior.get("location_slugs", [])
            ),
            "eligibility_criteria_slugs": (
                entities.eligibility_criteria_slugs
                or prior.get("eligibility_criteria_slugs", [])
            ),
        }
        entities = ExtractedEntities(**merged)
        logger.info(f"Merged follow-up entities: {entities.model_dump()}")

    result_dict = entities.model_dump()
    logger.info(f"Extracted entities: {result_dict}")
    return {"extracted_entities": result_dict}
