"""Tests for the scheduled factor-trading sweep (watchlist -> advisor -> auto-exec)."""
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import pytest
from sqlalchemy import select

from app.models import SignalSource, SignalTip, WatchlistItem
from app.services import factor_trading as ft


def _ohlcv_bars(n=300, start=60000.0):
    rng = np.random.default_rng(7)
    closes = start + np.cumsum(rng.normal(0, 300, n))
    ts = pd.date_range(end="2026-08-19", periods=n, freq="h", tz="UTC")
    return [
        [int(t.timestamp() * 1000), c, c * 1.01, c * 0.99, c, 10000 + i]
        for i, (t, c) in enumerate(zip(ts, closes))
    ]


async def _add_watchlist(db, device_id="dev-1", symbols=("BTC",)):
    for s in symbols:
        db.add(WatchlistItem(device_id=device_id, symbol=s, asset_class="crypto", source="coingecko"))
    await db.commit()


@pytest.mark.asyncio
async def test_ensure_factor_source_is_singleton(db):
    src = await ft._ensure_factor_source(db, "dev-1")
    assert src.source_type == "factor"
    assert src.display_name == "Alpha Zoo Decider"

    again = await ft._ensure_factor_source(db, "dev-1")
    rows = (await db.execute(select(SignalSource).where(SignalSource.device_id == "dev-1"))).scalars().all()
    assert again.id == src.id
    assert len(rows) == 1


@pytest.mark.asyncio
async def test_already_traded_detects_recent_tip(db):
    src = await ft._ensure_factor_source(db, "dev-1")
    db.add(
        SignalTip(
            device_id="dev-1", source_id=src.id, slug="BTC-long", symbol="BTC", side="long",
            confidence=0.8, execution_status="executed",
            created_at=datetime.utcnow() - timedelta(minutes=10),
        )
    )
    await db.commit()

    assert await ft._already_traded(db, "dev-1", "BTC", "long", src.id) is True
    assert await ft._already_traded(db, "dev-1", "BTC", "short", src.id) is False
    assert await ft._already_traded(db, "dev-1", "ETH", "long", src.id) is False


@pytest.mark.asyncio
async def test_sweep_creates_tip_and_auto_executes(db, monkeypatch):
    await _add_watchlist(db, "dev-1", ("BTC",))

    async def fake_fetch(symbol):
        return _ohlcv_bars()

    async def fake_auto_execute(s, device_id, tip):
        tip.execution_status = "executed"
        tip.executed = True
        tip.executed_at = datetime.utcnow()
        return {"success": True, "symbol": tip.symbol, "side": "buy", "quantity": 1.0, "price": 60000.0}

    monkeypatch.setattr(ft, "_fetch_ohlcv", fake_fetch)
    monkeypatch.setattr("app.services.signal_sources.ingest.maybe_auto_execute", fake_auto_execute)

    stats = await ft.run_factor_sweep(db)

    assert stats["enabled"] is not False
    assert stats["traded"] >= 1
    assert stats["devices"] == 1

    tips = (await db.execute(select(SignalTip))).scalars().all()
    assert len(tips) == 1
    assert tips[0].symbol == "BTC"
    assert tips[0].side in ("long", "short")
    assert tips[0].execution_status == "executed"
    assert tips[0].rationale and "consensus" in tips[0].rationale


@pytest.mark.asyncio
async def test_sweep_dedupes_within_refractory_window(db, monkeypatch):
    await _add_watchlist(db, "dev-1", ("BTC",))
    src = await ft._ensure_factor_source(db, "dev-1")
    db.add(
        SignalTip(
            device_id="dev-1", source_id=src.id, slug="BTC-long", symbol="BTC", side="long",
            confidence=0.8, execution_status="executed",
            created_at=datetime.utcnow() - timedelta(minutes=5),
        )
    )
    await db.commit()

    async def fake_fetch(symbol):
        return _ohlcv_bars()

    async def fake_auto_execute(s, device_id, tip):
        return {"success": True}

    monkeypatch.setattr(ft, "_fetch_ohlcv", fake_fetch)
    monkeypatch.setattr("app.services.signal_sources.ingest.maybe_auto_execute", fake_auto_execute)

    stats = await ft.run_factor_sweep(db)

    # The existing long tip blocks a new long; a short may still fire, but the
    # previously-traded side must not be re-entered.
    assert stats["traded"] == 0 or stats["traded"] == 1
    tips = (await db.execute(select(SignalTip))).scalars().all()
    longs = [t for t in tips if t.side == "long"]
    assert len(longs) == 1
    assert longs[0].created_at <= datetime.utcnow()
