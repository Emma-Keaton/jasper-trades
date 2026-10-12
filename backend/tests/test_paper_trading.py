"""Universal Paper Trading engine: fills, ledger, PnL, normalization."""
from conftest import TEST_DEVICE_ID, TEST_DEVICE_ID_2
import pytest

from app.services.paper_trading_service import get_paper_trading_service


@pytest.fixture(autouse=True)
def _fresh_ledger():
    get_paper_trading_service().clear_cache()
    yield


async def test_initial_account_defaults():
    acct = await get_paper_trading_service().get_account(TEST_DEVICE_ID)
    assert acct["enabled"] is True
    assert acct["initial_capital"] == 10000.0
    assert acct["current_balance"] == 10000.0
    assert acct["positions"] == {}
    assert acct["trade_count"] == 0


async def test_place_buy_updates_balance_and_position():
    result = await get_paper_trading_service().place_trade(
        device_id=TEST_DEVICE_ID, symbol="BTC", side="buy", qty=0.05, price=60000,
        asset_class="crypto",
    )
    assert result["success"] is True
    assert result["quantity"] == 0.05
    assert result["balance"] < 10000.0

    acct = await get_paper_trading_service().get_account(TEST_DEVICE_ID)
    assert acct["positions"]["BTC"]["qty"] == 0.05
    assert acct["positions"]["BTC"]["avg_price"] == 60000.0
    assert acct["trade_count"] == 1


async def test_insufficient_balance_rejected():
    result = await get_paper_trading_service().place_trade(
        device_id=TEST_DEVICE_ID, symbol="BTC", side="buy", qty=100, price=60000,
        asset_class="crypto",
    )
    assert "error" in result
    assert "Insufficient" in result["error"]


async def test_sell_without_position_rejected():
    result = await get_paper_trading_service().place_trade(
        device_id=TEST_DEVICE_ID, symbol="BTC", side="sell", qty=1, price=60000,
        asset_class="crypto",
    )
    assert "error" in result
    assert "Insufficient paper position" in result["error"]


async def test_buy_then_sell_realizes_pnl():
    svc = get_paper_trading_service()
    await svc.place_trade(device_id=TEST_DEVICE_ID, symbol="BTC", side="buy", qty=1, price=100, asset_class="crypto")
    result = await svc.place_trade(device_id=TEST_DEVICE_ID, symbol="BTC", side="sell", qty=1, price=200, asset_class="crypto")
    assert result["realized_pnl"] > 0

    acct = await svc.get_account(TEST_DEVICE_ID)
    assert "BTC" not in acct["positions"]
    assert acct["wins"] == 1


async def test_buy_then_sell_realizes_loss():
    svc = get_paper_trading_service()
    await svc.place_trade(device_id=TEST_DEVICE_ID, symbol="BTC", side="buy", qty=1, price=200, asset_class="crypto")
    result = await svc.place_trade(device_id=TEST_DEVICE_ID, symbol="BTC", side="sell", qty=1, price=100, asset_class="crypto")
    assert result["realized_pnl"] < 0

    acct = await svc.get_account(TEST_DEVICE_ID)
    assert acct["losses"] == 1


async def test_average_price_on_multiple_buys():
    svc = get_paper_trading_service()
    await svc.place_trade(device_id=TEST_DEVICE_ID, symbol="AAPL", side="buy", qty=1, price=100, asset_class="stocks")
    await svc.place_trade(device_id=TEST_DEVICE_ID, symbol="AAPL", side="buy", qty=1, price=200, asset_class="stocks")
    acct = await svc.get_account(TEST_DEVICE_ID)
    assert acct["positions"]["AAPL"]["qty"] == 2
    assert abs(acct["positions"]["AAPL"]["avg_price"] - 150) < 1e-9


