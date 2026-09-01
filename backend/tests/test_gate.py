"""Trade gate: mode resolution, per-broker prerequisites, caps, cash, breaker."""
import pytest

from app.models import DeviceSettings, Portfolio, TradingCap
from app.models_ext.crypto_credentials import DeviceCryptoCredential
from app.services import trade_gate


# ---------------------------------------------------------------------------
# resolve_mode
# ---------------------------------------------------------------------------

async def test_resolve_mode_default_paper(db):
    assert await trade_gate.resolve_mode(db, "missing-device") == trade_gate.PAPER


async def test_resolve_mode_practice_sandbox_is_paper(db, device_settings):
    assert await trade_gate.resolve_mode(db, "dev-1") == trade_gate.PAPER


async def test_resolve_mode_live_only_when_both_flags(db, live_device):
    assert await trade_gate.resolve_mode(db, "dev-1") == trade_gate.LIVE


async def test_resolve_mode_live_mode_but_sandbox_env(db):
    from app.models import DeviceSettings

    db.add(DeviceSettings(device_id="dev-1", trading_mode="live", environment_mode="sandbox"))
    await db.commit()
    assert await trade_gate.resolve_mode(db, "dev-1") == trade_gate.PAPER


# ---------------------------------------------------------------------------
# Paper prerequisites
# ---------------------------------------------------------------------------

async def test_paper_prerequisites_pass_by_default(db):
    gate = await trade_gate.check_prerequisites(
        db, "dev-1", symbol="BTC", side="buy", qty=0.5, price=60000,
        intent="paper", asset_class="crypto",
    )
    assert gate["passed"] is True
    assert gate["mode"] == "paper"


async def test_invalid_side_fails(db):
    gate = await trade_gate.check_prerequisites(
        db, "dev-1", symbol="BTC", side="hodl", qty=1, price=1, intent="paper",
    )
    assert not gate["passed"]
    names = {c["name"] for c in gate["checks"]}
    assert "valid_side" in names


async def test_nonpositive_quantity_and_price_fail(db):
    gate = await trade_gate.check_prerequisites(
        db, "dev-1", symbol="BTC", side="buy", qty=0, price=-1, intent="paper",
    )
    assert not gate["passed"]
    assert all(
        not c["passed"]
        for c in gate["checks"]
        if c["name"] in ("valid_quantity", "valid_price")
    )


# ---------------------------------------------------------------------------
# Live intent requires a live-configured device
# ---------------------------------------------------------------------------

async def test_live_intent_needs_live_device(db, device_settings):
    gate = await trade_gate.check_prerequisites(
        db, "dev-1", symbol="AAPL", side="buy", qty=1, price=150,
        intent="live", asset_class="stocks",
    )
    assert not gate["passed"]
    check = next(c for c in gate["checks"] if c["name"] == "live_enabled")
    assert check["passed"] is False


# ---------------------------------------------------------------------------
# Per-broker gates
# ---------------------------------------------------------------------------

async def test_live_cn_requires_tiger(db, live_device):
    gate = await trade_gate.check_prerequisites(
        db, "dev-1", symbol="600000", side="buy", qty=100, price=10,
        intent="live", asset_class="cn",
    )
    assert not gate["passed"]
    check = next(c for c in gate["checks"] if c["name"] == "tiger_configured")
    assert check["passed"] is False
    assert "Tiger OpenAPI" in check["detail"]


async def test_live_cn_with_tiger_passes(db, live_device, monkeypatch):
    async def _fake_tiger_configured(db, device_id):
        return True

    monkeypatch.setattr(trade_gate, "_tiger_configured", _fake_tiger_configured)
    gate = await trade_gate.check_prerequisites(
        db, "dev-1", symbol="600000", side="buy", qty=100, price=10,
        intent="live", asset_class="cn",
    )
    assert gate["passed"] is True


async def test_live_us_stocks_tiger_or_trove(db, live_device, monkeypatch):
    async def _fake_tiger_configured(db, device_id):
        return True

    monkeypatch.setattr(trade_gate, "_tiger_configured", _fake_tiger_configured)
    gate = await trade_gate.check_prerequisites(
        db, "dev-1", symbol="AAPL", side="buy", qty=1, price=150,
        intent="live", asset_class="us-stocks",
    )
    assert gate["passed"] is True


async def test_live_us_stocks_without_broker_blocked(db, live_device):
    gate = await trade_gate.check_prerequisites(
        db, "dev-1", symbol="AAPL", side="buy", qty=1, price=150,
        intent="live", asset_class="us-stocks",
    )
    assert not gate["passed"]
    check = next(c for c in gate["checks"] if c["name"] == "live_broker_configured")
    assert check["passed"] is False


async def test_trove_configured_pass(db):
    db.add(DeviceSettings(
        device_id="dev-1", trading_mode="live", environment_mode="live",
        trove_api_key="encrypted-key", trove_enabled=True,
    ))
    await db.commit()
    gate = await trade_gate.check_prerequisites(
        db, "dev-1", symbol="AAPL", side="buy", qty=1, price=150,
        intent="live", asset_class="stocks", broker="trove",
    )
    assert gate["passed"] is True


