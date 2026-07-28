import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import MetaData
from app.models import Base
from app.schedulers.ctrader_token_refresh import token_refresh_lifespan

async def main():
    # In‑memory SQLite database for testing
    engine = create_async_engine('sqlite+aiosqlite:///./test.db', echo=False)
    # Create all tables required for the scheduler
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    # Run the scheduler lifespan (it will perform an immediate refresh check)
    async with token_refresh_lifespan(engine) as scheduler:
        await asyncio.sleep(1)

asyncio.run(main())
