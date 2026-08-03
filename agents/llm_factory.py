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
DEFAULT_REASONING_EFFORT = "low"
DEFAULT_REQUEST_TIMEOUT = 90  # seconds per LLM call
DEFAULT_MAX_RETRIES = 1


def create_pipeline_llm(temperature: float, openai_api_key: str = None) -> ChatOpenAI:
    """Build the pipeline LLM with GPT-5.x-safe parameters.

    GPT-5.x chat completions reject any temperature other than the default (1),
    so the caller's temperature is only honored for older models.
    """
    model = os.getenv("PIPELINE_MODEL", DEFAULT_PIPELINE_MODEL)
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
        kwargs["reasoning_effort"] = os.getenv(
            "PIPELINE_REASONING_EFFORT", DEFAULT_REASONING_EFFORT
        )

    return ChatOpenAI(**kwargs)
