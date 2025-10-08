"""
LangSmith Setup and Configuration
Provides tracing and monitoring for LangChain operations
"""
import os
from typing import Optional
from .settings import settings

def setup_langsmith() -> bool:
    """
    Setup LangSmith tracing if enabled and configured
    
    Returns:
        bool: True if LangSmith is enabled and configured, False otherwise
    """
    if not settings.LANGSMITH_TRACING:
        print("🔍 LangSmith tracing is disabled")
        return False
    
    if not settings.LANGSMITH_API_KEY:
        print("⚠️  LangSmith API key not found, tracing disabled")
        return False
    
    # Set LangSmith environment variables
    os.environ["LANGCHAIN_TRACING_V2"] = "true"
    os.environ["LANGCHAIN_ENDPOINT"] = settings.LANGSMITH_ENDPOINT
    os.environ["LANGCHAIN_API_KEY"] = settings.LANGSMITH_API_KEY
    os.environ["LANGCHAIN_PROJECT"] = settings.LANGSMITH_PROJECT
    
    print("🚀 LangSmith tracing enabled")
    print(f"📊 Project: {settings.LANGSMITH_PROJECT}")
    print(f"🔗 Endpoint: {settings.LANGSMITH_ENDPOINT}")
    
    return True

def get_langsmith_config() -> dict:
    """
    Get current LangSmith configuration
    
    Returns:
        dict: LangSmith configuration details
    """
    return {
        "tracing_enabled": settings.LANGSMITH_TRACING,
        "endpoint": settings.LANGSMITH_ENDPOINT,
        "project": settings.LANGSMITH_PROJECT,
        "api_key_configured": bool(settings.LANGSMITH_API_KEY),
        "environment_vars_set": {
            "LANGCHAIN_TRACING_V2": os.getenv("LANGCHAIN_TRACING_V2"),
            "LANGCHAIN_PROJECT": os.getenv("LANGCHAIN_PROJECT"),
            "LANGCHAIN_ENDPOINT": os.getenv("LANGCHAIN_ENDPOINT"),
            "LANGCHAIN_API_KEY": "***" if os.getenv("LANGCHAIN_API_KEY") else None
        }
    }

def create_run_name(operation: str, model: str = "", extra: str = "") -> str:
    """
    Create a standardized run name for LangSmith tracing
    
    Args:
        operation: The operation being performed (e.g., "grant_collection", "metadata_generation")
        model: The model being used (e.g., "gpt-4o-mini")
        extra: Extra context (e.g., foundation name, grant count)
    
    Returns:
        str: Formatted run name for tracing
    """
    parts = ["grant_writer_agent", operation]
    
    if model:
        parts.append(f"model_{model}")
    
    if extra:
        parts.append(extra)
    
    return "_".join(parts).replace("-", "_").lower()

def log_langsmith_status():
    """Log current LangSmith configuration status"""
    config = get_langsmith_config()
    
    print("\n" + "="*50)
    print("🔍 LANGSMITH CONFIGURATION STATUS")
    print("="*50)
    print(f"Tracing Enabled: {config['tracing_enabled']}")
    print(f"Project: {config['project']}")
    print(f"Endpoint: {config['endpoint']}")
    print(f"API Key Configured: {config['api_key_configured']}")
    
    if config['tracing_enabled'] and config['api_key_configured']:
        print("✅ LangSmith is properly configured and active")
    elif config['tracing_enabled']:
        print("⚠️  LangSmith tracing is enabled but API key is missing")
    else:
        print("📝 LangSmith tracing is disabled")
    
    print("="*50 + "\n")