async def test_akshare_live_blocked(db, live_device):
    gate = await trade_gate.check_prerequisites(
        db, "dev-1", symbol="600000", side="buy", qty=100, price=10,
        intent="live", asset_class="cn", broker="akshare",
    )
    assert not gate["passed"]
    check = next(c for c in gate["checks"] if c["name"] == "akshare_live_supported")
    assert check["passed"] is False
    assert "paper trading only" in check["detail"]


async def test_memecoin_live_needs_solana_wallet(db, live_device):
    gate = await trade_gate.check_prerequisites(
        db, "dev-1", symbol="PEPE", side="buy", qty=100, price=0.01,
        intent="live", route="memecoin", asset_class="crypto",
    )
    assert not gate["passed"]
    check = next(c for c in gate["checks"] if c["name"] == "solana_wallet_configured")
    assert check["passed"] is False


async def test_memecoin_live_with_wallet_and_jupiter(db, live_device):
    db.add(DeviceCryptoCredential(
        device_id="dev-1",
        exchange="solana",
        encrypted_api_key="k",
        encrypted_api_secret="s",
        wallet_address="8xY9abcdefghijklmnop",
    ))
    live_device.jupiter_enabled = True
    await db.commit()
    gate = await trade_gate.check_prerequisites(
        db, "dev-1", symbol="PEPE", side="buy", qty=100, price=0.01,
        intent="live", route="memecoin", asset_class="crypto",
    )
    assert gate["passed"] is True


# ---------------------------------------------------------------------------
# Portfolio cash + trading caps
# ---------------------------------------------------------------------------

async def test_buy_exceeding_cash_blocked(db):
    p = Portfolio(device_id="dev-1", cash=100.0)
    db.add(p)
    await db.commit()
    await db.refresh(p)
    gate = await trade_gate.check_prerequisites(
        db, "dev-1", symbol="BTC", side="buy", qty=2, price=100,
        intent="paper", asset_class="crypto", portfolio_id=p.id,
    )
    assert not gate["passed"]
    check = next(c for c in gate["checks"] if c["name"] == "portfolio_cash")
    assert check["passed"] is False


async def test_buy_within_cash_passes(db):
    p = Portfolio(device_id="dev-1", cash=10000.0)
    db.add(p)
    await db.commit()
    await db.refresh(p)
    gate = await trade_gate.check_prerequisites(
        db, "dev-1", symbol="BTC", side="buy", qty=1, price=100,
        intent="paper", asset_class="crypto", portfolio_id=p.id,
    )
    assert gate["passed"] is True


async def test_trading_cap_blocks_large_order(db):
    p = Portfolio(device_id="dev-1", cash=10000.0)
    db.add(p)
    await db.commit()
    await db.refresh(p)
    db.add(TradingCap(portfolio_id=p.id, enabled=True, max_position_amount=500.0))
    await db.commit()
    gate = await trade_gate.check_prerequisites(
        db, "dev-1", symbol="BTC", side="buy", qty=10, price=100,
        intent="paper", asset_class="crypto", portfolio_id=p.id,
    )
    assert not gate["passed"]
    check = next(c for c in gate["checks"] if c["name"] == "trading_caps")
    assert check["passed"] is False


# ---------------------------------------------------------------------------
# Circuit breaker + describe_failures
# ---------------------------------------------------------------------------

async def test_circuit_breaker_open_blocks(db):
    from app.services.circuit_breaker import get_circuit_breaker

    cb = get_circuit_breaker()
    cb.trigger_halt("testing halt")
    try:
        gate = await trade_gate.check_prerequisites(
            db, "dev-1", symbol="BTC", side="buy", qty=1, price=100, intent="paper",
        )
        assert not gate["passed"]
        check = next(c for c in gate["checks"] if c["name"] == "circuit_breaker")
        assert check["passed"] is False
        assert "testing halt" in check["detail"]
    finally:
        cb.resume_trading()


async def test_circuit_breaker_closed_passes(db):
    from app.services.circuit_breaker import get_circuit_breaker

    cb = get_circuit_breaker()
    assert cb.can_trade()
    gate = await trade_gate.check_prerequisites(
        db, "dev-1", symbol="BTC", side="buy", qty=1, price=100, intent="paper",
    )
    assert gate["passed"] is True


def test_describe_failures_empty():
    assert trade_gate.describe_failures({"checks": []}) == ""


def test_describe_failures_joins_failures_only():
    result = {
        "checks": [
            {"name": "a", "passed": False, "detail": "bad a"},
            {"name": "b", "passed": True, "detail": "ok b"},
            {"name": "c", "passed": False, "detail": "bad c"},
        ]
    }
    text = trade_gate.describe_failures(result)
    assert "a: bad a" in text
    assert "c: bad c" in text
    assert "ok b" not in text


def test_intent_and_mode_exposed():
    assert trade_gate.PAPER == "paper"
    assert trade_gate.LIVE == "live"
