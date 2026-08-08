"""Migrate data from local SQLite to Supabase/Postgres.

Run AFTER installing asyncpg:
    pip install asyncpg

Usage (PowerShell):
    $env:SOURCE_DB_URL="sqlite+aiosqlite:///./data/sqlite/jasper_trades.db"
    $env:DEST_DB_URL="postgresql://postgres.xxxx:password@aws-0-region.pooler.supabase.com:6543/postgres"
    python scripts/migrate_sqlite_to_postgres.py

Idempotent-ish: it creates the schema on the destination (create_all) and
copies all rows from every model table. Re-running will duplicate rows, so
run once on a fresh Supabase project.
"""

import asyncio
import os
import sys

# Ensure backend app is importable when run from backend/
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy import select, insert
from app.models import Base


def _to_async_pg(url: str) -> str:
    if url.startswith("postgres://"):
        return "postgresql+asyncpg://" + url[len("postgres://"):]
    if url.startswith("postgresql://") and "+asyncpg" not in url:
        return "postgresql+asyncpg://" + url[len("postgresql://"):]
    return url


async def main():
    src_url = os.environ.get("SOURCE_DB_URL")
    dst_url = os.environ.get("DEST_DB_URL")
    if not src_url or not dst_url:
        print("Set SOURCE_DB_URL (sqlite) and DEST_DB_URL (supabase postgres).")
        return

    src = create_async_engine(src_url)
    dst = create_async_engine(_to_async_pg(dst_url))

    # 1. Create schema on destination (all model tables)
    async with dst.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("[OK] Schema created on destination")

    tables = Base.metadata.sorted_tables
    async with AsyncSession(src) as s, AsyncSession(dst) as d:
        total = 0
        for t in tables:
            rows = (await s.execute(select(t))).fetchall()
            if not rows:
                continue
            data = [dict(r._mapping) for r in rows]
            await d.execute(insert(t), data)
            total += len(data)
            print(f"  copied {len(data)} rows -> {t.name}")
        await d.commit()
    await src.dispose()
    await dst.dispose()
    print(f"[DONE] Migrated {total} rows to Supabase/Postgres.")


if __name__ == "__main__":
    asyncio.run(main())
