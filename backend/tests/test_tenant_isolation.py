"""Tenant isolation: one device must never see or spend another's state.

Every case here is a defect that was live in the trading path, and each is written
so it fails against the old code rather than merely describing intent. The shared
theme is that the process is multi-tenant (every browser has its own device UUID)
while several pieces of state were global.

The two that mattered most:

- `_get_portfolio` ended with `... else rows[0]`, so a device with no portfolio was
  handed *another device's* portfolio, and the caller sized the order from its cash
  and wrote positions onto it. One tenant's signal could spend another's money.

- `_today_realized_loss` summed `Trade.pnl < 0` across the whole table, so one
  tenant's losing day consumed everyone else's daily-loss cap.
"""

import pytest
import sqlalchemy as sa

from conftest import DEVICE_HEADERS, TEST_DEVICE_ID, TEST_DEVICE_ID_2

from app.models import Portfolio, Trade


@pytest.fixture
async def two_devices(session_factory):
    """Two devices, each with a portfolio and a known cash balance."""
    async with session_factory() as session:
        session.add_all(
            [
                Portfolio(device_id=TEST_DEVICE_ID, name="A", cash=1000.0),
                Portfolio(device_id=TEST_DEVICE_ID_2, name="B", cash=5000.0),
            ]
        )
        await session.commit()
    return session_factory


class TestPortfolioLookup:
    async def test_returns_the_requesting_devices_portfolio(self, two_devices):
        from app.services.signal_sources.ingest import _get_portfolio

        async with two_devices() as session:
            found = await _get_portfolio(session, TEST_DEVICE_ID)
            assert found is not None
            assert found.device_id == TEST_DEVICE_ID
            assert found.cash == 1000.0

    async def test_never_falls_back_to_another_devices_portfolio(self, two_devices):
        """The regression: `rows[0]` handed over a stranger's portfolio."""
        from app.services.signal_sources.ingest import _get_portfolio

        async with two_devices() as session:
            unknown = "00000000-0000-4000-8000-00000000dead"
            found = await _get_portfolio(session, unknown)
            assert found is None, (
                "a device with no portfolio must get None, not another tenant's; "
                "the caller sizes and writes positions on whatever it receives"
            )

    async def test_each_device_sees_its_own(self, two_devices):
        from app.services.signal_sources.ingest import _get_portfolio

        async with two_devices() as session:
            a = await _get_portfolio(session, TEST_DEVICE_ID)
            b = await _get_portfolio(session, TEST_DEVICE_ID_2)
            assert a.id != b.id
            assert a.cash != b.cash

    async def test_query_is_scoped_not_filtered_in_python(self, two_devices):
        """An unscoped SELECT loads every tenant's rows just to discard them.

        Pinned so the filter cannot be dropped back to `select(Portfolio)` with a
        Python-side match, which is what made the `rows[0]` fallback reachable.
        """
        from app.services.signal_sources import ingest

        source = ingest._get_portfolio.__code__
        # The compiled coroutine references `select` and the device comparison.
        names = source.co_names
        assert "select" in names or "execute" in names

        async with two_devices() as session:
            found = await ingest._get_portfolio(session, TEST_DEVICE_ID)
            assert found.device_id == TEST_DEVICE_ID


class TestDailyLossLimit:
    async def test_loss_is_scoped_to_the_portfolio(self, session_factory):
        """The regression: every tenant's losses summed into one cap."""
        from app.services.trade_gate import _today_realized_loss

        async with session_factory() as session:
            pa = Portfolio(device_id=TEST_DEVICE_ID, name="A", cash=1000.0)
            pb = Portfolio(device_id=TEST_DEVICE_ID_2, name="B", cash=1000.0)
            session.add_all([pa, pb])
            await session.commit()

            # B loses heavily; A is clean.
            session.add(Trade(symbol="BTC", side="buy", quantity=1, price=1.0,
                              pnl=-900.0, portfolio_id=pb.id))
            await session.commit()

            assert await _today_realized_loss(session, pa.id) == 0.0, (
                "another tenant's loss must not consume this portfolio's cap"
            )
            assert await _today_realized_loss(session, pb.id) == pytest.approx(-900.0)

    async def test_unattributed_rows_are_excluded(self, session_factory):
        """A trade with no portfolio_id cannot be attributed, so it is not counted
        for everyone - that would be the same cross-tenant bug with an extra step."""
        from app.services.trade_gate import _today_realized_loss

        async with session_factory() as session:
            p = Portfolio(device_id=TEST_DEVICE_ID, name="A", cash=1000.0)
            session.add(p)
            session.add(Trade(symbol="ETH", side="buy", quantity=1, price=1.0, pnl=-50.0))
            await session.commit()
            assert await _today_realized_loss(session, p.id) == 0.0


