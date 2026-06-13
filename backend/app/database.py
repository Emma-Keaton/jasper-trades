# Database connection and session management
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import sessionmaker
from app.models import Base
from app.config import settings
import os

# Ensure data directory exists
os.makedirs(settings.DATA_DIR, exist_ok=True)
os.makedirs(f"{settings.DATA_DIR}/sqlite", exist_ok=True)

# Create async engine
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    future=True,
)

# Async session factory
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

# Global async_session for backward compatibility
async_session = AsyncSessionLocal


async def get_db() -> AsyncSession:
    """Dependency for getting async database session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db():
    """Initialize database with migrations."""
    from app.migrations import migrate
    await migrate()


async def close_db():
    """Close database connections."""
    await engine.dispose()


# Backward compatibility alias for async_engine
async_engine = engine
