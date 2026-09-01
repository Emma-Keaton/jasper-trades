"""Signal pipeline: dedupe, confidence, auto-exec, execute_signal routing."""
import pytest

from app.models import DeviceSettings, Portfolio
from app.services.signal_sources import ingest


@pytest.fixture
def fake_confidence(monkeypatch):
    """Replace Kronos/LLM compute_confidence with a deterministic passthrough."""
    async def _fake(symbol, side, confidence, src_id, db):
        return float(confidence), {"model": "test", "score": float(confidence)}

    monkeypatch.setattr(ingest, "compute_confidence", _fake)
    monkeypatch.setattr("app.services.signal_sources.confidence.compute_confidence", _fake)


@pytest.fixture
def fake_price(monkeypatch):
    from app.services.valuation_service import ValuationService

    async def _fake(self, symbol):
        return 10.0

    monkeypatch.setattr(ValuationService, "get_price", _fake)


def _tip_dict(source_id, slug="btc-long", symbol="BTC", side="long", confidence=0.9, **kw):
    return {
        "source_id": source_id,
        "slug": slug,
        "symbol": symbol,
        "side": side,
        "confidence": confidence,
        "text": "signal text",
        "rationale": "test rationale",
        **kw,
    }


# ---------------------------------------------------------------------------
# Ingest + dedupe
# ---------------------------------------------------------------------------

async def test_ingest_creates_tip(db, fake_confidence):
    tip = await ingest.ingest_tip_dict(db, "dev-1", _tip_dict(1001))
    assert tip is not None
    assert tip.device_id == "dev-1"
    assert tip.symbol == "BTC"
    assert tip.side == "long"
    assert tip.confidence == 0.9
    assert tip.execution_status == "pending"


async def test_ingest_dedupes_identical_tips(db, fake_confidence):
    first = await ingest.ingest_tip_dict(db, "dev-1", _tip_dict(1002))
    second = await ingest.ingest_tip_dict(db, "dev-1", _tip_dict(1002))
    assert first is not None
    assert second is None


async def test_ingest_allows_same_source_different_slug(db, fake_confidence):
    first = await ingest.ingest_tip_dict(db, "dev-1", _tip_dict(1003))
    second = await ingest.ingest_tip_dict(db, "dev-1", _tip_dict(1003, slug="btc-short", side="short"))
    assert first is not None
    assert second is not None


async def test_ingest_rejects_zero_source(db):
    tip = await ingest.ingest_tip_dict(db, "dev-1", _tip_dict(0))
    assert tip is None


# ---------------------------------------------------------------------------
# maybe_auto_execute gating
# ---------------------------------------------------------------------------

async def test_auto_execute_disabled_skips(db, fake_confidence):
    tip = await ingest.ingest_tip_dict(db, "dev-1", _tip_dict(2001))
    await ingest.save_signal_settings(db, "dev-1", auto_execute_enabled=False)
    result = await ingest.maybe_auto_execute(db, "dev-1", tip)
    assert result == {"skipped": "disabled"}
    assert tip.execution_status == "skipped"


async def test_auto_execute_low_confidence_skips(db, fake_confidence):
    tip = await ingest.ingest_tip_dict(db, "dev-1", _tip_dict(2002, confidence=0.3))
    result = await ingest.maybe_auto_execute(db, "dev-1", tip)
    assert result == {"skipped": "low_confidence"}
    assert tip.execution_status == "skipped"


async def test_auto_execute_already_executed(db, fake_confidence):
    tip = await ingest.ingest_tip_dict(db, "dev-1", _tip_dict(2003))
    tip.execution_status = "executed"
    result = await ingest.maybe_auto_execute(db, "dev-1", tip)
    assert result == {"error": "already executed"}


# ---------------------------------------------------------------------------
# execute_signal
# ---------------------------------------------------------------------------

async def test_execute_signal_no_portfolio(db, fake_confidence):
    tip = await ingest.ingest_tip_dict(db, "dev-1", _tip_dict(3001))
    result = await ingest.execute_signal(db, "dev-1", tip)
    assert result == {"error": "no portfolio"}
    assert tip.execution_status == "skipped"