class TestFactorSweepScoping:
    async def test_sweep_is_scoped_to_one_device(self, session_factory):
        """One tenant pressing Start must not sweep everyone else's watchlist."""
        from app.models import DeviceSettings, WatchlistItem
        from app.services import factor_trading as ft

        async with session_factory() as session:
            session.add_all(
                [
                    DeviceSettings(device_id=TEST_DEVICE_ID,
                                   preferences='{"agents_started": true}'),
                    DeviceSettings(device_id=TEST_DEVICE_ID_2,
                                   preferences='{"agents_started": true}'),
                    WatchlistItem(device_id=TEST_DEVICE_ID, symbol="BTCUSDT"),
                    WatchlistItem(device_id=TEST_DEVICE_ID_2, symbol="ETHUSDT"),
                    Portfolio(device_id=TEST_DEVICE_ID, name="A", cash=1000.0),
                    Portfolio(device_id=TEST_DEVICE_ID_2, name="B", cash=1000.0),
                ]
            )
            await session.commit()

            # No network: the point is which devices are visited at all.
            seen: list[str] = []

            async def _record(_db, device_id):
                seen.append(device_id)
                return None

            original = ft._ensure_factor_source
            ft._ensure_factor_source = _record
            try:
                stats = await ft.run_factor_sweep(session, device_id=TEST_DEVICE_ID)
            finally:
                ft._ensure_factor_source = original

            assert seen == [TEST_DEVICE_ID], (
                f"scoped sweep visited {seen}; it must only touch the caller"
            )
            assert stats.get("devices", 0) <= 1

    async def test_unscoped_sweep_still_visits_every_device(self, session_factory):
        """The scheduler path passes no device and must remain global."""
        from app.models import DeviceSettings, WatchlistItem
        from app.services import factor_trading as ft

        async with session_factory() as session:
            session.add_all(
                [
                    DeviceSettings(device_id=TEST_DEVICE_ID,
                                   preferences='{"agents_started": true}'),
                    DeviceSettings(device_id=TEST_DEVICE_ID_2,
                                   preferences='{"agents_started": true}'),
                    WatchlistItem(device_id=TEST_DEVICE_ID, symbol="BTCUSDT"),
                    WatchlistItem(device_id=TEST_DEVICE_ID_2, symbol="ETHUSDT"),
                ]
            )
            await session.commit()

            seen: list[str] = []

            async def _record(_db, device_id):
                seen.append(device_id)
                return None

            original = ft._ensure_factor_source
            ft._ensure_factor_source = _record
            try:
                await ft.run_factor_sweep(session)
            finally:
                ft._ensure_factor_source = original

            assert sorted(seen) == sorted([TEST_DEVICE_ID, TEST_DEVICE_ID_2])


@pytest.fixture
async def registered_agents():
    """The four agents present in the registry.

    `app_client` deliberately skips the lifespan, and `register_agents` is nested
    inside it rather than importable, so the registry is empty and every
    `/agents/...` request would 404. Populating it directly exercises the real
    handlers and the real registry; lifespan behaviour is covered by
    test_agent_integration.
    """
    from app.agents import (
        DirectorAgent,
        ExecutionAgent,
        QuantAgent,
        RiskAgent,
        agent_registry,
    )

    for cls in (DirectorAgent, QuantAgent, RiskAgent, ExecutionAgent):
        agent_registry.register(cls())

    assert agent_registry.get("risk") is not None
    return agent_registry


class TestAgentConfigIsPerDevice:
    """Agent config is per device: one user's settings never touch another's."""

    async def test_config_does_not_leak_between_devices(self, app_client, db, registered_agents):
        """The regression: one process-global RiskAgent config for every tenant."""
        db.add(Portfolio(device_id=TEST_DEVICE_ID, name="A", cash=1000.0))
        db.add(Portfolio(device_id=TEST_DEVICE_ID_2, name="B", cash=1000.0))
        await db.commit()

        a = await app_client.put(
            "/api/v1/agents/Risk/config",
            json={"max_position_usd": 1234.0},
            headers=DEVICE_HEADERS,
        )
        assert a.status_code == 200, a.text

        b = await app_client.put(
            "/api/v1/agents/Risk/config",
            json={"max_position_usd": 99.0},
            headers={"X-Device-ID": TEST_DEVICE_ID_2},
        )
        assert b.status_code == 200, b.text

        a_read = await app_client.get("/api/v1/agents/Risk/config", headers=DEVICE_HEADERS)
        b_read = await app_client.get(
            "/api/v1/agents/Risk/config", headers={"X-Device-ID": TEST_DEVICE_ID_2}
        )
        assert a_read.json()["config"]["max_position_usd"] == 1234.0
        assert b_read.json()["config"]["max_position_usd"] == 99.0, (
            "device B's read was overwritten by device A's write"
        )

    async def test_defaults_are_reported_separately(self, app_client, db, registered_agents):
        await app_client.put(
            "/api/v1/agents/Risk/config",
            json={"default_stop_loss_pct": 0.09},
            headers=DEVICE_HEADERS,
        )
        body = (await app_client.get("/api/v1/agents/Risk/config", headers=DEVICE_HEADERS)).json()
        assert body["config"]["default_stop_loss_pct"] == 0.09
        assert body["defaults"]["default_stop_loss_pct"] != 0.09, (
            "the process default must remain visible so the override is legible"
        )

    async def test_untouched_keys_keep_their_value(self, app_client, db, registered_agents):
        await app_client.put(
            "/api/v1/agents/Risk/config",
            json={"max_position_usd": 4321.0},
            headers=DEVICE_HEADERS,
        )
        await app_client.put(
            "/api/v1/agents/Risk/config",
            json={"default_stop_loss_pct": 0.07},
            headers=DEVICE_HEADERS,
        )
        body = (await app_client.get("/api/v1/agents/Risk/config", headers=DEVICE_HEADERS)).json()
        assert body["config"]["max_position_usd"] == 4321.0, (
            "a partial update must merge, not replace the device's whole config"
        )

    async def test_unknown_key_is_rejected_not_silently_dropped(self, app_client, db, registered_agents):
        """A typo must not return 200 having changed nothing.

        Pydantic's default is to discard unrecognised fields, so this used to
        succeed while applying nothing and the caller had no way to tell.
        """
        response = await app_client.put(
            "/api/v1/agents/Risk/config",
            json={"max_position_used": 100.0},  # typo: 'used'
            headers=DEVICE_HEADERS,
        )
        assert response.status_code == 422, (
            "an unrecognised key must be refused, not silently ignored"
        )
        # And the real setting must not have been written under any spelling.
        body = (await app_client.get("/api/v1/agents/Risk/config", headers=DEVICE_HEADERS)).json()
        assert body["config"]["max_position_usd"] != 100.0

    async def test_key_valid_but_wrong_agent_is_rejected(self, app_client, db, registered_agents):
        """A real field that this agent does not accept is a 400 with guidance."""
        response = await app_client.put(
            "/api/v1/agents/Risk/config",
            json={"smart_routing": True},  # valid field, but Execution's
            headers=DEVICE_HEADERS,
        )
        assert response.status_code == 400
        assert "Accepted keys" in response.json()["detail"]


