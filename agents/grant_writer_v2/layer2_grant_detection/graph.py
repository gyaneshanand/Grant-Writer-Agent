"""
LangGraph StateGraph for Layer 2 grant detection.

Nodes:
  crawl_agent        — tool-calling agent loop (fetch_page / find_links / extract_pdf)
  tools              — ToolNode executing the 3 tools
  identify_programs  — LLM: corpus → distinct programs
  evaluate_rules     — LLM × N: 7-rule evaluation per program
  aggregate_verdicts — pure Python rollup

Flow:
  START → crawl_agent → tools? → crawl_agent (loop) → identify_programs → evaluate_rules → aggregate_verdicts → END
"""
import uuid
from typing import Any

from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import ToolNode
from langchain_core.messages import HumanMessage, SystemMessage

from agents.grant_writer_v2.config import v2_settings
from agents.grant_writer_v2.core.llm import get_chat_model, BudgetExceeded, get_run_cost
from agents.grant_writer_v2.core.logger import get_logger
from agents.grant_writer_v2.layer2_grant_detection.prompts import CRAWL_AGENT_SYSTEM
from agents.grant_writer_v2.layer2_grant_detection.schemas import GraphState
from agents.grant_writer_v2.layer2_grant_detection.tools import make_tools
from agents.grant_writer_v2.layer2_grant_detection.program_identifier import identify_programs
from agents.grant_writer_v2.layer2_grant_detection.rule_evaluator import evaluate_all_programs
from agents.grant_writer_v2.layer2_grant_detection.verdict_aggregator import aggregate

logger = get_logger("layer2.graph")


def _over_cap(state: GraphState) -> bool:
    return (
        state.get("iterations", 0) >= v2_settings.V2_L2_MAX_ITERATIONS
        or state.get("pages_fetched", 0) >= v2_settings.V2_L2_MAX_PAGES
        or state.get("bytes_fetched", 0) >= v2_settings.V2_L2_MAX_BYTES
        or state.get("cost_usd", 0.0) >= v2_settings.V2_L2_MAX_COST_USD
    )


def _stop_reason(state: GraphState) -> str:
    if state.get("iterations", 0) >= v2_settings.V2_L2_MAX_ITERATIONS:
        return "max_iterations"
    if state.get("pages_fetched", 0) >= v2_settings.V2_L2_MAX_PAGES:
        return "max_pages"
    if state.get("bytes_fetched", 0) >= v2_settings.V2_L2_MAX_BYTES:
        return "max_bytes"
    if state.get("cost_usd", 0.0) >= v2_settings.V2_L2_MAX_COST_USD:
        return "max_cost"
    return "completed"


