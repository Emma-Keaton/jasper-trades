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

from types import SimpleNamespace

import sys
from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

from app.models import Base  # noqa: E402

#: The device UUID every test acts as.
#:
#: The device ID is the application's credential, and `require_device_id`
#: validates it as a UUID. Tests previously sent `"dev-1"` or omitted the header
#: entirely and relied on the backend substituting `"default-device"` - which is
#: precisely the hole device-UUID auth closes. Tests now present a real UUID.
TEST_DEVICE_ID = "3f2504e0-4f89-41d3-9a0c-0305e82c3301"

#: A second, distinct device, for tests that need two identities.
TEST_DEVICE_ID_2 = "9c858901-8a57-4791-81fe-4c455b099bc9"

DEVICE_HEADERS = {"X-Device-ID": TEST_DEVICE_ID}

# Every declarative model must be registered on `Base` *before* the test schema is
# created, or tables will be missing for the duration of the run.
#
# `app/models_ext/` holds nine tables (broker connections, crypto credentials,
# cTrader accounts/execution logs/token refresh logs, four Polymarket). Its
# modules are only imported when their routers load, which in a test happens
# inside a fixture - after `_fresh_db` has already created the schema. That
# produced `no such column: broker_connections.device_id` from the lifespan.
# Production does not hit this because `app.main` is imported before `init_db`,
# so this mirrors that order.
import app.models_ext.broker_connections  # noqa: E402,F401
import app.models_ext.crypto_credentials  # noqa: E402,F401
import app.models_ext.ctrader  # noqa: E402,F401
import app.models_ext.polymarket  # noqa: E402,F401

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
async def portfolio(db, device_id: str = TEST_DEVICE_ID) -> object:
    """A Portfolio with cash, owned by `device_id`.

    Used by payout/withdrawal tests, which need a real owner because the
    scheduler and the hot-wallet key both resolve per device.
    """
    from app.models import Portfolio

    p = Portfolio(
        device_id=device_id,
        name="Default",
        cash=10000.0,
        initial_value=10000.0,
        initial_capital=10000.0,
    )
    db.add(p)
    await db.commit()
    await db.refresh(p)
    return p


@pytest.fixture(scope="session")
def event_loop_policy():
    """Session-scoped loop for the lifespan fixture below.

    The app's lifespan creates background tasks (scheduler, warm-up), so it needs
    a loop that outlives a single test.
    """
    import asyncio

    return asyncio.get_event_loop_policy()


@pytest_asyncio.fixture
async def booted_app():
    """Run the real FastAPI lifespan against the test database.

    httpx's ASGITransport does not run lifespan events, so without this the
    entire startup and shutdown sequence is untested. That is how a `NameError` in
    the lifespan body survived a 446-test run: nothing ever executed it.
    """
    import contextlib

    from app import main as main_module

    @contextlib.asynccontextmanager
    async def _host():
        # The lifespan ignores its argument; a stub keeps the signature honest.
        yield SimpleNamespace(state=SimpleNamespace())

    async with main_module.lifespan(_host()):
        yield main_module.app


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


@pytest.fixture(autouse=True)
def _no_optional_dep_install(monkeypatch):
    """Never let a test trigger a real `pip install`.

    The deferred installer is started by the lifespan, and it first waits out a
    settle period plus a memory gate. Every test that boots the real lifespan would
    therefore pay that wait, and any test where a soft dependency is genuinely absent
    would reach the network and mutate site-packages partway through a run.

    The install logic is covered directly in tests/test_optional_deps.py with the
    subprocess stubbed, so nothing is lost. This only stops it from firing as a side
    effect of booting the app.
    """
    from app.config import settings

    monkeypatch.setattr(settings, "OPTIONAL_DEPS_AUTO_INSTALL", False)


@pytest_asyncio.fixture
async def app_client(session_factory):
    """The real FastAPI app (all routers + production paths) wired to the test DB.

    Deliberately does NOT run the lifespan. Booting it here was tried and
    reverted: the app's module-level singletons (`start_publisher_tasks` queues,
    scheduler, market data) bind `asyncio` primitives to the first event loop that
    awaits them, so running the lifespan per test leaves those objects bound to a
    closed loop for the next test. That produced
    "Queue ... is bound to a different event loop" and several unrelated
    failures, for a test-isolation problem rather than a product one - in
    production there is exactly one loop for the process lifetime.

    Boot is covered where it belongs instead: `test_agent_integration.py` drives
    the real lifespan, and `test_boot_lifecycle.py` covers its parts. That is
    what caught a `NameError` in the lifespan body which 446 tests had missed.
    """
    from httpx import ASGITransport, AsyncClient

    from app.main import app

    async def _override_db():
        async with session_factory() as s:
            yield s

    app.dependency_overrides[get_db] = _override_db

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


@pytest_asyncio.fixture
async def device_settings(db, device_id: str = TEST_DEVICE_ID) -> object:
    """A DeviceSettings row for the given device (default practice/sandbox)."""
    from app.models import DeviceSettings

    ds = DeviceSettings(device_id=device_id)
    db.add(ds)
    await db.commit()
    await db.refresh(ds)
    return ds


@pytest_asyncio.fixture
async def live_device(db, device_id: str = TEST_DEVICE_ID) -> object:
    """A live-configured DeviceSettings row (trading_mode=live, environment=live)."""
    from app.models import DeviceSettings

    ds = DeviceSettings(device_id=device_id, trading_mode="live", environment_mode="live")
    db.add(ds)
    await db.commit()
    await db.refresh(ds)
    return ds
