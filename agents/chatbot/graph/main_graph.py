"""
Main LangGraph state machine.

Flow:
  detect_follow_up → classify_query → [route] → handler → save_conversation → END
"""

import logging
from langgraph.graph import StateGraph, END
from agents.chatbot.models.state import ChatbotState

from agents.chatbot.nodes.conversation import save_conversation
from agents.chatbot.nodes.follow_up import detect_follow_up
from agents.chatbot.nodes.classifier import classify_query, route_by_type
from agents.chatbot.nodes.entity_extraction import extract_and_resolve_entities
from agents.chatbot.nodes.search import build_and_execute_search
from agents.chatbot.nodes.response import format_grant_results
from agents.chatbot.nodes.product_navigation import handle_product_navigation
from agents.chatbot.nodes.handlers import (
    handle_greeting,
    handle_fallback,
    handle_account_support,
    handle_eligibility_assessment,
    handle_application_guidance,
)

logger = logging.getLogger(__name__)


def build_graph() -> StateGraph:
    """
    Construct and compile the chatbot LangGraph.

    Entry point is detect_follow_up.
    """

    graph = StateGraph(ChatbotState)

    # ── Register all nodes ──────────────────────────────────

    # Spine
    graph.add_node("detect_follow_up", detect_follow_up)
    graph.add_node("classify_query", classify_query)
    graph.add_node("save_conversation", save_conversation)

    # Branch handlers
    graph.add_node("handle_greeting", handle_greeting)
    graph.add_node("handle_product_navigation", handle_product_navigation)
    graph.add_node("handle_account_support", handle_account_support)
    graph.add_node("handle_eligibility_assessment", handle_eligibility_assessment)
    graph.add_node("handle_application_guidance", handle_application_guidance)
    graph.add_node("handle_fallback", handle_fallback)

    # Grant search pipeline
    graph.add_node("extract_and_resolve_entities", extract_and_resolve_entities)
    graph.add_node("build_and_execute_search", build_and_execute_search)
    graph.add_node("format_grant_results", format_grant_results)

    # ── Entry point ─────────────────────────────────────────

    graph.set_entry_point("detect_follow_up")
    graph.add_edge("detect_follow_up", "classify_query")

    # ── Conditional routing ─────────────────────────────────

    graph.add_conditional_edges(
        "classify_query",
        route_by_type,
        {
            "greeting": "handle_greeting",
            "grant_search": "extract_and_resolve_entities",
            "product_navigation": "handle_product_navigation",
            "account_support": "handle_account_support",
            "eligibility_assessment": "handle_eligibility_assessment",
            "application_guidance": "handle_application_guidance",
            "other": "handle_fallback",
        },
    )

    # ── Grant search pipeline ───────────────────────────────

    graph.add_edge("extract_and_resolve_entities", "build_and_execute_search")
    graph.add_edge("build_and_execute_search", "format_grant_results")

    # ── All paths → save → END ──────────────────────────────

    terminal_nodes = [
        "handle_greeting",
        "handle_product_navigation",
        "handle_account_support",
        "handle_eligibility_assessment",
        "handle_application_guidance",
        "handle_fallback",
        "format_grant_results",
    ]

    for node in terminal_nodes:
        graph.add_edge(node, "save_conversation")

    graph.add_edge("save_conversation", END)

    return graph.compile()


# Compiled once on import, reused for every request
chatbot_graph = build_graph()

logger.info("LangGraph chatbot graph compiled successfully")
