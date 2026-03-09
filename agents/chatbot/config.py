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
    llm_model: str = "gpt-4"
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
    support_email: str = "tech@promero.com"

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
The Grant Portal Pricing Plans

FREE PLAN : Grant Alert Newsletter ($0)

Receive daily grant alerts based on your profile (interests & locations)
View basic summary overviews of grants
Search grants by interest, location, eligibility
No credit card required to sign up

WEEKLY PLAN : $14.99/week

Full access to grant details, eligibilities & requirements
Search all grants with advanced keyword search
Save grants as favorites
Set calendar reminders
Full access to IRS 990-PF private foundations directory
Access archived grants & grant history
Auto-renew subscription, cancel anytime

MONTHLY PLAN : $34.99/month

Everything in Weekly plan
Continue access on a monthly auto-renewing cycle
Cancel at any time before renewal

QUARTERLY PLAN : $79.99/quarter

Everything in Monthly plan
Billed every 3 months
Cancel at any time before renewal

YEARLY PLAN : $199.99/year

Everything in Quarterly plan
Best value for long-term subscribers
Cancel any time before renewal

Optional Add-On: Grant Writer Directory

(Requires a paid subscription to The Grant Portal)
Monthly: $19.99
Quarterly: $39.99
Yearly: $69.99

Provides access to contact and work with professional grant writers via the Grant Writer Directory

Additional Notes

Free plan does not provide full grant details or application links — only summaries and alerts. Paid subscriptions are required for full access.
Subscriptions are auto-renewing and can be cancelled at any time before the next billing cycle.

All pricing is in USD.
"""