async def test_forex_lot_normalization():
    # 0.01 lot * 100k base units * 1.1 price = 1100 notional - affordable.
    result = await get_paper_trading_service().place_trade(
        device_id=TEST_DEVICE_ID, symbol="EUR/USD", side="buy", qty=0.01, price=1.1,
        asset_class="forex",
    )
    assert result["success"] is True
    assert result["quantity"] == 0.01


async def test_invalid_quantity_or_price_rejected():
    result = await get_paper_trading_service().place_trade(
        device_id=TEST_DEVICE_ID, symbol="BTC", side="buy", qty=0, price=100,
        asset_class="crypto",
    )
    assert result.get("error") == "Invalid quantity or price"


async def test_state_is_per_device():
    svc = get_paper_trading_service()
    await svc.place_trade(device_id=TEST_DEVICE_ID, symbol="BTC", side="buy", qty=1, price=100, asset_class="crypto")
    acct_b = await svc.get_account(TEST_DEVICE_ID_2)
    assert acct_b["positions"] == {}
    assert acct_b["current_balance"] == 10000.0


async def test_reset_account_restores_initial():
    svc = get_paper_trading_service()
    await svc.place_trade(device_id=TEST_DEVICE_ID, symbol="BTC", side="buy", qty=1, price=100, asset_class="crypto")
    await svc.reset_account(TEST_DEVICE_ID)
    acct = await svc.get_account(TEST_DEVICE_ID)
    assert acct["current_balance"] == 10000.0
    assert acct["positions"] == {}
    assert acct["trade_count"] == 0


async def test_bracket_levels_stored_on_buy(monkeypatch):
    from app.services.valuation_service import ValuationService

    svc = get_paper_trading_service()
    await svc.place_trade(
        device_id=TEST_DEVICE_ID, symbol="BTC", side="buy", qty=1, price=100,
        asset_class="crypto", stop_loss=90, take_profit=120,
    )
    state = await svc._load_state(TEST_DEVICE_ID)
    assert state["positions"]["BTC"]["stop_loss"] == 90
    assert state["positions"]["BTC"]["take_profit"] == 120

    async def _price(_self, _symbol):
        return 85.0  # below the stop

    monkeypatch.setattr(ValuationService, "get_price", _price)
    closed = await svc.check_brackets(TEST_DEVICE_ID)
    assert len(closed) == 1
    assert closed[0]["trigger"] == "stop_loss"
    assert closed[0]["symbol"] == "BTC"

    acct = await svc.get_account(TEST_DEVICE_ID)
    assert "BTC" not in acct["positions"]
    assert acct["losses"] == 1


async def test_bracket_take_profit_closes_and_no_trigger_holds(monkeypatch):
    from app.services.valuation_service import ValuationService

    svc = get_paper_trading_service()
    await svc.place_trade(
        device_id=TEST_DEVICE_ID, symbol="ETH", side="buy", qty=1, price=100,
        asset_class="crypto", stop_loss=50, take_profit=150,
    )

    async def _mid(_self, _symbol):
        return 100.0  # inside the bracket

    monkeypatch.setattr(ValuationService, "get_price", _mid)
    assert await svc.check_brackets(TEST_DEVICE_ID) == []
    acct = await svc.get_account(TEST_DEVICE_ID)
    assert "ETH" in acct["positions"]

    async def _high(_self, _symbol):
        return 155.0  # through the take-profit

    monkeypatch.setattr(ValuationService, "get_price", _high)
    closed = await svc.check_brackets(TEST_DEVICE_ID)
    assert len(closed) == 1
    assert closed[0]["trigger"] == "take_profit"
    assert closed[0]["realized_pnl"] > 0
    acct = await svc.get_account(TEST_DEVICE_ID)
    assert "ETH" not in acct["positions"]
    assert acct["wins"] == 1


def test_opt_float_coercion():
    from app.services.signal_sources.ingest import _opt_float

    assert _opt_float("1.5") == 1.5
    assert _opt_float(2) == 2.0
    assert _opt_float(None) is None
    assert _opt_float(0) is None
    assert _opt_float(-1) is None
    assert _opt_float("abc") is None
