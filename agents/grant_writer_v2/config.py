import os
from pydantic_settings import BaseSettings


class V2Settings(BaseSettings):
    # OpenRouter (primary LLM gateway)
    OPENROUTER_API_KEY: str = os.getenv("OPENROUTER_API_KEY", "")
    OPENROUTER_BASE_URL: str = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")

    # SerpAPI
    SERPAPI_API_KEY: str = os.getenv("SERPAPI_API_KEY", "")

    # Database (reuse existing DATABASE_URL)
    DATABASE_URL: str = os.getenv("DATABASE_URL", "")

    # L2 cost & safety caps
    V2_L2_MAX_ITERATIONS: int = int(os.getenv("V2_L2_MAX_ITERATIONS", "12"))
    V2_L2_MAX_PAGES: int = int(os.getenv("V2_L2_MAX_PAGES", "25"))
    V2_L2_MAX_PDFS: int = int(os.getenv("V2_L2_MAX_PDFS", "5"))
    V2_L2_MAX_BYTES: int = int(os.getenv("V2_L2_MAX_BYTES", str(8 * 1024 * 1024)))  # 8 MB
    V2_L2_MAX_COST_USD: float = float(os.getenv("V2_L2_MAX_COST_USD", "0.50"))

    # Per-use-case model overrides (see core/models.py for full registry)
    V2_MODEL_LAYER1_RERANKER: str = os.getenv("V2_MODEL_LAYER1_RERANKER", "openai/gpt-4o-mini")
    V2_MODEL_LAYER2_AGENT: str = os.getenv("V2_MODEL_LAYER2_AGENT", "anthropic/claude-sonnet-4")
    V2_MODEL_LAYER2_PROGRAM_IDENTIFIER: str = os.getenv("V2_MODEL_LAYER2_PROGRAM_IDENTIFIER", "openai/gpt-4o")
    V2_MODEL_LAYER2_RULE_EVALUATOR: str = os.getenv("V2_MODEL_LAYER2_RULE_EVALUATOR", "openai/gpt-4.1-mini")
    V2_MODEL_LAYER3_EXTRACTOR: str = os.getenv("V2_MODEL_LAYER3_EXTRACTOR", "openai/gpt-4o-mini")
    V2_MODEL_LAYER4_PER_PROGRAM: str = os.getenv("V2_MODEL_LAYER4_PER_PROGRAM", "openai/gpt-4o")
    V2_MODEL_LAYER4_CONSOLIDATOR: str = os.getenv("V2_MODEL_LAYER4_CONSOLIDATOR", "openai/gpt-4o-mini")
    V2_MODEL_LAYER5_SEO: str = os.getenv("V2_MODEL_LAYER5_SEO", "openai/gpt-4o-mini")

    # HTTP client
    HTTP_TIMEOUT_SECONDS: int = int(os.getenv("V2_HTTP_TIMEOUT", "30"))
    HTTP_MAX_RETRIES: int = int(os.getenv("V2_HTTP_MAX_RETRIES", "3"))

    # On-disk cache directory (relative to this file's package root)
    CACHE_DIR: str = os.getenv("V2_CACHE_DIR", "agents/grant_writer_v2/.cache")

    class Config:
        env_file = ".env"
        extra = "allow"


v2_settings = V2Settings()