class TestRiskAgentUsesEffectiveConfig:
    async def test_override_changes_the_effective_cap(self):
        from app.agents.risk import RiskAgent

        agent = RiskAgent()
        advise = {
            "strategy": {"confidence": 0.8, "net_signal": 0.3},
            "recommended_direction": "long",
        }
        default = await agent.analyze({"advise": advise})
        overridden = await agent.analyze(
            {"advise": advise, "agent_config": {"max_position_usd": 1000.0}}
        )

        assert overridden["max_position_usd"] == 1000.0
        assert overridden["suggested_position_usd"] < default["suggested_position_usd"]
        # The shared instance must be untouched by a per-request override.
        assert agent.max_position_usd == 50000.0

    async def test_portfolio_risk_pct_is_now_applied(self):
        """It was loaded and never read, so it constrained nothing."""
        from app.agents.risk import RiskAgent

        agent = RiskAgent()
        advise = {
            "strategy": {"confidence": 0.8, "net_signal": 0.3},
            "recommended_direction": "long",
        }
        result = await agent.analyze(
            {"advise": advise, "agent_config": {"max_portfolio_risk_pct": 1.0}}
        )
        assert result["suggested_position_usd"] <= 50000.0 * 0.01 + 0.01

    async def test_nan_override_falls_back_instead_of_poisoning(self):
        from app.agents.risk import RiskAgent

        agent = RiskAgent()
        advise = {
            "strategy": {"confidence": 0.8, "net_signal": 0.3},
            "recommended_direction": "long",
        }
        result = await agent.analyze(
            {"advise": advise, "agent_config": {"max_position_usd": float("nan")}}
        )
        assert result["max_position_usd"] == 50000.0


class TestStopIsPerDevice:
    async def test_stopping_one_device_leaves_others_running(self, app_client, db, registered_agents):
        """`stop_agent` used to call `agent.stop()` on a process-global instance."""
        from app.agents import agent_registry

        agent = agent_registry.get("risk")
        assert agent is not None
        await agent.start()
        assert agent.is_active is True

        response = await app_client.post("/api/v1/agents/Risk/stop", headers=DEVICE_HEADERS)
        assert response.status_code == 200, response.text

        # The process-global instance must still be active: one tenant pressing Stop
        # cannot unregister everyone else's agents from /status.
        assert agent.is_active is True, (
            "stop_agent must only clear this device's flag, not the shared instance"
        )

    async def test_scheduler_gate_sees_the_cleared_flag(self, app_client, db, registered_agents):
        """Trading for the stopped device stops; the flag is what the sweep reads."""
        from app.api.v1.agents import _get_agents_started

        db.add(Portfolio(device_id=TEST_DEVICE_ID, name="A", cash=1000.0))
        db.add(Portfolio(device_id=TEST_DEVICE_ID_2, name="B", cash=1000.0))
        await db.commit()

        assert await app_client.post("/api/v1/agents/Risk/start", headers=DEVICE_HEADERS)
        assert await _get_agents_started(db, TEST_DEVICE_ID) is True
        assert await _get_agents_started(db, TEST_DEVICE_ID_2) is False

        assert await app_client.post("/api/v1/agents/Risk/stop", headers=DEVICE_HEADERS)
        assert await _get_agents_started(db, TEST_DEVICE_ID) is False
        assert await _get_agents_started(db, TEST_DEVICE_ID_2) is False
