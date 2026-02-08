"""
Logging utility for the chatbot.
Provides a standard logger and a decorator for tracing node execution.
"""
import logging
import time
import json
import functools
from typing import Any, Callable
from agents.chatbot.models.state import ChatbotState

# Configure logger
logger = logging.getLogger("chatbot")
logger.setLevel(logging.INFO)

# Create console handler if not exists
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)


def log_node_execution(func: Callable) -> Callable:
    """
    Decorator to log the execution of a LangGraph node.
    Logs entry with state summary and exit with execution time.
    """
    @functools.wraps(func)
    async def wrapper(state: ChatbotState, *args, **kwargs) -> dict:
        node_name = func.__name__
        start_time = time.time()
        
        # Log Entry
        query_type = state.get("query_type", "unknown")
        session_id = state.get("session_id", "unknown")
        logger.info(f"▶️  ENTERING NODE: {node_name} | Session: {session_id} | QueryType: {query_type}")
        
        if node_name == "classify_query":
            user_msg = state.get("user_message", "")
            logger.info(f"📝 User Message: '{user_msg}'")

        try:
            # Execute Node
            result = await func(state, *args, **kwargs)
            
            # Calculate duration
            duration = (time.time() - start_time) * 1000
            
            # Log Exit
            logger.info(f"✅ EXITING NODE: {node_name} | Sub-steps took: {duration:.2f}ms")
            
            # Node-specific logging (if result changes state significantly)
            if node_name == "classify_query":
                logger.info(f"🧠 Classification Result: {result.get('query_type')}")
            elif node_name == "extract_and_resolve_entities":
                entities = result.get('extracted_entities')
                logger.info(f"🧩 Extracted Entities: {json.dumps(entities, default=str)}")
            elif node_name == "build_and_execute_search":
                count = len(result.get('search_results') or [])
                logger.info(f"🔍 Search Execution: Found {count} grants")
            
            return result
            
        except Exception as e:
            logger.error(f"❌ ERROR IN NODE {node_name}: {str(e)}", exc_info=True)
            raise e
            
    return wrapper