def build_graph(state_ref: dict[str, Any]):
    """
    Build and compile the StateGraph.
    `state_ref` is a mutable dict shared with the tools so they can update cap counters.
    """
    tools_list = make_tools(state_ref)
    tool_node = ToolNode(tools_list)

    llm = get_chat_model("layer2_agent", temperature=0.0).bind_tools(tools_list)

    async def crawl_agent_node(state: GraphState) -> dict:
        iterations = state.get("iterations", 0) + 1
        state_ref["iterations"] = iterations

        # Sync cap counters from state_ref back into returned state update
        cost_usd = get_run_cost(state.get("run_id", ""))

        if _over_cap({**state, "iterations": iterations, "cost_usd": cost_usd}):
            stop = _stop_reason({**state, "iterations": iterations, "cost_usd": cost_usd})
            logger.info(f"[L2] {state['ein']} — cap hit ({stop}) at iteration {iterations}")
            return {
                "iterations": iterations,
                "cost_usd": cost_usd,
                "stop_reason": stop,
                "messages": [],  # clear messages so should_continue sees no tool_calls
                "pages_fetched": state_ref.get("pages_fetched", state.get("pages_fetched", 0)),
                "pdfs_processed": state_ref.get("pdfs_processed", state.get("pdfs_processed", 0)),
                "bytes_fetched": state_ref.get("bytes_fetched", state.get("bytes_fetched", 0)),
                "visited_urls": state_ref.get("visited_urls", state.get("visited_urls", [])),
                "corpus": state_ref.get("corpus", state.get("corpus", [])),
            }

        messages = state.get("messages", [])
        if not messages:
            system_prompt = CRAWL_AGENT_SYSTEM.replace("{base_url}", state["base_url"])
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=(
                    f"Research the grant programs at: {state['base_url']}\n"
                    f"Foundation: {state['org_name']}"
                )),
            ]

        try:
            response = await llm.ainvoke(messages)
        except BudgetExceeded:
            return {
                "iterations": iterations, "cost_usd": get_run_cost(state.get("run_id", "")),
                "stop_reason": "max_cost",
            }
        except Exception as e:
            logger.error(f"[L2] crawl_agent LLM error for {state['ein']}: {e}")
            return {"iterations": iterations, "stop_reason": "error", "error": str(e)}

        tool_calls = getattr(response, "tool_calls", []) or []
        logger.info(f"[L2] {state['ein']} — iteration {iterations}: agent made {len(tool_calls)} tool call(s): {[t.get('name') for t in tool_calls]}")

        return {
            "messages": [response],
            "iterations": iterations,
            "cost_usd": get_run_cost(state.get("run_id", "")),
            "pages_fetched": state_ref.get("pages_fetched", state.get("pages_fetched", 0)),
            "pdfs_processed": state_ref.get("pdfs_processed", state.get("pdfs_processed", 0)),
            "bytes_fetched": state_ref.get("bytes_fetched", state.get("bytes_fetched", 0)),
            "visited_urls": state_ref.get("visited_urls", state.get("visited_urls", [])),
            "corpus": state_ref.get("corpus", state.get("corpus", [])),
        }

    def should_continue(state: GraphState) -> str:
        """Route after crawl_agent: call tools, stop for cap/error, or proceed to identify."""
        if state.get("stop_reason") or state.get("error"):
            return "identify_programs"
        messages = state.get("messages", [])
        last = messages[-1] if messages else None
        if last and hasattr(last, "tool_calls") and last.tool_calls:
            return "tools"
        return "identify_programs"

    def after_tools(state: GraphState) -> str:
        """After tool execution, check caps before going back to agent."""
        cost_usd = get_run_cost(state.get("run_id", ""))
        check = {**state, "cost_usd": cost_usd}
        if _over_cap(check):
            return "identify_programs"
        return "crawl_agent"

    async def identify_programs_node(state: GraphState) -> dict:
        corpus = state_ref.get("corpus", state.get("corpus", []))
        run_id = state.get("run_id", "")
        budget_remaining = v2_settings.V2_L2_MAX_COST_USD - state.get("cost_usd", 0.0)
        programs = await identify_programs(
            corpus=corpus,
            org_name=state["org_name"],
            ein=state["ein"],
            run_id=run_id,
            budget_usd=max(budget_remaining, 0.05),
        )
        cost_usd = get_run_cost(run_id)
        return {"programs": programs, "cost_usd": cost_usd}

    async def evaluate_rules_node(state: GraphState) -> dict:
        corpus = state_ref.get("corpus", state.get("corpus", []))
        run_id = state.get("run_id", "")
        budget_remaining = v2_settings.V2_L2_MAX_COST_USD - state.get("cost_usd", 0.0)
        verdicts = await evaluate_all_programs(
            programs=state.get("programs", []),
            corpus=corpus,
            org_name=state["org_name"],
            ein=state["ein"],
            run_id=run_id,
            budget_usd=max(budget_remaining, 0.05),
        )
        cost_usd = get_run_cost(run_id)
        return {"verdicts": verdicts, "cost_usd": cost_usd}

    def aggregate_verdicts_node(state: GraphState) -> dict:
        verdicts = state.get("verdicts", [])
        rollup, valid_count, total_count = aggregate(verdicts)
        stop = state.get("stop_reason") or "completed"
        return {
            "stop_reason": stop,
        }

    # Build graph
    g = StateGraph(GraphState)
    g.add_node("crawl_agent", crawl_agent_node)
    g.add_node("tools", tool_node)
    g.add_node("identify_programs", identify_programs_node)
    g.add_node("evaluate_rules", evaluate_rules_node)
    g.add_node("aggregate_verdicts", aggregate_verdicts_node)

    g.add_edge(START, "crawl_agent")
    g.add_conditional_edges("crawl_agent", should_continue, {
        "tools": "tools",
        "identify_programs": "identify_programs",
    })
    g.add_conditional_edges("tools", after_tools, {
        "crawl_agent": "crawl_agent",
        "identify_programs": "identify_programs",
    })
    g.add_edge("identify_programs", "evaluate_rules")
    g.add_edge("evaluate_rules", "aggregate_verdicts")
    g.add_edge("aggregate_verdicts", END)

    return g.compile()
