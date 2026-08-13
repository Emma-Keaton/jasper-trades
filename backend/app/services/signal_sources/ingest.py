"""Shared signal tip-ingest + hands-free auto-execution pipeline.

Used by the scheduler poller, the on-demand /signals/fetch endpoint, and the
real-time Telegram listener so every path behaves identically:

    draft(s) -> LLM extraction -> dedupe -> confidence -> SignalTip row
             -> (automatic) paper/live execution ledger on the tip

Rules baked in by design:
- Auto-exec is ON by default (hands-free) and gated by a per-device kill switch.
- Only tips at/above the device's min_confidence are traded automatically.
- Position size = max_position_pct of portfolio equity, capped by TradingCaps.
- Paper by default; Live only when trading_mode=live AND environment is live
  AND at least one non-paper broker is connected (circuit breaker enforced).
Every attempt writes a ledger entry on the tip (executed / skipped / failed).
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import DeviceSettings, Portfolio, SignalSettings, SignalTip, TradingCap
from app.services.valuation_service import ValuationService

from .confidence import compute_confidence
from .tip_extraction import TipExtractionService

logger = structlog.get_logger(__name__)

DEFAULT_MIN_CONFIDENCE = 0.60
DEFAULT_MAX_POSITION_PCT = 0.05

_CRYPTO = {
    "BTC", "ETH", "SOL", "BNB", "XRP", "ADA", "DOGE", "DOT",
    "MATIC", "LINK", "AVAX", "UNI", "ATOM", "LTC", "BCH",
    "JUP", "RAY", "ORCA", "BONK",
}


# ---------------------------------------------------------------------------
# Ingest
# ---------------------------------------------------------------------------

async def extract_and_ingest(db: AsyncSession, device_id: str, drafts: List[Any]) -> List[SignalTip]:
    """Run LLM extraction over drafts and insert new (uncommitted) tips.

    The caller is responsible for committing. Duplicates are skipped.
    """
    extractor = TipExtractionService()
    extracted = await extractor.extract_tips(
        [d.to_dict() if hasattr(d, "to_dict") else d for d in drafts]
    )
    saved: List[SignalTip] = []
    for t in extracted:
        sig = await ingest_tip_dict(db, device_id, t)
        if sig is not None:
            saved.append(sig)
    return saved


async def ingest_tip_dict(db: AsyncSession, device_id: str, tip: Dict[str, Any]) -> Optional[SignalTip]:
    """Dedupe + score one extracted tip into a new (uncommitted) SignalTip."""
    try:
        src_id = int(tip.get("source_id") or "0")
    except (TypeError, ValueError):
        return None
    if src_id == 0:
        return None

    dup = await db.execute(
        select(SignalTip.id).where(
            SignalTip.device_id == device_id,
            SignalTip.source_id == src_id,
            SignalTip.slug == (tip.get("slug") or ""),
        )
    )
    if dup.scalar_one_or_none():
        return None

    final_conf, _basis = await compute_confidence(
        tip.get("symbol") or "",
        tip.get("side") or "long",
        float(tip.get("confidence") or 0.0),
        src_id,
        db,
    )
    sig = SignalTip(
        device_id=device_id,
        source_id=src_id,
        slug=tip.get("slug") or "",
        symbol=tip.get("symbol") or "",
        side=tip.get("side") or "long",
        timeframe=tip.get("timeframe"),
        confidence=final_conf,
        rationale=tip.get("rationale"),
        text=tip.get("text"),
        url=tip.get("url"),
        source_created_at=_coerce_dt(tip.get("created_at")),
        execution_status="pending",
    )
    db.add(sig)
    await db.flush()
    return sig


# ---------------------------------------------------------------------------
# Per-device settings
# ---------------------------------------------------------------------------

async def get_signal_settings(db: AsyncSession, device_id: str) -> SignalSettings:
    res = await db.execute(select(SignalSettings).where(SignalSettings.device_id == device_id))
    row = res.scalar_one_or_none()
    if row:
        return row
    return SignalSettings(
        device_id=device_id,
        auto_execute_enabled=True,
        min_confidence=DEFAULT_MIN_CONFIDENCE,
        max_position_pct=DEFAULT_MAX_POSITION_PCT,
    )


async def save_signal_settings(
    db: AsyncSession,
    device_id: str,
    *,
    auto_execute_enabled: Optional[bool] = None,
    min_confidence: Optional[float] = None,
    max_position_pct: Optional[float] = None,
    commit: bool = True,
) -> SignalSettings:
    res = await db.execute(select(SignalSettings).where(SignalSettings.device_id == device_id))
    row = res.scalar_one_or_none()
    if row is None:
        row = SignalSettings(device_id=device_id)
        db.add(row)
    if auto_execute_enabled is not None:
        row.auto_execute_enabled = bool(auto_execute_enabled)
    if min_confidence is not None:
        row.min_confidence = max(0.0, min(1.0, float(min_confidence)))
    if max_position_pct is not None:
        row.max_position_pct = max(0.0, min(1.0, float(max_position_pct)))
    if commit:
        await db.commit()
    return row


# ---------------------------------------------------------------------------
# Execution
# ---------------------------------------------------------------------------

async def maybe_auto_execute(db: AsyncSession, device_id: str, tip: SignalTip) -> Dict[str, Any]:
    """Auto-execution entry point (kill-switch + confidence gated)."""
    if tip.execution_status == "executed":
        return {"error": "already executed"}
    s = await get_signal_settings(db, device_id)
    if not s.auto_execute_enabled:
        _mark(tip, "skipped", "auto-execution is disabled")
        return {"skipped": "disabled"}
    if (tip.confidence or 0.0) < s.min_confidence:
        _mark(tip, "skipped", f"below {s.min_confidence:.0%} minimum confidence")
        return {"skipped": "low_confidence"}
    return await execute_signal(db, device_id, tip)


async def execute_signal(db: AsyncSession, device_id: str, tip: SignalTip) -> Dict[str, Any]:
    """Place the order for a tip (paper by default, live when eligible)."""
    if tip.execution_status == "executed":
        return {"error": "already executed"}

    portfolio = await _get_portfolio(db, device_id)
    if portfolio is None:
        _mark(tip, "skipped", "no portfolio configured")
        await db.commit()
        return {"error": "no portfolio"}

    equity = float(portfolio.cash or 0.0)
    if equity <= 0:
        _mark(tip, "skipped", "portfolio has zero cash")
        await db.commit()
        return {"error": "zero cash"}

    s = await get_signal_settings(db, device_id)
    notional = equity * s.max_position_pct
    notional = await _apply_caps(db, portfolio.id, equity, notional)
    if notional <= 0:
        _mark(tip, "skipped", "position budget is zero after caps")
        await db.commit()
        return {"error": "zero budget"}

    price = await ValuationService().get_price(tip.symbol)
    if not price or price <= 0:
        _mark(tip, "skipped", f"no market price for {tip.symbol}")
        await db.commit()
        return {"error": f"no price for {tip.symbol}"}

    qty = notional / price
    side = "buy" if (tip.side or "long").lower() == "long" else "sell"
    asset_class = _asset_class(tip.symbol)

    if not await _is_live(db, device_id):
        return await _execute_paper(db, device_id, tip, side, qty, price, notional)
    return await _execute_live(db, device_id, tip, portfolio.id, side, qty, price)


async def _execute_paper(
    db: AsyncSession, device_id: str, tip: SignalTip, side: str, qty: float, price: float, notional: float
) -> Dict[str, Any]:
    from app.services.paper_trading_service import get_paper_trading_service

    asset_class = "crypto" if _asset_class(tip.symbol) == "crypto" else "stocks"
    result = await get_paper_trading_service().place_trade(
        device_id=device_id,
        symbol=tip.symbol,
        side=side,
        qty=qty,
        price=price,
        asset_class=asset_class,
        agent_name="signal-auto",
        reasoning=(tip.rationale or (tip.text or ""))[:300],
    )
    if result.get("error"):
        _mark(tip, "failed", f"paper trade rejected: {result['error']}")
        await db.commit()
        return {"error": result["error"]}

    tip.executed = True
    tip.entry_price = float(result.get("price", price))
    tip.execution_status = "executed"
    tip.execution_detail = (
        f"Paper {side.upper()} {result.get('quantity', qty):g} {tip.symbol} @ "
        f"{result.get('price', price):g} (notional {notional:.2f})"
    )
    tip.executed_at = datetime.utcnow()
    await db.commit()
    return {"success": True, "mode": "paper", "symbol": tip.symbol, "side": side, "quantity": qty, "price": price}


async def _execute_live(
    db: AsyncSession, device_id: str, tip: SignalTip, portfolio_id: int, side: str, qty: float, price: float
) -> Dict[str, Any]:
    from app.agents import agent_registry
    from app.services.circuit_breaker import get_circuit_breaker
    from app.services.portfolio_service import PortfolioService

    circuit = get_circuit_breaker()
    if not circuit.can_trade():
        _mark(tip, "skipped", f"circuit breaker open: {circuit.trigger_reason}")
        await db.commit()
        return {"error": "circuit breaker open"}

    execution_agent = agent_registry.get("execution")
    if execution_agent is None:
        _mark(tip, "failed", "execution agent unavailable")
        await db.commit()
        return {"error": "execution agent unavailable"}
    if not getattr(execution_agent, "_brokers_initialized", False):
        await execution_agent.initialize_brokers()

    trade = await execution_agent.create_order(symbol=tip.symbol, side=side, quantity=qty, order_type="market")
    trade = await execution_agent.submit_to_broker(trade)
    if trade.status != "submitted":
        _mark(tip, "failed", f"live order rejected by broker (status={trade.status})")
        await db.commit()
        return {"error": "live order rejected"}

    ps = PortfolioService(db)
    fill_price = trade.price or price
    if side == "buy":
        await ps.add_position(portfolio_id, symbol=tip.symbol, quantity=qty, price=fill_price)
        cost = qty * fill_price
        if cost > 0:
            await ps.update_cash(portfolio_id, amount=-cost, description=f"Auto-trade buy {tip.symbol}")
    else:
        await ps.reduce_position(portfolio_id, symbol=tip.symbol, quantity=qty, price=fill_price)

    db.add(trade)
    await db.commit()

    tip.executed = True
    tip.entry_price = fill_price
    tip.execution_status = "executed"
    tip.execution_detail = f"Live {side.upper()} {qty:g} {tip.symbol} via {trade.broker}"
    tip.executed_at = datetime.utcnow()
    await db.commit()
    return {"success": True, "mode": "live", "symbol": tip.symbol, "side": side, "quantity": qty, "price": fill_price}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mark(tip: SignalTip, status: str, detail: str) -> None:
    tip.execution_status = status
    tip.execution_detail = detail
    if status == "executed":
        tip.executed = True
        tip.executed_at = datetime.utcnow()


async def _get_portfolio(db: AsyncSession, device_id: str) -> Optional[Portfolio]:
    rows = (await db.execute(select(Portfolio))).scalars().all()
    if not rows:
        return None
    return next((p for p in rows if (p.device_id or "") == device_id), rows[0])


async def _apply_caps(db: AsyncSession, portfolio_id: int, equity: float, notional: float) -> float:
    res = await db.execute(
        select(TradingCap).where(TradingCap.portfolio_id == portfolio_id, TradingCap.enabled == True)  # noqa: E712
    )
    caps = res.scalar_one_or_none()
    if caps is None:
        return notional
    out = notional
    if caps.max_position_amount:
        out = min(out, float(caps.max_position_amount))
    if caps.max_position_percentage:
        out = min(out, equity * (float(caps.max_position_percentage) / 100.0))
    return out


async def _is_live(db: AsyncSession, device_id: str) -> bool:
    res = await db.execute(select(DeviceSettings).where(DeviceSettings.device_id == device_id))
    ds = res.scalar_one_or_none()
    if ds is None:
        return False
    mode = (ds.trading_mode or "practice").lower()
    env = (ds.environment_mode or "sandbox").lower()
    if mode != "live" or env != "live":
        return False
    try:
        from app.brokers import broker_registry
    except Exception:  # noqa: BLE001
        return False
    stats = broker_registry.get_stats()
    return any(
        (info.get("connected") and not info.get("paper_trading")) for info in stats.values()
    )


def _asset_class(symbol: str) -> str:
    sym = (symbol or "").upper()
    if sym in _CRYPTO:
        return "crypto"
    if 2 <= len(sym) <= 5 and sym.isalpha():
        return "stocks"
    return "crypto"


def _coerce_dt(value: Any) -> Optional[datetime]:
    if isinstance(value, datetime):
        return value
    if isinstance(value, (int, float)):
        try:
            return datetime.utcfromtimestamp(value)
        except Exception:  # noqa: BLE001
            return None
    return None