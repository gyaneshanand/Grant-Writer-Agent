"""
Single LLM gateway for grant_writer_v2.
Routes all calls through OpenRouter using the OpenAI SDK's base_url override.
Logs every call to v2_llm_calls. Enforces per-run cost budgets.
"""
import asyncio
import hashlib
import json
import time
import uuid
from typing import Any, Optional

from openai import AsyncOpenAI
from langchain_openai import ChatOpenAI

from agents.grant_writer_v2.config import v2_settings
from agents.grant_writer_v2.core.models import MODEL_REGISTRY
from agents.grant_writer_v2.core.logger import get_logger

logger = get_logger("llm")

# OpenAI SDK pointed at OpenRouter
_client = AsyncOpenAI(
    base_url=v2_settings.OPENROUTER_BASE_URL,
    api_key=v2_settings.OPENROUTER_API_KEY,
)

# Per-run cost accumulator: run_id → cumulative cost USD
_run_costs: dict[str, float] = {}


class BudgetExceeded(Exception):
    """Raised when a per-run cost ceiling is hit."""
    pass


def start_run(run_id: str) -> None:
    _run_costs[run_id] = 0.0


def get_run_cost(run_id: str) -> float:
    return _run_costs.get(run_id, 0.0)


def clear_run(run_id: str) -> None:
    _run_costs.pop(run_id, None)


def _estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """
    Rough cost estimate. OpenRouter returns usage in the response;
    this is a fallback for models that don't report it.
    Per-million-token pricing (approximate, 2025):
    """
    pricing: dict[str, tuple[float, float]] = {
        # (input $/1M, output $/1M)
        "openai/gpt-4o": (2.50, 10.00),
        "openai/gpt-4o-mini": (0.15, 0.60),
        "anthropic/claude-sonnet-4": (3.00, 15.00),
        "anthropic/claude-haiku-4-5": (0.25, 1.25),
        "google/gemini-2.5-pro": (1.25, 10.00),
    }
    in_price, out_price = pricing.get(model, (1.0, 5.0))
    return (input_tokens / 1_000_000 * in_price) + (output_tokens / 1_000_000 * out_price)


async def _log_call(
    ein: str,
    layer: str,
    use_case: str,
    model: str,
    prompt_hash: str,
    input_tokens: int,
    output_tokens: int,
    cost_usd: float,
    latency_ms: int,
    status: str,
    error_message: Optional[str] = None,
) -> None:
    """Write a row to v2_llm_calls (best-effort, never raises)."""
    try:
        from agents.grant_writer_v2.core.db import sql_exec
        await sql_exec(
            """
            INSERT INTO v2_llm_calls
              (ein, layer, provider, model, prompt_hash,
               input_tokens, output_tokens, cost_usd, latency_ms, status, error_message)
            VALUES
              (:ein, :layer, 'openrouter', :model, :prompt_hash,
               :input_tokens, :output_tokens, :cost_usd, :latency_ms, :status, :error_message)
            """,
            {
                "ein": ein,
                "layer": layer,
                "model": model,
                "prompt_hash": prompt_hash,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "cost_usd": cost_usd,
                "latency_ms": latency_ms,
                "status": status,
                "error_message": error_message,
            },
        )
    except Exception as e:
        logger.warning(f"Failed to log LLM call: {e}")


async def chat(
    use_case: str,
    messages: list[dict],
    *,
    ein: str = "",
    layer: str = "",
    run_id: Optional[str] = None,
    budget_usd: Optional[float] = None,
    max_tokens: int = 4000,
    temperature: float = 0.1,
    response_format: Optional[dict] = None,
    **kwargs: Any,
) -> Any:
    """
    Async one-shot LLM completion via OpenRouter.
    Logs to v2_llm_calls and enforces optional per-run budget cap.
    Returns the raw OpenAI-SDK ChatCompletion object.
    """
    model = MODEL_REGISTRY[use_case]
    prompt_hash = hashlib.sha256(json.dumps(messages, sort_keys=True).encode()).hexdigest()[:16]

    start = time.monotonic()
    status = "ok"
    error_msg = None
    input_tokens = output_tokens = 0

    try:
        call_kwargs: dict[str, Any] = dict(
            model=model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
            **kwargs,
        )
        if response_format:
            call_kwargs["response_format"] = response_format

        resp = await _client.chat.completions.create(**call_kwargs)

        if resp.usage:
            input_tokens = resp.usage.prompt_tokens or 0
            output_tokens = resp.usage.completion_tokens or 0

        cost = _estimate_cost(model, input_tokens, output_tokens)
        latency_ms = int((time.monotonic() - start) * 1000)

        # Update per-run budget
        if run_id:
            _run_costs[run_id] = _run_costs.get(run_id, 0.0) + cost
            cap = budget_usd or v2_settings.V2_L2_MAX_COST_USD
            if _run_costs[run_id] > cap:
                raise BudgetExceeded(
                    f"Run {run_id} exceeded cost cap ${cap:.4f} "
                    f"(current: ${_run_costs[run_id]:.4f})"
                )

        asyncio.ensure_future(
            _log_call(ein, layer, use_case, model, prompt_hash,
                      input_tokens, output_tokens, cost, latency_ms, status)
        )
        return resp

    except BudgetExceeded:
        raise
    except Exception as e:
        status = "error"
        error_msg = str(e)
        latency_ms = int((time.monotonic() - start) * 1000)
        asyncio.ensure_future(
            _log_call(ein, layer, use_case, model, prompt_hash,
                      input_tokens, output_tokens, 0.0, latency_ms, status, error_msg)
        )
        raise


def get_chat_model(use_case: str, **kwargs: Any) -> ChatOpenAI:
    """
    LangChain-compatible ChatOpenAI model for the L2 LangGraph agent.
    Points to OpenRouter via openai_api_base override.
    """
    return ChatOpenAI(
        model=MODEL_REGISTRY[use_case],
        openai_api_base=v2_settings.OPENROUTER_BASE_URL,
        openai_api_key=v2_settings.OPENROUTER_API_KEY,
        **kwargs,
    )
