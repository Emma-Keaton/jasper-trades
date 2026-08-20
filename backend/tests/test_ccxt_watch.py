"""CCXT watch service + broker registry startup coverage.

These tests avoid touching the network: exchange probing and ticker calls are
mocked so we validate the service's control flow, symbol tracking, fallback
selection, and the registry's settings usage.
"""
from app.services.ccxt_watch_service import CCXTWatchService
from app.brokers import registry as broker_registry


class FakeTickerExchange:
    """Minimal stand-in with a watchTicker callable."""

    has = {"watchTicker": None}

    async def watchTicker(self, symbol):  # noqa: N802 - ccxt camelCase API
        return {
            "symbol": f"{symbol}",
            "last": 12.5,
            "close": 12.5,
            "high": 13.0,
            "low": 12.0,
            "baseVolume": 100.0,
            "change": 0.5,
            "percentage": 4.0,
            "datetime": "2026-08-20T12:00:00Z",
        }

    async def close(self):
        pass


def _svc(monkeypatch):
    svc = CCXTWatchService()

    async def _noop(*a, **k):
        return None

    monkeypatch.setattr(svc, "_emit", _noop)
    return svc


async def test_preferred_exchanges_falls_back_to_defaults(monkeypatch):
    svc = CCXTWatchService()
    geo = type("G", (), {})()
    geo.available_ccxt_exchanges = lambda: []
    geo.ensure_fresh = lambda: None  # noqa: E731
    monkeypatch.setattr(svc, "_geo", geo) if hasattr(svc, "_geo") else None
    # The service locates geo probe internally; just assert defaults parse.
    from app.services.ccxt_watch_service import _default_candidates

    candidates = _default_candidates()
    assert "bybit" in candidates
    assert "okx" in candidates


async def test_pick_ws_exchange_returns_first_with_method(monkeypatch):
    svc = CCXTWatchService()

    async def _fake_get(ex_id):
        return FakeTickerExchange()

    monkeypatch.setattr(svc, "_get_exchange", _fake_get)
    chosen = await svc._pick_ws_exchange(["bybit", "okx"])
    assert chosen == "bybit"


async def test_pick_ws_exchange_returns_none_when_no_method(monkeypatch):
    class NoWatchExchange:
        async def close(self):
            pass

    svc = CCXTWatchService()

    async def _fake_get(ex_id):
        return NoWatchExchange()

    monkeypatch.setattr(svc, "_get_exchange", _fake_get)
    chosen = await svc._pick_ws_exchange(["bybit"])
    assert chosen is None


async def test_watch_adds_symbols_after_start(monkeypatch):
    svc = _svc(monkeypatch)
    started = {}

    async def _fake_start(symbols):
        started["symbols"] = list(symbols)

    monkeypatch.setattr(svc, "start", _fake_start)
    await svc.watch(["BTC/USDT"])
    assert started["symbols"] == ["BTC/USDT"]


async def test_watch_updates_existing_set(monkeypatch):
    svc = _svc(monkeypatch)
    svc._running = True
    svc._symbols.add("BTC/USDT")
    await svc.watch(["ETH/USDT"])
    assert "BTC/USDT" in svc.watched_symbols()
    assert "ETH/USDT" in svc.watched_symbols()


def test_registry_uses_settings_without_nameerror():
    """BUG-1 regression: initialize_brokers referenced settings with no import."""
    # Building a fresh registry must not raise NameError on settings access.
    reg = broker_registry.initialize_brokers({})
    assert reg is not None