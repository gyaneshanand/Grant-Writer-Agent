"""Shared ChatOpenAI factory for the v1 pipeline agents.

Model comes from PIPELINE_MODEL (default gpt-5.5) so all four
/api/v1/pipeline/complete agents stay on one model without editing code.

Latency posture: this pipeline's job is scrape -> extract -> store. The client
does not review each field, so speed beats polish here. GPT-5.x reasoning is
therefore forced to PIPELINE_REASONING_EFFORT (default "low"), retries are
capped at 1, and every request carries a hard timeout so a stuck call cannot
stall the whole pipeline.
"""

import os

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

load_dotenv()

DEFAULT_PIPELINE_MODEL = "gpt-5.5"
DEFAULT_EXTRACT_MODEL = "gpt-5.4-mini"
DEFAULT_REASONING_EFFORT = "low"
DEFAULT_REQUEST_TIMEOUT = 90  # seconds per LLM call
DEFAULT_MAX_RETRIES = 1

# $/1M tokens (input, output), from OpenAI's published pricing (2026-08).
# Only used for the per-call cost log lines — never for billing decisions.
MODEL_PRICES = {
    "gpt-5.5": (5.00, 30.00),
    "gpt-5.4-mini": (0.75, 4.50),  # keep before gpt-5.4: prefix-matched
    "gpt-5.4": (2.50, 15.00),
}


def log_llm_usage(tag: str, response) -> None:
    """Print one grep-able cost line (📊) for an LLM response.

    Extraction runs ~15x per pipeline call, so these lines are what turns
    "the pipeline costs about a dollar" into a measured per-stage number.
    """
    try:
        usage = getattr(response, "usage_metadata", None) or {}
        tokens_in = usage.get("input_tokens", 0)
        tokens_out = usage.get("output_tokens", 0)
        model = (getattr(response, "response_metadata", None) or {}).get("model_name", "?")
        cost = ""
        for prefix, (p_in, p_out) in MODEL_PRICES.items():
            if model.startswith(prefix):
                cost = f" ≈ ${ (tokens_in * p_in + tokens_out * p_out) / 1_000_000:.4f}"
                break
        print(f"📊 LLM usage [{tag}] {model}: {tokens_in} in / {tokens_out} out{cost}")
    except Exception:
        pass  # a broken cost log must never break the pipeline


def create_pipeline_llm(
    temperature: float,
    openai_api_key: str = None,
    reasoning_effort: str = None,
    model: str = None,
) -> ChatOpenAI:
    """Build the pipeline LLM with GPT-5.x-safe parameters.

    GPT-5.x chat completions reject any temperature other than the default (1),
    so the caller's temperature is only honored for older models.

    reasoning_effort lets a caller override the pipeline default. Extraction runs
    at the cheap PIPELINE_REASONING_EFFORT ("low") for latency; the two synthesis
    calls (consolidated description + teaser/metadata) pass a higher effort since
    they are low-volume and quality-critical.

    model lets a caller pick a different tier: the per-page extraction calls pass
    PIPELINE_EXTRACT_MODEL (default gpt-5.4-mini, ~6.7x cheaper than gpt-5.5),
    while the two writer calls stay on PIPELINE_MODEL where quality lives.
    """
    model = model or os.getenv("PIPELINE_MODEL", DEFAULT_PIPELINE_MODEL)
    if openai_api_key is None:
        openai_api_key = os.getenv("OPENAI_API_KEY")
    if not openai_api_key:
        raise ValueError("OPENAI_API_KEY not found in environment variables. Please set it in .env file.")

    kwargs = {
        "temperature": 1 if "gpt-5" in model else temperature,
        "model": model,
        "api_key": openai_api_key,
        "timeout": int(os.getenv("PIPELINE_LLM_TIMEOUT", DEFAULT_REQUEST_TIMEOUT)),
        "max_retries": int(os.getenv("PIPELINE_LLM_MAX_RETRIES", DEFAULT_MAX_RETRIES)),
    }

    if "gpt-5" in model:
        kwargs["reasoning_effort"] = reasoning_effort or os.getenv(
            "PIPELINE_REASONING_EFFORT", DEFAULT_REASONING_EFFORT
        )

    return ChatOpenAI(**kwargs)
