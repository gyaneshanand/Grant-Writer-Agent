"""
Async MySQL connection pool.

Uses the `databases` library for async query execution.
Optional - only needed if grant search functionality is enabled.
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Database instance (lazily initialized)
_database: Optional["Database"] = None


async def get_database():
    """Get the database instance, initializing if needed."""
    global _database
    if _database is None:
        from agents.chatbot.config import chatbot_settings
        if chatbot_settings.database_url:
            from databases import Database
            _database = Database(chatbot_settings.database_url)
        else:
            logger.warning("DATABASE_URL not configured - grant search disabled")
            return None
    return _database


async def startup_db():
    """Connect to MySQL. Called on FastAPI startup."""
    db = await get_database()
    if db:
        await db.connect()
        logger.info("MySQL connected for chatbot")


async def shutdown_db():
    """Disconnect from MySQL. Called on FastAPI shutdown."""
    global _database
    if _database:
        await _database.disconnect()
        _database = None
        logger.info("MySQL disconnected")


# For direct access in nodes (after startup)
database = None


async def ensure_database():
    """Ensure database is available, raising if not configured."""
    global database
    if database is None:
        database = await get_database()
    return database
