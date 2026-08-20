"""Tests for the factor-trading results API (watched + traded ledger)."""
from datetime import datetime, timedelta

import pytest
from sqlalchemy import select

from app.models import SignalSource, SignalTip, WatchlistItem
from app.services import factor_trading as ft


@pytest.mark.asyncio
async def test_signals_endpoint_empty(db, app_client):
    res = await app_client.get("/api/v1/factor-trading/signals", headers={"X-Device-ID": "dev-1"})
    assert res.status_code == 200
    data = res.json()
    assert data["signals"] == []
    assert data["traded"] == []
    assert data["watching"] == []
    assert data["counts"]["traded"] == 0


@pytest.mark.asyncio
async def test_signals_endpoint_reports_watched_and_traded(db, app_client):
    await ft._ensure_factor_source(db, "dev-1")
    src = (await db.execute(select(SignalSource).where(SignalSource.device_id == "dev-1"))).scalars().one()
    db.add(WatchlistItem(device_id="dev-1", symbol="BTC", asset_class="crypto", source="coingecko"))
    db.add(WatchlistItem(device_id="dev-1", symbol="ETH", asset_class="crypto", source="coingecko"))
    db.add(
        SignalTip(
            device_id="dev-1", source_id=src.id, slug="BTC-long", symbol="BTC", side="long",
            confidence=0.82, rationale="Momentum consensus, strong z-score.",
            execution_status="executed", executed=True, entry_price=60000.0,
            created_at=datetime.utcnow() - timedelta(hours=1),
        )
    )
    db.add(
        SignalTip(
            device_id="dev-1", source_id=src.id, slug="ETH-long", symbol="ETH", side="long",
            confidence=0.64, rationale="Mixed factor consensus.",
            execution_status="pending", executed=False,
            created_at=datetime.utcnow() - timedelta(minutes=30),
        )
    )
    await db.commit()

    res = await app_client.get("/api/v1/factor-trading/signals", headers={"X-Device-ID": "dev-1"})
    assert res.status_code == 200
    data = res.json()
    assert data["counts"]["traded"] == 1
    assert len(data["signals"]) == 2
    assert len(data["watching"]) == 2
    by_symbol = {w["symbol"]: w for w in data["watching"]}
    assert by_symbol["BTC"]["last_signal"] == "long"
    assert by_symbol["BTC"]["last_status"] == "executed"
    assert by_symbol["ETH"]["last_status"] == "pending"
    assert by_symbol["ETH"]["last_signal"] == "long"


@pytest.mark.asyncio
async def test_stats_endpoint_counts(db, app_client):
    await ft._ensure_factor_source(db, "dev-1")
    src = (await db.execute(select(SignalSource).where(SignalSource.device_id == "dev-1"))).scalars().one()
    db.add(WatchlistItem(device_id="dev-1", symbol="BTC", asset_class="crypto"))
    for i, side in enumerate(["long", "short", "long"]):
        db.add(
            SignalTip(
                device_id="dev-1", source_id=src.id, slug=f"SYM-{i}", symbol="BTC", side=side,
                confidence=0.8, execution_status="executed", executed=True,
            )
        )
    await db.commit()

    res = await app_client.get("/api/v1/factor-trading/stats", headers={"X-Device-ID": "dev-1"})
    assert res.status_code == 200
    data = res.json()
    assert data["trades_taken"] == 3
    assert data["watching"] == 1