async def test_execute_signal_paper_success(db, fake_confidence, fake_price):
    db.add(DeviceSettings(device_id="dev-1"))
    db.add(Portfolio(device_id="dev-1", cash=10000.0))
    await db.commit()
    tip = await ingest.ingest_tip_dict(db, "dev-1", _tip_dict(3002))
    # Commit the tip so the paper engine's own DB session (same shared pool
    # connection under the test StaticPool) does not clobber a pending flush.
    await db.commit()
    await db.refresh(tip)
    result = await ingest.execute_signal(db, "dev-1", tip)
    assert result["success"] is True
    assert result["mode"] == "paper"
    assert tip.execution_status == "executed"
    assert tip.entry_price == 10.0


async def test_execute_signal_paper_budget_from_caps(db, fake_confidence, fake_price):
    from app.models import TradingCap

    db.add(DeviceSettings(device_id="dev-1"))
    p = Portfolio(device_id="dev-1", cash=10000.0)
    db.add(p)
    await db.commit()
    await db.refresh(p)
    db.add(TradingCap(portfolio_id=p.id, enabled=True, max_position_amount=100.0))
    await db.commit()

    tip = await ingest.ingest_tip_dict(db, "dev-1", _tip_dict(3003))
    await db.commit()
    await db.refresh(tip)
    result = await ingest.execute_signal(db, "dev-1", tip)
    assert result["success"] is True
    assert result["quantity"] == 10.0  # 100 budget / 10 price


async def test_execute_signal_live_cn_blocked_without_tiger(db, fake_confidence, fake_price):
    db.add(DeviceSettings(device_id="dev-1", trading_mode="live", environment_mode="live"))
    db.add(Portfolio(device_id="dev-1", cash=10000.0))
    await db.commit()
    tip = await ingest.ingest_tip_dict(db, "dev-1", _tip_dict(3004, symbol="600000", slug="cn-long"))
    result = await ingest.execute_signal(db, "dev-1", tip)
    assert "error" in result
    assert "Tiger OpenAPI" in result["error"]
    assert tip.execution_status == "skipped"


async def test_execute_signal_live_us_via_tiger(db, fake_confidence, fake_price, monkeypatch):
    from app.services import trade_gate

    db.add(DeviceSettings(device_id="dev-1", trading_mode="live", environment_mode="live"))
    db.add(Portfolio(device_id="dev-1", cash=10000.0))
    await db.commit()

    async def _tiger_ready(db_, device_id_):
        return True

    async def _fake_tiger_order(db_, device_id_, symbol, side, quantity, order_type, asset_class, limit_price=None):
        return {
            "success": True, "order_id": "tid-1", "filled_quantity": quantity,
            "filled_price": 10.0, "message": "filled", "symbol": symbol,
        }

    monkeypatch.setattr(ingest, "_tiger_ready", _tiger_ready)
    monkeypatch.setattr("app.brokers.tiger_service.place_tiger_live_order", _fake_tiger_order)
    monkeypatch.setattr(trade_gate, "_tiger_configured", _tiger_ready)

    tip = await ingest.ingest_tip_dict(db, "dev-1", _tip_dict(3005, symbol="AAPL", slug="aapl-long"))
    result = await ingest.execute_signal(db, "dev-1", tip)
    assert result["success"] is True
    assert result["mode"] == "live"
    assert result["broker"] == "tiger"
    assert tip.execution_status == "executed"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def test_asset_class_detection():
    assert ingest._asset_class("BTC") == "crypto"
    assert ingest._asset_class("SOL") == "crypto"
    assert ingest._asset_class("600000") == "cn"
    assert ingest._asset_class("000001") == "cn"
    assert ingest._asset_class("AAPL") == "stocks"


def test_tip_mark_executed():
    from datetime import datetime

    from app.models import SignalTip

    tip = SignalTip(device_id="dev-1", source_id=1, slug="x", symbol="BTC")
    ingest._mark(tip, "executed", "done")
    assert tip.executed is True
    assert tip.execution_status == "executed"
    assert isinstance(tip.executed_at, datetime)
