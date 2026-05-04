"""
Async DB wrappers using the `databases` library (already in requirements.txt).
Reuses the existing DATABASE_URL from the environment.
"""
from typing import Any, Optional
import databases
from agents.grant_writer_v2.config import v2_settings
from agents.grant_writer_v2.core.logger import get_logger

logger = get_logger("db")

_db: Optional[databases.Database] = None


def get_db() -> databases.Database:
    global _db
    if _db is None:
        _db = databases.Database(v2_settings.DATABASE_URL)
    return _db


async def connect():
    db = get_db()
    if not db.is_connected:
        await db.connect()


async def disconnect():
    db = get_db()
    if db.is_connected:
        await db.disconnect()


async def _ensure_connected() -> databases.Database:
    """Return a connected Database instance, connecting lazily if needed."""
    db = get_db()
    if not db.is_connected:
        await db.connect()
    return db


async def sql_one(query: str, values: dict | None = None) -> Optional[Any]:
    """Fetch a single row. Returns None if not found."""
    db = await _ensure_connected()
    return await db.fetch_one(query=query, values=values or {})


async def sql_all(query: str, values: dict | None = None) -> list[Any]:
    """Fetch all matching rows."""
    db = await _ensure_connected()
    return await db.fetch_all(query=query, values=values or {})


async def sql_exec(query: str, values: dict | None = None) -> None:
    """Execute a write statement (INSERT / UPDATE / DELETE)."""
    db = await _ensure_connected()
    await db.execute(query=query, values=values or {})


async def sql_exec_many(query: str, values: list[dict]) -> None:
    """Execute the same write statement for multiple value sets."""
    db = await _ensure_connected()
    await db.execute_many(query=query, values=values)
