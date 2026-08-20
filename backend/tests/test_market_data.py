"""Market data router: priority-chain failover across mocked providers."""
from app.services import market_data_router as mdr


async def test_chain_falls_through_to_second_provider(monkeypatch):
    router = mdr.MarketDataRouter()

    async def _fail(symbol):
        return None

    async def _ok(symbol):
        return {"symbol": symbol, "price": 42.0}

    monkeypatch.setattr(router, "_coingecko", _fail)
    monkeypatch.setattr(router, "_ccxt", _ok)

    result = await router.get_price("BTC")
    assert result["price"] == 42.0
    assert result["provider"] == "ccxt"


async def test_chain_exception_is_caught(monkeypatch):
    router = mdr.MarketDataRouter()

    async def _explode(symbol):
        raise RuntimeError("provider down")

    async def _ok(symbol):
        return {"symbol": symbol, "price": 1.0}

    monkeypatch.setattr(router, "_coingecko", _explode)
    monkeypatch.setattr(router, "_ccxt", _ok)

    result = await router.get_price("ETH")
    assert result["price"] == 1.0
    assert result["provider"] == "ccxt"


async def test_chain_returns_none_when_all_fail(monkeypatch):
    router = mdr.MarketDataRouter()

    async def _none(symbol):
        return None

    for name in ("_coingecko", "_ccxt", "_coinmarketcap", "_coinlore"):
        monkeypatch.setattr(router, name, _none)

    result = await router.get_price("DOGE")
    assert result["price"] == 0.0
    assert result["provider"] == "none"


def test_symbol_to_coingecko_id():
    assert mdr._symbol_to_coingecko_id("BTC") == "bitcoin"
    assert mdr._symbol_to_coingecko_id("ETH") == "ethereum"
    assert mdr._symbol_to_coingecko_id("SOL") == "solana"
    assert mdr._symbol_to_coingecko_id("btcusdt") == "bitcoin"
    assert mdr._symbol_to_coingecko_id("BTC/USDT") == "bitcoin"
    assert mdr._symbol_to_coingecko_id("DOGE") == "dogecoin"
    assert mdr._symbol_to_coingecko_id("UNKNOWN-XYZ") == "unknown-xyz"
