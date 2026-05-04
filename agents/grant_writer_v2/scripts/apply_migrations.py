"""
One-shot migration runner.
Usage: python -m agents.grant_writer_v2.scripts.apply_migrations
"""
import asyncio
import glob
import os
from pathlib import Path

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent.parent.parent / ".env")

import databases

MIGRATIONS_DIR = Path(__file__).parent.parent / "db" / "migrations"


async def run():
    db_url = os.getenv("DATABASE_URL", "")
    if not db_url:
        raise RuntimeError("DATABASE_URL env var not set")

    # databases library requires the async driver variant
    db = databases.Database(db_url)
    await db.connect()

    sql_files = sorted(glob.glob(str(MIGRATIONS_DIR / "*.sql")))
    print(f"Applying {len(sql_files)} migration(s) from {MIGRATIONS_DIR}")

    for path in sql_files:
        print(f"  → {Path(path).name}")
        sql = Path(path).read_text()
        # Split on semicolons and execute each statement
        statements = [s.strip() for s in sql.split(";") if s.strip()]
        for stmt in statements:
            try:
                await db.execute(query=stmt)
            except Exception as e:
                # Ignore "already exists" errors on CREATE TABLE IF NOT EXISTS
                if "already exists" not in str(e).lower():
                    print(f"    WARNING: {e}")

    await db.disconnect()
    print("Done.")


if __name__ == "__main__":
    asyncio.run(run())
