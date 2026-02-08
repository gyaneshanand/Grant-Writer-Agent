"""
Chatbot configuration.
Loads from .env file and provides typed settings.
"""

from pydantic_settings import BaseSettings
from typing import Optional


class ChatbotSettings(BaseSettings):
    """Chatbot settings loaded from environment variables."""

    # --- OpenAI ---
    openai_api_key: str
    llm_model: str = "gpt-4o-mini"
    llm_temperature: float = 0.3

    # --- MySQL (optional - for grant search) ---
    database_url: Optional[str] = None

    # --- Vector Store ---
    vector_store_provider: str = "chroma"  # 'chroma' or 'pinecone'
    chroma_path: str = "agents/chatbot/data/chroma_db"
    pinecone_api_key: Optional[str] = None
    pinecone_index_name: str = "tgp-product-docs"

    # --- Application ---
    app_env: str = "development"
    max_conversation_history: int = 10
    max_search_results: int = 10
    support_email: str = "support@thegrantportal.com"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


chatbot_settings = ChatbotSettings()


# ────────────────────────────────────────────────────────────
# Pricing & Subscription Context
# ────────────────────────────────────────────────────────────
# This is injected as context for pricing questions.
# Update here when plans change.
# ────────────────────────────────────────────────────────────

PRICING_CONTEXT = """
The Grant Portal Pricing Plans:

FREE PLAN ($0/month):
- Browse grant directory (limited results)
- Basic search filters (interest, location)
- View grant summaries
- Save up to 5 grants

STARTER PLAN ($29/month or $290/year):
- Full grant directory access
- Advanced search filters
- Unlimited saved grants
- Grant deadline reminders via email
- Export grant lists (CSV)

PRO PLAN ($79/month or $790/year):
- Everything in Starter
- AI-powered grant matching & recommendations
- Priority access to new grants
- Grant writing templates
- Dedicated support

ENTERPRISE (Custom pricing):
- Everything in Pro
- Team collaboration features
- Custom grant alerts
- API access
- Dedicated account manager
- Contact sales@thegrantportal.com

All paid plans include a 14-day free trial. Cancel anytime.
"""
