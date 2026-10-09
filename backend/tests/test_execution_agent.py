"""Tests for the execution agent and the agent registry.

The regression these exist for: `create_order`, `submit_to_broker` and
`initialize_brokers` were removed from `ExecutionAgent` in a refactor while three
live call sites kept using them, and nothing caught it. Every order raised
`AttributeError`. The tests below execute the real path, so removing a method
again fails here rather than in production.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from app.agents.base import AgentRegistry, BaseAgent
from app.agents.execution import ExecutionAgent


# ---------------------------------------------------------------------------
# The call-site contract
# ---------------------------------------------------------------------------

class TestCallSiteContract:
    """These are the exact members the three live callers use.

    `app/api/v1/trading.py`, `app/services/copytrade_service.py` and
    `app/services/signal_sources/ingest.py` are the production consumers. This
    test is the contract they were written against.
    """

    @pytest.mark.parametrize(
        "member", ["create_order", "submit_to_broker", "initialize_brokers"]
    )
    def test_required_members_exist(self, member):
        assert hasattr(ExecutionAgent, member), (
            f"ExecutionAgent.{member} is missing. Three call sites use it and "
            "every order will raise AttributeError without it."
        )

    @pytest.mark.parametrize(
        "member", ["create_order", "submit_to_broker", "initialize_brokers"]
    )
    def test_required_members_are_awaitable(self, member):
        assert asyncio.iscoroutinefunction(getattr(ExecutionAgent, member))

    def test_brokers_initialized_flag_exists(self):
        """`ingest.py` reads `_brokers_initialized` via getattr with a default,
        but `trading.py` reads it directly - so it must exist on a fresh agent."""
        assert ExecutionAgent()._brokers_initialized is False

    def test_stop_is_awaitable_and_overridden(self):
        """The agent opens broker connections, so it must close them on stop."""
        assert asyncio.iscoroutinefunction(ExecutionAgent.stop)
        assert ExecutionAgent.stop is not BaseAgent.stop


# ---------------------------------------------------------------------------
# Order creation
# ---------------------------------------------------------------------------

class TestCreateOrder:
    async def test_builds_a_pending_trade(self):
        trade = await ExecutionAgent().create_order(
            symbol="btc/usdt", side="buy", quantity=0.5
        )
        assert trade.status == "pending"
        assert trade.symbol == "BTC/USDT"
        assert trade.side == "buy"
        assert trade.quantity == 0.5
        assert trade.order_type == "market"
        assert trade.agent_name == "Execution"

    @pytest.mark.parametrize("side", ["buy", "sell", "BUY", "Sell", "long", "short"])
    async def test_accepts_valid_sides(self, side):
        trade = await ExecutionAgent().create_order("BTC", side, 1)
        assert trade.side == side.strip().lower()

    @pytest.mark.parametrize("side", ["", None, "hodl", "BUY NOW", "b"])
    async def test_rejects_invalid_sides(self, side):
        """A bad side must be refused locally rather than sent and rejected by a
        venue after the order has been built."""
        with pytest.raises(ValueError, match="side"):
            await ExecutionAgent().create_order("BTC", side, 1)

    @pytest.mark.parametrize("quantity", [0, -1, -0.001])
    async def test_rejects_non_positive_quantity(self, quantity):
        with pytest.raises(ValueError, match="positive"):
            await ExecutionAgent().create_order("BTC", "buy", quantity)

    @pytest.mark.parametrize("quantity", ["abc", None, [1]])
    async def test_rejects_non_numeric_quantity(self, quantity):
        with pytest.raises(ValueError, match="numeric"):
            await ExecutionAgent().create_order("BTC", "buy", quantity)

    @pytest.mark.parametrize("quantity", ["1.5", 1, 1.0, 0.001])
    async def test_accepts_numeric_strings_and_floats(self, quantity):
        trade = await ExecutionAgent().create_order("BTC", "buy", quantity)
        assert float(trade.quantity) == pytest.approx(float(quantity))

    @pytest.mark.parametrize("symbol", ["", "   ", None])
    async def test_rejects_empty_symbol(self, symbol):
        with pytest.raises(ValueError, match="symbol"):
            await ExecutionAgent().create_order(symbol, "buy", 1)

    async def test_rejects_unknown_order_type(self):
        with pytest.raises(ValueError, match="order_type"):
            await ExecutionAgent().create_order("BTC", "buy", 1, order_type="mkt")

    async def test_limit_order_requires_a_price(self):
        with pytest.raises(ValueError, match="limit_price"):
            await ExecutionAgent().create_order("BTC", "buy", 1, order_type="limit")

    async def test_stop_order_requires_a_stop_price(self):
        with pytest.raises(ValueError, match="stop_price"):
            await ExecutionAgent().create_order("BTC", "buy", 1, order_type="stop")

    async def test_limit_order_with_price_is_accepted(self):
        trade = await ExecutionAgent().create_order(
            "BTC", "buy", 1, order_type="limit", limit_price=50000.0
        )
        assert trade.price == 50000.0

    async def test_order_creation_makes_no_network_call(self):
        """The previous implementation round-tripped every order through the
        NVIDIA chat API. That added a multi-second round trip and a
        single-point-of-failure to the critical path of every single order."""

        class Exploding:
            async def chat_completion(self, *a, **k):
                raise AssertionError("order creation must not call an LLM")

        agent = ExecutionAgent()
        agent.nvidia_client = Exploding()
        agent.groq_client = Exploding()
        trade = await agent.create_order("BTC", "buy", 1)
        assert trade.status == "pending"


# ---------------------------------------------------------------------------
# Broker initialization
# ---------------------------------------------------------------------------

class TestInitializeBrokers:
    async def test_succeeds_when_a_broker_connects(self, monkeypatch):
        agent = ExecutionAgent()

        async def connect_all():
            return {"binance": True, "trove": False}

        monkeypatch.setattr(
            agent.broker_registry, "connect_all", connect_all, raising=False
        )
        assert await agent.initialize_brokers() is True
        assert agent.brokers_ready() is True

    async def test_returns_false_when_nothing_connects(self, monkeypatch):
        """No exchange keys is a configuration state, not an error."""
        agent = ExecutionAgent()

        async def connect_all():
            return {"binance": False}

        monkeypatch.setattr(
            agent.broker_registry, "connect_all", connect_all, raising=False
        )
        assert await agent.initialize_brokers() is False

    async def test_does_not_raise_when_connect_raises(self, monkeypatch):
        agent = ExecutionAgent()

        async def connect_all():
            raise RuntimeError("exchange unreachable")

        monkeypatch.setattr(
            agent.broker_registry, "connect_all", connect_all, raising=False
        )
        assert await agent.initialize_brokers() is False

    async def test_second_call_does_not_reconnect(self, monkeypatch):
        """Callers hit this on every order. Reconnecting each time would open a
        fresh connection set per order."""
        agent = ExecutionAgent()
        calls = []

        async def connect_all():
            calls.append(1)
            return {"binance": True}

        monkeypatch.setattr(
            agent.broker_registry, "connect_all", connect_all, raising=False
        )
        await agent.initialize_brokers()
        await agent.initialize_brokers()
        await agent.initialize_brokers()
        assert len(calls) == 1

    async def test_concurrent_callers_connect_once(self, monkeypatch):
        """Three call sites race on a cold container. Without a lock each would
        open its own broker connections."""
        agent = ExecutionAgent()
        calls = []

        async def connect_all():
            calls.append(1)
            await asyncio.sleep(0.01)
            return {"binance": True}

        monkeypatch.setattr(
            agent.broker_registry, "connect_all", connect_all, raising=False
        )
        results = await asyncio.gather(
            agent.initialize_brokers(),
            agent.initialize_brokers(),
            agent.initialize_brokers(),
        )
        assert all(results)
        assert len(calls) == 1, "lock must collapse concurrent initialisation"


# ---------------------------------------------------------------------------
# Submission
# ---------------------------------------------------------------------------

def _result(success=True, order_id="ord-1", message="ok"):
    return SimpleNamespace(success=success, order_id=order_id, message=message)


class TestSubmitToBroker:
    async def test_marks_submitted_on_success(self, monkeypatch):
        agent = ExecutionAgent()

        class Broker:
            name = "binance"
            is_connected = True

            async def submit_order(self, **kwargs):
                return _result()

        monkeypatch.setattr(
            agent.broker_registry, "get", lambda name: Broker(), raising=False
        )
        trade = await agent.create_order("BTCUSDT", "buy", 1)
        trade = await agent.submit_to_broker(trade, broker="binance")

        assert trade.status == "submitted"
        assert trade.broker == "binance"
        assert trade.broker_order_id == "ord-1"
        assert agent.trades_executed == 1

    async def test_marks_rejected_when_the_venue_refuses(self, monkeypatch):
        agent = ExecutionAgent()

        class Broker:
            name = "binance"
            is_connected = True

            async def submit_order(self, **kwargs):
                return _result(success=False, message="insufficient balance")

        monkeypatch.setattr(
            agent.broker_registry, "get", lambda name: Broker(), raising=False
        )
        trade = await agent.create_order("BTCUSDT", "buy", 1)
        trade = await agent.submit_to_broker(trade, broker="binance")

        assert trade.status == "rejected"
        assert "insufficient balance" in trade.error_detail
        # A rejection is not an execution.
        assert agent.trades_executed == 0

    async def test_records_the_reason_an_unregistered_broker_failed(self, monkeypatch):
        agent = ExecutionAgent()
        monkeypatch.setattr(
            agent.broker_registry, "get", lambda name: None, raising=False
        )
        trade = await agent.create_order("BTCUSDT", "buy", 1)
        trade = await agent.submit_to_broker(trade, broker="nope")

        assert trade.status == "rejected"
        assert "nope" in trade.error_detail

    async def test_transport_failure_is_recorded_not_raised(self, monkeypatch):
        """A venue that never answered must leave an auditable status, not an
        exception escaping and leaving the row stuck at "pending"."""
        agent = ExecutionAgent()

        class Broken:
            name = "binance"
            is_connected = True

            async def submit_order(self, **kwargs):
                raise ConnectionError("connection reset by peer")

        monkeypatch.setattr(
            agent.broker_registry, "get", lambda name: Broken(), raising=False
        )
        trade = await agent.create_order("BTCUSDT", "buy", 1)
        trade = await agent.submit_to_broker(trade, broker="binance")

        assert trade.status == "error"
        assert agent.trades_executed == 0

    async def test_auto_routing_uses_the_router(self, monkeypatch):
        agent = ExecutionAgent()
        seen = {}

        async def execute_with_routing(**kwargs):
            seen.update(kwargs)
            return [{"broker": "okx", "success": True, "order_id": "x1"}]

        monkeypatch.setattr(
            "app.agents.execution.broker_router.execute_with_routing",
            execute_with_routing,
            raising=False,
        )
        trade = await agent.create_order("BTC/USDT", "buy", 1)
        trade = await agent.submit_to_broker(trade)

        assert trade.status == "submitted"
        assert seen["symbol"] == "BTC/USDT"
        assert seen["quantity"] == 1

    async def test_empty_result_list_is_a_rejection_not_a_crash(self, monkeypatch):
        agent = ExecutionAgent()

        async def execute_with_routing(**kwargs):
            return []

        monkeypatch.setattr(
            "app.agents.execution.broker_router.execute_with_routing",
            execute_with_routing,
            raising=False,
        )
        trade = await agent.create_order("BTC/USDT", "buy", 1)
        trade = await agent.submit_to_broker(trade)
        assert trade.status == "rejected"

    async def test_requires_a_trade(self):
        with pytest.raises(ValueError):
            await ExecutionAgent().submit_to_broker(None)

    async def test_counts_only_successes_across_multi_broker(self, monkeypatch):
        agent = ExecutionAgent()

        async def execute_with_routing(**kwargs):
            return [
                {"broker": "a", "success": False, "message": "down"},
                {"broker": "b", "success": True, "order_id": "o2"},
            ]

        monkeypatch.setattr(
            "app.agents.execution.broker_router.execute_with_routing",
            execute_with_routing,
            raising=False,
        )
        trade = await agent.create_order("BTC/USDT", "buy", 1)
        trade = await agent.submit_to_broker(trade)

        assert trade.broker == "b"
        assert agent.trades_executed == 1


class TestSubmitOrderSingleCall:
    async def test_creates_and_submits(self, monkeypatch):
        agent = ExecutionAgent()

        class Broker:
            name = "binance"
            is_connected = True

            async def submit_order(self, **kwargs):
                return _result()

        async def connect_all():
            return {"binance": True}

        monkeypatch.setattr(
            agent.broker_registry, "get", lambda name: Broker(), raising=False
        )
        monkeypatch.setattr(
            agent.broker_registry, "connect_all", connect_all, raising=False
        )

        result = await agent.submit_order("BTCUSDT", "buy", 1)
        assert result["success"] is True
        assert result["status"] == "submitted"

    async def test_reports_failure_without_raising(self, monkeypatch):
        """This previously raised ImportError on every call, because it imported
        a `place_order` helper that does not exist."""
        agent = ExecutionAgent()

        class Broker:
            name = "binance"
            is_connected = True

            async def submit_order(self, **kwargs):
                return _result(success=False, message="venue down")

        async def connect_all():
            return {"binance": True}

        monkeypatch.setattr(
            agent.broker_registry, "get", lambda name: Broker(), raising=False
        )
        monkeypatch.setattr(
            agent.broker_registry, "connect_all", connect_all, raising=False
        )

        result = await agent.submit_order("BTCUSDT", "buy", 1)
        assert result["success"] is False
        assert result["status"] == "rejected"

    async def test_validates_before_connecting(self, monkeypatch):
        """A bad side must not cause a broker connection to be opened."""
        agent = ExecutionAgent()

        async def connect_all():
            raise AssertionError("must not connect for an invalid order")

        monkeypatch.setattr(
            agent.broker_registry, "connect_all", connect_all, raising=False
        )
        with pytest.raises(ValueError):
            await agent.submit_order("BTCUSDT", "not-a-side", 1)


class TestCancelOrder:
    async def test_cancels_locally_when_nothing_was_submitted(self):
        trade = await ExecutionAgent().create_order("BTC", "buy", 1)
        assert await ExecutionAgent().cancel_order(trade) is True
        assert trade.status == "cancelled"

    async def test_refuses_to_cancel_a_filled_order(self):
        trade = await ExecutionAgent().create_order("BTC", "buy", 1)
        trade.status = "filled"
        assert await ExecutionAgent().cancel_order(trade) is False
        assert trade.status == "filled"

    async def test_failure_returns_false_rather_than_raising(self, monkeypatch):
        agent = ExecutionAgent()
        trade = await agent.create_order("BTC", "buy", 1)
        trade.broker = "binance"

        class Broker:
            is_connected = True

            async def cancel_order(self, order_id):
                raise RuntimeError("venue timeout")

        monkeypatch.setattr(
            agent.broker_registry, "get", lambda name: Broker(), raising=False
        )
        assert await agent.cancel_order(trade) is False


class TestAnalyze:
    async def test_flags_poor_conditions(self):
        result = await ExecutionAgent().analyze(
            {"orderbook": {"spread_pct": 2.0, "liquidity_usd": 100}}
        )
        assert result["spread_acceptable"] is False
        assert result["liquidity_ok"] is False

    async def test_flags_good_conditions(self):
        result = await ExecutionAgent().analyze(
            {"orderbook": {"spread_pct": 0.05, "liquidity_usd": 500_000}}
        )
        assert result["spread_acceptable"] is True
        assert result["liquidity_ok"] is True

    async def test_missing_orderbook_fails_safe(self):
        """Absent data must read as "not acceptable", never as acceptable."""
        result = await ExecutionAgent().analyze({})
        assert result["spread_acceptable"] is False
        assert result["liquidity_ok"] is False

    async def test_malformed_input_does_not_raise(self):
        result = await ExecutionAgent().analyze(
            {"orderbook": {"spread_pct": "not-a-number"}}
        )
        assert result["spread_acceptable"] is False

    async def test_generate_signal_refuses_on_bad_conditions(self):
        agent = ExecutionAgent()
        assert await agent.generate_signal("BTC", {"spread_acceptable": False}) is None
        assert agent.signals_generated == 0


# ---------------------------------------------------------------------------
# Registry lifecycle
# ---------------------------------------------------------------------------

class _Stub(BaseAgent):
    def __init__(self, name, fail_start=False, fail_stop=False, hang=False):
        super().__init__(name=name)
        self.fail_start = fail_start
        self.fail_stop = fail_stop
        self.hang = hang

    async def analyze(self, market_data):
        return {}

    async def generate_signal(self, symbol, analysis):
        return None

    async def start(self):
        if self.fail_start:
            raise RuntimeError("start failed")
        if self.hang:
            await asyncio.sleep(60)
        await super().start()

    async def stop(self):
        if self.fail_stop:
            raise RuntimeError("stop failed")
        if self.hang:
            await asyncio.sleep(60)
        await super().stop()


class TestRegistryLifecycle:
    async def test_start_all_marks_agents_active(self):
        registry = AgentRegistry()
        registry.register(_Stub("Director"))
        registry.register(_Stub("Quant"))

        results = await registry.start_all()

        assert results == {"Director": True, "Quant": True}
        assert len(registry.get_active()) == 2

    async def test_one_failed_start_does_not_block_the_others(self):
        registry = AgentRegistry()
        registry.register(_Stub("Good"))
        registry.register(_Stub("Bad", fail_start=True))
        registry.register(_Stub("Other"))

        results = await registry.start_all()

        assert results["Good"] is True
        assert results["Bad"] is False
        # The failure must not leave its siblings inactive.
        assert len(registry.get_active()) == 2

    async def test_stop_all_clears_every_agent(self):
        registry = AgentRegistry()
        registry.register(_Stub("A"))
        registry.register(_Stub("B"))
        await registry.start_all()

        results = await registry.stop_all()

        assert all(results.values())
        assert registry.get_active() == []

    async def test_one_failed_stop_does_not_skip_the_rest(self):
        """Previously a raise from the first agent skipped every later one,
        leaving broker connections open through shutdown."""
        registry = AgentRegistry()
        registry.register(_Stub("Good"))
        registry.register(_Stub("Bad", fail_stop=True))
        registry.register(_Stub("Other"))
        await registry.start_all()

        await registry.stop_all()

        assert registry.get_active() == [], (
            "every agent must be stopped even if one raises"
        )

    async def test_hanging_stop_is_bounded(self):
        """Render sends SIGTERM then force-kills; an agent that will not stop
        must not consume the grace period."""
        registry = AgentRegistry()
        registry.register(_Stub("Stuck", hang=True))

        results = await registry.stop_all(timeout=0.1)

        assert results["Stuck"] is False

    async def test_registry_lookup_is_case_insensitive(self):
        registry = AgentRegistry()
        registry.register(_Stub("Execution"))
        assert registry.get("EXECUTION") is registry.get("execution")
        assert registry.get("missing") is None

    async def test_stats_reports_active_state(self):
        """`/status` reads `get_active()`; it must not be permanently empty."""
        registry = AgentRegistry()
        registry.register(_Stub("Director"))
        assert registry.get_active() == []
        await registry.start_all()
        assert len(registry.get_active()) == 1
        assert registry.stats()["director"]["is_active"] is True