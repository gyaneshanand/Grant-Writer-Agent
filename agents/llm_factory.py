"""Shared ChatOpenAI factory for the v1 pipeline agents.

Model comes from PIPELINE_MODEL (default gpt-5.5) so all four
/api/v1/pipeline/complete agents stay on one model without editing code.
"""

import os

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

load_dotenv()

DEFAULT_PIPELINE_MODEL = "gpt-5.5"


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

    return ChatOpenAI(
        temperature=1 if "gpt-5" in model else temperature,
        model=model,
        api_key=openai_api_key,
    )
