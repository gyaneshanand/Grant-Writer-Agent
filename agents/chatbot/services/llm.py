"""
LLM client for chatbot.
Uses OpenAI via LangChain with lazy initialization.
"""

from functools import lru_cache
from langchain_openai import ChatOpenAI
from agents.chatbot.config import chatbot_settings


@lru_cache(maxsize=1)
def get_llm() -> ChatOpenAI:
    """Get the LLM client (lazy initialized, cached)."""
    return ChatOpenAI(
        model=chatbot_settings.llm_model,
        temperature=chatbot_settings.llm_temperature,
    )


# For backwards compatibility - property that lazily creates the LLM
class _LazyLLM:
    """Lazy LLM wrapper that only initializes when accessed."""
    
    _instance = None
    
    def __getattr__(self, name):
        if _LazyLLM._instance is None:
            _LazyLLM._instance = get_llm()
        return getattr(_LazyLLM._instance, name)
    
    async def ainvoke(self, *args, **kwargs):
        if _LazyLLM._instance is None:
            _LazyLLM._instance = get_llm()
        return await _LazyLLM._instance.ainvoke(*args, **kwargs)
    
    def invoke(self, *args, **kwargs):
        if _LazyLLM._instance is None:
            _LazyLLM._instance = get_llm()
        return _LazyLLM._instance.invoke(*args, **kwargs)


llm = _LazyLLM()
