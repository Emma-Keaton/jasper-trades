"""
Unified trade-execution gate: paper/live routing + prerequisite checks.

Single source of truth for *every* execution route (`/trading/execute`,
`/paper/trade`, signal auto-execution, `/trove/order`, `/akshare/order`,
`/memecoin/trade`). A route decides what it INTENDS to do (paper or live),
calls `resolve_mode` to see what the device is configured for, then
`check_prerequisites` returns the list of passed/failed checks with reasons.

Rules shared by ingestion code:
- Paper by default; Live only when trading_mode=live AND environment_mode=live.
- Live additionally requires a connected non-paper broker (except routes with
  their own live config: trove key, akshare paper-only, solana wallet).
- Circuit breaker, caps, quantity/price sanity are enforced everywhere.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import DeviceSettings, Portfolio, TradingCap, Trade
from app.models_ext.crypto_credentials import DeviceCryptoCredential

logger = structlog.get_logger(__name__)

PAPER = "paper"
LIVE = "live"


# ---------------------------------------------------------------------------
# Mode resolution
# ---------------------------------------------------------------------------

async def resolve_mode(db: AsyncSession, device_id: str) -> str:
    """Return 'paper' or 'live' based on the device's persisted config."""
    res = await db.execute(select(DeviceSettings).where(DeviceSettings.device_id == device_id))
    ds = res.scalar_one_or_none()
    if ds is None:
        return PAPER
    mode = (ds.trading_mode or "practice").lower()
    env = (ds.environment_mode or "sandbox").lower()
    if mode != "live" or env != "live":
        return PAPER
    return LIVE


async def get_device_settings(db: AsyncSession, device_id: str) -> Optional[DeviceSettings]:
    res = await db.execute(select(DeviceSettings).where(DeviceSettings.device_id == device_id))
    return res.scalar_one_or_none()


async def broker_live_connected() -> bool:
    """True if at least one non-paper broker is connected."""
    try:
        from app.brokers import broker_registry
    except Exception:  # noqa: BLE001
        return False
    try:
        stats = broker_registry.get_stats()
    except Exception:  # noqa: BLE001
        return False
    return any(
        (info.get("connected") and not info.get("paper_trading")) for info in stats.values()
    )


async def solana_wallet_configured(db: AsyncSession, device_id: str) -> bool:
    """Live memecoin requires a stored Solana wallet address."""
    res = await db.execute(
        select(DeviceCryptoCredential).where(
            DeviceCryptoCredential.device_id == device_id,
            DeviceCryptoCredential.exchange == "solana",
            DeviceCryptoCredential.wallet_address.isnot(None),
        )
    )
    return res.scalar_one_or_none() is not None


# ---------------------------------------------------------------------------
# Prerequisites
# ---------------------------------------------------------------------------

def _add(checks: List[Dict[str, Any]], name: str, passed: bool, detail: str) -> None:
    checks.append({"name": name, "passed": bool(passed), "detail": detail})


async def check_prerequisites(
    db: AsyncSession,
    device_id: str,
    *,
    symbol: str,
    side: str,
    qty: float,
    price: float,
    intent: str,
    asset_class: str = "crypto",
    broker: Optional[str] = None,
    portfolio_id: Optional[int] = None,
    mode: Optional[str] = None,
    route: str = "execute",
) -> Dict[str, Any]:
    """
    Evaluate all prerequisites ahead of placing an order.

    `intent` is what the route *wants* to do (paper | live). `mode` is what the
    device is actually configured for (resolved if not given). Broker-specific
    gates apply for live routes (trove/akshare/solana).
    """
    checks: List[Dict[str, Any]] = []
    mode = mode or await resolve_mode(db, device_id)

    side = (side or "").lower()
    try:
        qty = float(qty or 0)
        price = float(price or 0)
    except (TypeError, ValueError):
        qty, price = 0.0, 0.0

    # 1. Circuit breaker (global kill switch)
    circuit = None
    try:
        from app.services.circuit_breaker import get_circuit_breaker

        circuit = get_circuit_breaker()
    except Exception:  # noqa: BLE001
        circuit = None
    if circuit is not None:
        _add(
            checks,
            "circuit_breaker",
            circuit.can_trade(),
            circuit.trigger_reason or "closed",
        )
    else:
        _add(checks, "circuit_breaker", True, "circuit breaker unavailable - proceeding optimistically")

    # 2. Order sanity
    _add(checks, "valid_side", side in ("buy", "sell"), "side must be buy or sell")
    _add(checks, "valid_quantity", qty > 0, "quantity must be positive")
    _add(checks, "valid_price", price > 0, "price must be positive")

    # 3. Live eligibility (live intent requires a live-configured device)
    if intent == LIVE:
        _add(
            checks,
            "live_enabled",
            mode == LIVE,
            "live trading requires trading_mode=live and environment_mode=live",
        )
        if mode == LIVE:
            if broker in ("tiger",) or route in ("tiger",):
                _add(checks, "tiger_configured", await _tiger_configured(db, device_id),
                     "Tiger OpenAPI credentials (tiger_id + api key + private key) required for live orders")
            elif broker == "trove":
                _add(checks, "trove_configured", await _trove_configured(db, device_id),
                     "trove_api_key + trove_enabled required for live stock orders")
            elif broker == "akshare":
                _add(checks, "akshare_live_supported", False,
                     "AKShare supports paper trading only (no live execution)")
            elif broker == "solana" or route == "memecoin":
                _add(checks, "solana_wallet_configured", await solana_wallet_configured(db, device_id),
                     "a Solana wallet address must be stored in device crypto credentials")
                _add(checks, "jupiter_enabled", await _jupiter_enabled(db, device_id),
                     "jupiter_enabled must be true in device settings")
            elif asset_class in ("cn", "chinese", "chinese-stocks"):
                tiger_ok = await _tiger_configured(db, device_id)
                _add(checks, "tiger_configured", tiger_ok,
                     "Tiger OpenAPI credentials required for live Chinese stock trading "
                     "(AKShare is paper-only)")
            elif asset_class in ("stocks", "equities", "us-stocks"):
                # Tiger preferred for US live; falls back to Trove.
                tiger_ok = await _tiger_configured(db, device_id)
                trove_ok = await _trove_configured(db, device_id)
                _add(checks, "live_broker_configured", tiger_ok or trove_ok,
                     "connect a funded broker (Tiger or Trove) for live stock trading")
            else:
                _add(checks, "live_broker_connected", await broker_live_connected(),
                     "no connected non-paper broker")
    else:
        _add(checks, "paper_enabled", bool(settings.UNIVERSAL_PAPER_TRADING),
             "universal paper trading is disabled")

    # 4. Trading caps (TradingCaps row, if any)
    cap_error = await _check_caps(db, portfolio_id, qty, price, side, asset_class)
    if cap_error:
        _add(checks, "trading_caps", False, cap_error)

    # 5. Portfolio cash guard for buy orders (paper portfolio-modeled paths)
    if side == "buy" and portfolio_id is not None:
        cash_ok, detail = await _has_cash(db, portfolio_id, price, qty, asset_class)
        _add(checks, "portfolio_cash", cash_ok, detail)

    return {
        "passed": all(c["passed"] for c in checks),
        "mode": mode,
        "intent": intent,
        "checks": checks,
    }


