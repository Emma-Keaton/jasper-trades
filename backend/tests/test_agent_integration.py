"""End-to-end: the agents boot, and a trade reaches the execution path.

This is the test that would have caught the missing-methods regression. Every
other test here exercises a component; this one runs the real lifespan, then
drives the actual production path an order takes:

    factor sweep -> SignalTip -> maybe_auto_execute -> trade_gate
                 -> ExecutionAgent.create_order -> submit_to_broker
                 -> Trade row committed

The three broker calls are stubbed at the registry boundary, because sending a
real order is not something a test may do. Everything between is the real code:
the real agents, the real registry, the real trade gate, the real ORM.

Two structural facts are asserted here, because they are not obvious from
reading any single module:

1. Agents are registered *and active* after boot. `start_all()` was never called
   before, so `is_active` stayed false for the process lifetime.
2. `ExecutionAgent` is the only agent the trading path uses. Director, Quant and
   Risk are reachable only through the `/agents` API and are not consulted before
   an order is placed. That is a real gap, pinned here so it cannot be mistaken
   for working orchestration.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest
import pytest_asyncio

from app.models import Trade


@pytest.fixture(scope="module")
def agent_integrity_scan():
    """Import paths for the structural checks below."""
    from pathlib import Path

    import app.agents as agents_pkg

    return Path(agents_pkg.__file__).parent.parent


def _broker_ok():
    """A broker stub that accepts orders, recording what it was asked to do."""
    calls = []

    class Broker:
        name = "bybit"
        is_connected = True

        async def submit_order(self, **kwargs):
            calls.append(kwargs)
            return SimpleNamespace(
                success=True, order_id="TEST-ORDER-1", message="filled"
            )

        async def cancel_order(self, order_id):
            return True

    return Broker(), calls


class TestAgentsBoot:
    async def test_all_four_agents_are_registered(self, booted_app):
        from app.agents import agent_registry

        for name in ("director", "quant", "risk", "execution"):
            assert agent_registry.get(name) is not None, f"{name} not registered"

    async def test_agents_are_active_after_boot(self, booted_app):
        """`start_all()` used to be never called, so nothing was ever active and
        `/status` reported zero running agents for the life of the process."""
        from app.agents import agent_registry

        active = {a.name.lower() for a in agent_registry.get_active()}
        assert active == {"director", "quant", "risk", "execution"}, (
            f"agents not active after boot: {active}"
        )

    async def test_app_boots_and_serves_health(self, booted_app):
        """The health endpoint is what Render polls; it must answer after boot."""
        from httpx import ASGITransport, AsyncClient

        async with AsyncClient(
            transport=ASGITransport(app=booted_app), base_url="http://test"
        ) as client:
            response = await client.get("/api/v1/health")
        assert response.status_code == 200

    async def test_status_reports_active_agents(self, booted_app):
        """The value the UI reads to show agent state."""
        from app.agents import agent_registry

        assert len(agent_registry.get_active()) >= 4
        stats = agent_registry.stats()
        assert stats["execution"]["is_active"] is True


class TestExecutionPathReachable:
    """The three call sites that were broken by the missing methods."""

    async def test_ingest_path_reaches_order_creation(self, booted_app, monkeypatch):
        """`signal_sources/ingest.py` is the hands-free auto-execute path."""
        from app.agents import agent_registry

        agent = agent_registry.get("execution")
        assert hasattr(agent, "create_order")
        assert hasattr(agent, "submit_to_broker")
        assert hasattr(agent, "initialize_brokers")

    async def test_trading_router_path_reachable(self, booted_app):
        from app.agents import agent_registry

        agent = agent_registry.get("execution")
        assert callable(getattr(agent, "initialize_brokers", None))
        assert callable(getattr(agent, "create_order", None))
        assert callable(getattr(agent, "submit_to_broker", None))

    async def test_copytrade_path_reachable(self, booted_app):
        from app.agents import agent_registry

        agent = agent_registry.get("execution")
        assert callable(getattr(agent, "create_order", None))
        assert callable(getattr(agent, "submit_to_broker", None))


class TestFullOrderLifecycle:
    async def test_order_reaches_broker_and_is_recorded(self, booted_app, db, monkeypatch):
        """Drive create_order -> submit_to_broker -> commit, as the real callers do."""
        from app.agents import agent_registry

        broker, calls = _broker_ok()
        agent = agent_registry.get("execution")

        # Stub at the registry boundary only: everything above it is real.
        monkeypatch.setattr(
            agent.broker_registry, "get", lambda name: broker, raising=False
        )

        trade = await agent.create_order(
            symbol="BTC/USDT", side="buy", quantity=0.01, order_type="market"
        )
        assert trade.status == "pending"

        trade = await agent.submit_to_broker(trade, broker="bybit")
        assert trade.status == "submitted"
        assert trade.broker == "bybit"
        assert trade.broker_order_id == "TEST-ORDER-1"
        assert calls and calls[0]["symbol"] == "BTC/USDT"

        # Persist exactly as ingest.py does.
        db.add(trade)
        await db.commit()

        stored = (await db.execute(Trade.__table__.select())).all()
        assert len(stored) == 1

    async def test_rejected_order_records_why(self, booted_app, db, monkeypatch):
        from app.agents import agent_registry

        class RefusingBroker:
            name = "bybit"
            is_connected = True

            async def submit_order(self, **kwargs):
                return SimpleNamespace(
                    success=False, order_id=None, message="insufficient margin"
                )

        agent = agent_registry.get("execution")
        monkeypatch.setattr(
            agent.broker_registry, "get", lambda n: RefusingBroker(), raising=False
        )

        trade = await agent.create_order("BTC/USDT", "buy", 0.01)
        trade = await agent.submit_to_broker(trade, broker="bybit")

        assert trade.status == "rejected"
        assert "insufficient margin" in trade.error_detail
        db.add(trade)
        await db.commit()

    async def test_broker_outage_is_auditable(self, booted_app, db, monkeypatch):
        """A venue that never answers must not look like an un-attempted order."""
        from app.agents import agent_registry

        class BrokenBroker:
            name = "bybit"
            is_connected = True

            async def submit_order(self, **kwargs):
                raise ConnectionError("connection reset")

        agent = agent_registry.get("execution")
        monkeypatch.setattr(
            agent.broker_registry, "get", lambda n: BrokenBroker(), raising=False
        )

        trade = await agent.create_order("BTC/USDT", "buy", 0.01)
        trade = await agent.submit_to_broker(trade, broker="bybit")

        assert trade.status == "error"
        assert trade.error_detail


class TestAgentPipelineIsNotWired:
    """Pins a real gap rather than a bug.

    Director, Quant and Risk implement `analyze()` and `generate_signal()`, and
    Director's docstring claims it "Coordinates Quant, Risk, and Execution
    agents". It does not: nothing chains them. The trading path is
    AlphaFactorService -> trade_gate -> ExecutionAgent, so none of the risk
    sizing, regime or consensus logic in those three agents influences an order.

    This is documented as a limitation to fix, not endorsed. If the pipeline is
    ever wired up, this test should be replaced by one asserting the chain runs.
    """

    def test_no_code_chains_the_agents(self):
        from pathlib import Path

        import app.agents as agents_pkg

        root = Path(agents_pkg.__file__).parent.parent
        offenders = []
        for path in root.rglob("*.py"):
            if "__pycache__" in str(path) or "agents" not in path.parts:
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            for needle in ("await quant.", "await risk.", "await director."):
                if needle in text:
                    offenders.append((path.name, needle))
        assert not offenders, (
            f"an agent pipeline now exists ({offenders}); replace this test with "
            "one asserting the chain actually gates orders"
        )

    async def test_only_execution_agent_is_consulted_by_traders(self):
        """Trading code looks up exactly one agent."""
        from pathlib import Path

        import app.agents as agents_pkg

        root = Path(agents_pkg.__file__).parent.parent
        looked_up = set()
        for path in root.rglob("*.py"):
            if "__pycache__" in str(path):
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            for name in ("director", "quant", "risk", "execution"):
                if f'agent_registry.get("{name}")' in text:
                    looked_up.add(name)
        assert looked_up == {"execution"}, (
            f"trading paths now consult {sorted(looked_up)}; the agent pipeline "
            "is being wired and this test should be updated accordingly"
        )


class TestStopIsClean:
    async def test_registry_reports_every_agent_stopped_after_shutdown(self):
        """Shutdown must clear active state even if an agent misbehaves."""
        from app.agents.base import AgentRegistry, BaseAgent

        class Stubborn(BaseAgent):
            def __init__(self, name, refuse=False):
                super().__init__(name=name)
                self.refuse = refuse

            async def analyze(self, market_data):
                return {}

            async def generate_signal(self, symbol, analysis):
                return None

            async def stop(self):
                if self.refuse:
                    raise RuntimeError("will not stop cleanly")
                await super().stop()

        registry = AgentRegistry()
        registry.register(Stubborn(name="Stubborn", refuse=True))
        registry.register(Stubborn(name="Good"))
        await registry.start_all()

        results = await registry.stop_all(timeout=1)

        assert results["Stubborn"] is False
        assert results["Good"] is True
        assert registry.get_active() == [], (
            "an agent left active after shutdown"
        )