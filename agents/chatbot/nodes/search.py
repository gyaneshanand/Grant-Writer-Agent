"""
Grant search node.

Builds parameterized SQL from validated entity slugs and executes
against the TGP MySQL database.

NOTE: This node requires DATABASE_URL to be configured.
If database is not available, returns empty results with a message.
"""

from agents.chatbot.models.state import ChatbotState
from agents.chatbot.config import chatbot_settings
from agents.chatbot.services.database import ensure_database
from agents.chatbot.utils.logging import log_node_execution, logger


@log_node_execution
async def build_and_execute_search(state: ChatbotState) -> dict:
    """
    Build parameterized SQL from entity slugs and execute.

    Uses EXISTS subqueries per filter dimension.
    Only adds EXISTS clauses for dimensions that have active filters.
    """

    # Check if database is configured
    if not chatbot_settings.database_url:
        logger.warning("Database not configured - returning placeholder response")
        return {
            "search_results": [],
            "sql_query": None,
        }

    try:
        db = await ensure_database()

        entities = state.get("extracted_entities", {})
        conditions = ["g.status = 2"]  # status 2 = Active grants
        params: dict = {}
        exists_clauses: list[str] = []

        # ── Interest filter (EXISTS subquery) ──────────────────
        if entities.get("interest_slugs"):
            placeholders = []
            for j, slug in enumerate(entities["interest_slugs"]):
                key = f"int_{j}"
                placeholders.append(f":{key}")
                params[key] = slug

            exists_clauses.append(f"""
                EXISTS (
                    SELECT 1
                    FROM grants_info_interest_map gim_f
                    JOIN interests i_f ON gim_f.interest_id = i_f.id
                    WHERE gim_f.grant_info_id = g.id
                      AND i_f.slug IN ({', '.join(placeholders)})
                )
            """)

        # ── Location filter (EXISTS subquery) ──────────────────
        if entities.get("location_slugs"):
            placeholders = []
            for j, slug in enumerate(entities["location_slugs"]):
                key = f"loc_{j}"
                placeholders.append(f":{key}")
                params[key] = slug

            exists_clauses.append(f"""
                EXISTS (
                    SELECT 1
                    FROM grants_info_locations_map glm_f
                    JOIN provinces p_f ON glm_f.province_id = p_f.id
                    WHERE glm_f.grant_info_id = g.id
                      AND p_f.slug IN ({', '.join(placeholders)})
                )
            """)

        # ── Eligibility filter (EXISTS subquery) ───────────────
        if entities.get("eligibility_criteria_slugs"):
            placeholders = []
            for j, slug in enumerate(entities["eligibility_criteria_slugs"]):
                key = f"elig_{j}"
                placeholders.append(f":{key}")
                params[key] = slug

            exists_clauses.append(f"""
                EXISTS (
                    SELECT 1
                    FROM grants_info_eligibilty_map gem_f
                    JOIN eligibilties e_f ON gem_f.eligibilty_id = e_f.id
                    WHERE gem_f.grant_info_id = g.id
                      AND e_f.slug IN ({', '.join(placeholders)})
                )
            """)

        # ── Combine conditions ─────────────────────────────────
        all_conditions = conditions + exists_clauses
        where_clause = " AND ".join(all_conditions)

        # ── Build final query (no LIMIT - get all matching grants) ──
        query = f"""
            SELECT
                g.id,
                g.opportunity_title,
                g.amount_low,
                g.amount_high,
                g.deadline_at,
                GROUP_CONCAT(DISTINCT e.slug) AS eligibility_slugs,
                GROUP_CONCAT(DISTINCT i.slug) AS interest_slugs,
                GROUP_CONCAT(DISTINCT p.slug) AS province_slugs
            FROM grants_info g
            LEFT JOIN grants_info_eligibilty_map gem
                   ON g.id = gem.grant_info_id
            LEFT JOIN eligibilties e
                   ON gem.eligibilty_id = e.id
            LEFT JOIN grants_info_interest_map gim
                   ON g.id = gim.grant_info_id
            LEFT JOIN interests i
                   ON gim.interest_id = i.id
            LEFT JOIN grants_info_locations_map glm
                   ON g.id = glm.grant_info_id
            LEFT JOIN provinces p
                   ON glm.province_id = p.id
            WHERE {where_clause}
            GROUP BY g.id
            ORDER BY g.deadline_at ASC
        """

        # Log the generated SQL for visibility
        logger.info(f"🔍 Generated SQL Query:\n{query}")
        logger.debug(f"🔍 SQL Params: {params}")

        results = await db.fetch_all(query=query, values=params)
        processed_results = []
        for r in results:
            row = dict(r)
            # Convert datetime/date objects to strings for JSON
            if row.get("deadline_at"):
                row["deadline_at"] = str(row["deadline_at"])
            processed_results.append(row)

        total_grants = len(processed_results)
        logger.info(f"Search returned {total_grants} grants")
        return {
            "search_results": processed_results,
            "total_grants": total_grants,
            "sql_query": query,
        }

    except Exception as e:
        logger.error(f"Search query failed: {e}")
        return {"search_results": [], "total_grants": 0, "sql_query": None}