# ---------------------------------------------------------------------------
# Per-route support checks
# ---------------------------------------------------------------------------

async def _trove_configured(db: AsyncSession, device_id: str) -> bool:
    ds = await get_device_settings(db, device_id)
    return bool(ds and ds.trove_api_key and ds.trove_enabled)


async def _tiger_configured(db: AsyncSession, device_id: str) -> bool:
    from app.brokers.tiger_service import tiger_configured

    return await tiger_configured(db, device_id)


async def _jupiter_enabled(db: AsyncSession, device_id: str) -> bool:
    ds = await get_device_settings(db, device_id)
    return bool(ds and (ds.jupiter_enabled or False))


async def _check_caps(
    db: AsyncSession,
    portfolio_id: Optional[int],
    qty: float,
    price: float,
    side: str,
    asset_class: str,
) -> Optional[str]:
    if portfolio_id is None:
        return None
    res = await db.execute(
        select(TradingCap).where(TradingCap.portfolio_id == portfolio_id, TradingCap.enabled == True)  # noqa: E712
    )
    caps = res.scalar_one_or_none()
    if caps is None:
        return None

    if asset_class == "forex":
        notional = qty * price  # lots vs notional approximated below
    else:
        notional = qty * price

    if caps.max_position_amount and notional > float(caps.max_position_amount):
        return f"order size {notional:.2f} exceeds cap {caps.max_position_amount:.2f}"

    if caps.max_position_percentage:
        res = await db.execute(select(Portfolio).where(Portfolio.id == portfolio_id))
        portfolio = res.scalar_one_or_none()
        equity = float(portfolio.cash or 0.0) if portfolio else 0.0
        limit = equity * (float(caps.max_position_percentage) / 100.0)
        if notional > limit:
            return f"order size {notional:.2f} exceeds {caps.max_position_percentage:.1f}% cap ({limit:.2f})"

    if caps.daily_loss_limit and side == "sell":
        today_loss = await _today_realized_loss(db)
        if abs(today_loss) + notional * 0.01 > float(caps.daily_loss_limit):
            return f"order would exceed daily loss limit {caps.daily_loss_limit:.2f}"
    return None


async def _today_realized_loss(db: AsyncSession) -> float:
    """Sum of today's negative realized PnL across trades (global daily guard)."""
    from datetime import datetime

    today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    res = await db.execute(
        select(func.coalesce(func.sum(Trade.pnl), 0.0)).where(
            Trade.created_at >= today,
            Trade.pnl < 0,
        )
    )
    return float(res.scalar_one_or_none() or 0.0)


async def _has_cash(db: AsyncSession, portfolio_id: int, price: float, qty: float, asset_class: str) -> tuple[bool, str]:
    res = await db.execute(select(Portfolio.cash).where(Portfolio.id == portfolio_id))
    cash = float(res.scalar_one_or_none() or 0.0)
    notional = qty * price * (1 + 0.001)  # rough commission headroom
    if notional > cash:
        return False, f"insufficient cash ({cash:.2f}) for {notional:.2f} order"
    return True, f"cash {cash:.2f} covers order"



# ---------------------------------------------------------------------------
# Convenience: shared paper execution
# ---------------------------------------------------------------------------

async def execute_paper(
    device_id: str,
    symbol: str,
    side: str,
    qty: float,
    price: float,
    asset_class: str = "crypto",
    agent_name: str = "manual",
    reasoning: str = "",
) -> Dict[str, Any]:
    """Route a paper trade through the Universal Paper Trading engine."""
    from app.services.paper_trading_service import get_paper_trading_service

    return await get_paper_trading_service().place_trade(
        device_id=device_id,
        symbol=symbol,
        side=side,
        qty=qty,
        price=price,
        asset_class=asset_class,
        agent_name=agent_name,
        reasoning=reasoning,
    )


def describe_failures(result: Dict[str, Any]) -> str:
    """Human-readable join of the failed prerequisite checks."""
    failed = [c for c in result.get("checks", []) if not c["passed"]]
    if not failed:
        return ""
    return "; ".join(f"{c['name']}: {c['detail']}" for c in failed)