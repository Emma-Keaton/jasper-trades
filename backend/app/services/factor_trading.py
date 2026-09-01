"""
Factor Trading Service - scheduled, hands-free alpha-zoo driven trading.

Runs on the scheduler's signal-generation tick. For every device with a
watchlist AND agents_started=true, it fetches live OHLCV, asks the factor
advisor which way the winning factor consensus leans, and when the strategy
confidence is high enough it feeds the decision into the same ledger + trade
gate used by signal sources, so paper/live execution, position caps and the
circuit breaker all apply.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import structlog
from sqlalchemy import select

from app.config import settings
from app.models import DeviceSettings, SignalSource, SignalTip, WatchlistItem

logger = structlog.get_logger(__name__)

_SOURCE_TYPE = "factor"


# ---------------------------------------------------------------------------
# OHLCV -> panel
# ---------------------------------------------------------------------------

def _build_panel(ohlcv: List[List[float]]) -> Dict[str, Any]:
    """Convert CCXT-style OHLCV rows to a wide panel dict for factor compute."""
    import pandas as pd

    ts = pd.to_datetime([int(r[0]) for r in ohlcv], unit="ms")
    idx = pd.DatetimeIndex(ts, name="date")
    cols = {"open": [], "high": [], "low": [], "close": [], "volume": []}
    for r in ohlcv:
        for k, i in zip(cols, (1, 2, 3, 4, 5)):
            cols[k].append(float(r[i]))
    if not cols["close"]:
        return {}
    return {k: pd.DataFrame({1: v}, index=idx) for k, v in cols.items()}


async def _fetch_ohlcv(symbol: str) -> Optional[List[List[float]]]:
    """Fetch hourly OHLCV via CCXT (crypto) with a yfinance fallback (stocks)."""
    symbol = (symbol or "").upper()
    try:
        from app.services.ccxt_market_data_service import get_ccxt_market_data_service

        try:
            return await get_ccxt_market_data_service().get_ohlcv(
                symbol, timeframe=settings.FACTOR_TIMEFRAME, limit=settings.FACTOR_LIMIT_BARS
            )
        except Exception:  # noqa: BLE001
            logger.debug("factor_ohlcv_ccxt_failed", symbol=symbol)

        from app.services.data_connectors import data_connector_service

        hist = await data_connector_service.get_yfinance_data(symbol, interval="1d", range_="6mo")
        if hist:
            import pandas as pd

            return [
                [int(pd.Timestamp(r["timestamp"]).timestamp() * 1000), r["open"], r["high"], r["low"], r["close"], r["volume"]]
                for r in hist
            ]
    except Exception:  # noqa: BLE001
        logger.debug("factor_ohlcv_fetch_failed", symbol=symbol)
    return None


# ---------------------------------------------------------------------------
# Synthetic source + dedupe
# ---------------------------------------------------------------------------

async def _ensure_factor_source(db, device_id: str) -> Optional[SignalSource]:
    """Return (creating if needed) the per-device factor signal source."""
    res = await db.execute(
        select(SignalSource).where(
            SignalSource.device_id == device_id,
            SignalSource.source_type == _SOURCE_TYPE,
        )
    )
    src: Optional[SignalSource] = res.scalar_one_or_none()
    if src is not None:
        return src
    src = SignalSource(
        device_id=device_id,
        source_type=_SOURCE_TYPE,
        config={},
        display_name="Alpha Zoo Decider",
        is_active=True,
        fetch_interval_minutes=settings.FACTOR_SWEEP_INTERVAL // 60 if settings.FACTOR_SWEEP_INTERVAL >= 60 else 5,
    )
    db.add(src)
    await db.flush()
    return src


async def _already_traded(
    db, device_id: str, symbol: str, side: str, source_id: int
) -> bool:
    """True when the same device/symbol/side was traded within the refractory window."""
    cutoff = datetime.utcnow() - timedelta(minutes=settings.FACTOR_REFRACTORY_MINUTES)
    res = await db.execute(
        select(SignalTip.id).where(
            SignalTip.device_id == device_id,
            SignalTip.source_id == source_id,
            SignalTip.symbol == symbol,
            SignalTip.side == side,
            SignalTip.created_at >= cutoff,
        )
    )
    return res.scalar_one_or_none() is not None


async def _is_agents_started(db, device_id: str) -> bool:
    """True when the user has clicked Start on the dashboard for this device."""
    try:
        res = await db.execute(
            select(DeviceSettings).where(DeviceSettings.device_id == device_id)
        )
        row = res.scalar_one_or_none()
        if not row or not row.preferences:
            return False
        prefs = json.loads(row.preferences)
        return bool(prefs.get("agents_started", False))
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Sweep
# ---------------------------------------------------------------------------

async def run_factor_sweep(db) -> Dict[str, Any]:
    """Evaluate every watchlist symbol across devices; auto-execute strong calls.

    The advisor picks the winning factor consensus; only non-neutral, high
    enough confidence calls produce a SignalTip routed through
    ``maybe_auto_execute`` (paper by default, gate + caps enforced).
    """
    if not settings.FACTOR_TRADING_ENABLED:
        return {"enabled": False, "traded": 0}

    from app.services.alpha_factor_service import AlphaFactorService
    from app.services.signal_sources.ingest import get_signal_settings, maybe_auto_execute

    factor_service = AlphaFactorService(db)
    stats = {"enabled": True, "devices": 0, "symbols": 0, "traded": 0, "skipped": 0, "details": []}

    # Group watchlist symbols by device.
    rows = (await db.execute(select(WatchlistItem))).scalars().all()
    by_device: Dict[str, List[WatchlistItem]] = {}
    for item in rows:
        by_device.setdefault(item.device_id, []).append(item)

    for device_id, items in by_device.items():
        source = await _ensure_factor_source(db, device_id)
        if source is None:
            continue
        stats["devices"] += 1

        # Skip devices whose agents haven't been started
        if not await _is_agents_started(db, device_id):
            stats["skipped"] += len(items)
            continue

        s = await get_signal_settings(db, device_id)
        if not s.auto_execute_enabled:
            stats["skipped"] += len(items)
            continue

        for item in items:
            symbol = (item.symbol or "").strip().upper()
            if not symbol:
                continue
            stats["symbols"] += 1
            try:
                ohlcv = await _fetch_ohlcv(symbol)
                if not ohlcv or len(ohlcv) < 2:
                    stats["skipped"] += 1
                    continue
                panel = _build_panel(ohlcv)
                advise = await factor_service.advise_for_trade(
                    symbol=symbol,
                    panel=panel,
                    side="auto",
                    top=10,
                )
                strategy = advise.get("strategy") or {}
                direction = advise.get("recommended_direction")
                confidence = float(strategy.get("confidence") or 0.0)
                if not direction or direction == "neutral" or confidence < s.min_confidence:
                    stats["skipped"] += 1
                    continue

                side = "long" if direction == "long" else "short"
                if await _already_traded(db, device_id, symbol, side, source.id):
                    stats["skipped"] += 1
                    continue

                tip = SignalTip(
                    device_id=device_id,
                    source_id=source.id,
                    slug=f"{symbol}-{side.lower()}",
                    symbol=symbol,
                    side=side,
                    timeframe=settings.FACTOR_TIMEFRAME,
                    confidence=confidence,
                    rationale=(
                        f"Factor consensus: {strategy.get('theme', 'mixed')} "
                        f"(net signal {strategy.get('net_signal')}, confidence {confidence:.0%})"
                    ),
                    text=f"{side.upper()} {symbol} on {strategy.get('theme', 'mixed')} factor consensus.",
                    execution_status="pending",
                )
                db.add(tip)
                await db.flush()

                result = await maybe_auto_execute(db, device_id, tip)
                status = result.get("success") or result.get("error") or result.get("skipped")
                stats["details"].append({"symbol": symbol, "side": side, "confidence": round(confidence, 3), "result": status})
                if result.get("success") or result.get("executed"):
                    stats["traded"] += 1
                else:
                    stats["skipped"] += 1
                await db.commit()
            except Exception as exc:  # noqa: BLE001
                logger.warning("factor sweep symbol failed", device=device_id, symbol=symbol, error=str(exc))
                stats["skipped"] += 1

    if stats["traded"] or stats["details"]:
        await db.commit()
        logger.info(
            "factor sweep complete",
            devices=stats["devices"],
            symbols=stats["symbols"],
            traded=stats["traded"],
            skipped=stats["skipped"],
        )
    return stats