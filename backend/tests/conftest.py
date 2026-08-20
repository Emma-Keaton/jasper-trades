"""
Shared test fixtures for the jasper-trades backend test suite.

Every test runs against an in-memory SQLite database (StaticPool) with a fresh
schema per test. Network / global state is neutralized:

- `app.database.async_session` and the module-level copies used by
  `paper_trading_service` / `settings_extensions` are pointed at the test DB.
- The universal paper ledger and circuit breaker singleton are reset per test.
- Routes that resolve `db` via FastAPI dependency injection get the test DB
  through `app.database.get_db` overrides (see `app_client` fixture).
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

from app.models import Base  # noqa: E402

import app.models_ext.crypto_credentials  # noqa: E402,F401  (registers tables on Base)

from app.database import get_db  # noqa: E402

TEST_ENGINE = create_async_engine(
    "sqlite+aiosqlite://",
    poolclass=StaticPool,
    connect_args={"check_same_thread": False},
)
TEST_FACTORY = async_sessionmaker(TEST_ENGINE, class_=AsyncSession, expire_on_commit=False)


@pytest_asyncio.fixture(autouse=True)
async def _fresh_db():
    """Fresh in-memory schema before every test (macro-isolation)."""
    async with TEST_ENGINE.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield


@pytest_asyncio.fixture
async def db_engine(_fresh_db):
    yield TEST_ENGINE


@pytest_asyncio.fixture
async def db(db_engine):
    """A ready AsyncSession bound to the test database."""
    async with TEST_FACTORY() as session:
        yield session


@pytest_asyncio.fixture
async def session_factory(db_engine):
    yield TEST_FACTORY


@pytest.fixture(autouse=True)
def _isolate_globals(monkeypatch):
    """Reset in-process singletons and redirect async_session to the test DB."""
    from app.services.paper_trading_service import get_paper_trading_service
    from app.services.circuit_breaker import get_circuit_breaker

    get_paper_trading_service().clear_cache()
    get_circuit_breaker().reset()

    monkeypatch.setattr("app.database.async_session", TEST_FACTORY)
    monkeypatch.setattr("app.services.paper_trading_service.async_session", TEST_FACTORY)
    monkeypatch.setattr("app.api.v1.settings_extensions.async_session", TEST_FACTORY)


@pytest_asyncio.fixture
async def app_client(session_factory):
    """The real FastAPI app (all routers + production paths) wired to the test DB."""
    from httpx import ASGITransport, AsyncClient

    from app.main import app

    async def _override_db():
        async with session_factory() as s:
            yield s

    app.dependency_overrides[get_db] = _override_db

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


@pytest_asyncio.fixture
async def device_settings(db, device_id: str = "dev-1") -> object:
    """A DeviceSettings row for the given device (default practice/sandbox)."""
    from app.models import DeviceSettings

    ds = DeviceSettings(device_id=device_id)
    db.add(ds)
    await db.commit()
    await db.refresh(ds)
    return ds


@pytest_asyncio.fixture
async def live_device(db, device_id: str = "dev-1") -> object:
    """A live-configured DeviceSettings row (trading_mode=live, environment=live)."""
    from app.models import DeviceSettings

    ds = DeviceSettings(device_id=device_id, trading_mode="live", environment_mode="live")
    db.add(ds)
    await db.commit()
    await db.refresh(ds)
    return ds
