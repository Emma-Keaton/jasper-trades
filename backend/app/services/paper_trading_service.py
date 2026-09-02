"""
Universal Paper Trading Engine.

Simulates live fills (crypto, forex, stocks) so the AI trader can be tested
risk-free before going live. Every AI signal routes here first when
UNIVERSAL_PAPER_TRADING is enabled; a paper track record is kept per device
so we can measure the AI trader's actual ability.

Execution rules (per asset class):
- Crypto  : buy/sell token units against a quote base (e.g. USDT); decimals/precision
            handled to 8 dp.
- Forex   : size in lots (1 lot = 100,000 base units); pip-based P&L.
- Stocks  : number of shares; fractional shares allowed.

State is persisted in the DeviceSettings.universal_paper_trading_config JSON and
each fill is recorded as a Trade row with is_paper=True.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import structlog
from sqlalchemy import select

from app.config import settings
from app.database import async_session
from app.models import DeviceSettings, Trade, Portfolio

logger = structlog.get_logger(__name__)

FOREX_LOT_BASE_UNITS = 100_000
CRYPTO_PRECISION = 8


def _now() -> datetime:
    return datetime.now(timezone.utc)


class UniversalPaperTradingService:
    """Virtual ledger for paper trading across asset classes."""

    def __init__(self) -> None:
        self._mem: Dict[str, Dict[str, Any]] = {}  # device_id -> state cache

    # ------------------------------------------------------------------
    # State load / save
    # ------------------------------------------------------------------
    def _new_state(self) -> Dict[str, Any]:
        return {
            "enabled": settings.UNIVERSAL_PAPER_TRADING,
            "initial_capital": settings.UNIVERSAL_PAPER_CAPITAL,
            "current_balance": settings.UNIVERSAL_PAPER_CAPITAL,
            "total_pnl": 0.0,
            "realized_pnl": 0.0,
            "unrealized_pnl": 0.0,
            "currency": settings.UNIVERSAL_PAPER_CURRENCY,
            "positions": {},  # symbol -> {qty, avg_price, asset_class}
            "trade_count": 0,
            "wins": 0,
            "losses": 0,
            "created_at": _now().isoformat(),
        }

    async def _load_state(self, device_id: str) -> Dict[str, Any]:
        if device_id in self._mem:
            return self._mem[device_id]
        state = self._new_state()
        if settings.UNIVERSAL_PAPER_TRADING:
            try:
                async with async_session() as db:
                    result = await db.execute(
                        select(DeviceSettings).where(DeviceSettings.device_id == device_id)
                    )
                    ds = result.scalar_one_or_none()
                    if ds and ds.universal_paper_trading_config:
                        cfg = json.loads(ds.universal_paper_trading_config)
                        if cfg.get("current_balance") is not None:
                            state.update({k: cfg.get(k, state[k]) for k in state})
            except Exception as e:  # noqa: BLE001
                logger.debug("Paper state load failed", error=str(e))
        self._mem[device_id] = state
        return state

    async def _save_state(self, device_id: str, state: Dict[str, Any]) -> None:
        try:
            async with async_session() as db:
                result = await db.execute(
                    select(DeviceSettings).where(DeviceSettings.device_id == device_id)
                )
                ds = result.scalar_one_or_none()
                if ds is None:
                    ds = DeviceSettings(device_id=device_id)
                    db.add(ds)
                ds.universal_paper_trading_config = json.dumps(state)
                await db.commit()
        except Exception as e:  # noqa: BLE001
            logger.error("Failed to persist paper state", error=str(e))
        self._mem[device_id] = state

    def _normalize_quantity(self, qty: float, asset_class: str) -> float:
        """Round/normalize quantity for the asset class."""
        if asset_class == "forex":
            return round(qty, 2)  # lots
        if asset_class == "crypto":
            return round(qty, CRYPTO_PRECISION)
        return round(qty, 2)  # stocks fractional shares

    def _fill_cost(
        self, qty: float, price: float, asset_class: str, commission_rate: float
    ) -> tuple[float, float]:
        if asset_class == "forex":
            notional = qty * FOREX_LOT_BASE_UNITS * price
        else:
            notional = qty * price
        return notional, notional * commission_rate

    async def place_trade(
        self,
        device_id: str,
        symbol: str,
        side: str,
        qty: float,
        price: float,
        asset_class: str = "crypto",
        commission_rate: float = 0.001,
        agent_name: str = "unknown",
        reasoning: str = "",
    ) -> Dict[str, Any]:
        """Simulate a fill and update the paper ledger. Purely numeric/safe."""
        state = await self._load_state(device_id)
        if not state.get("enabled", True):
            return {"error": "Paper trading disabled"}

        qty = self._normalize_quantity(qty, asset_class)
        if qty <= 0 or price <= 0:
            return {"error": "Invalid quantity or price"}

        notional, commission = self._fill_cost(qty, price, asset_class, commission_rate)
        pos = state["positions"].get(symbol)

        if side == "buy":
            if notional + commission > state["current_balance"]:
                return {"error": "Insufficient paper balance"}
            if pos is None:
                pos = {"qty": 0.0, "avg_price": 0.0, "asset_class": asset_class}
                state["positions"][symbol] = pos
            total_qty = pos["qty"] + qty
            pos["avg_price"] = (
                (pos["avg_price"] * pos["qty"] + price * qty) / total_qty
                if total_qty
                else price
            )
            pos["qty"] = total_qty
            pos["asset_class"] = asset_class
            state["current_balance"] -= notional + commission
        else:  # sell
            if pos is None or pos["qty"] < qty:
                return {"error": "Insufficient paper position"}
            realized = (price - pos["avg_price"]) * qty - commission
            pos["qty"] -= qty
            state["current_balance"] += notional - commission
            state["realized_pnl"] += realized
            if pos["qty"] <= 0:
                state["positions"].pop(symbol, None)
            if realized > 0:
                state["wins"] += 1
            elif realized < 0:
                state["losses"] += 1

        state["trade_count"] += 1
        await self._save_state(device_id, state)

        # End-of-trade auto-payout: if enabled, pay out % of realized profit immediately on profitable closes
        if side == "sell" and realized > 0:
            try:
                await self._maybe_execute_end_of_trade_payout(
                    device_id=device_id, realized_pnl=realized, symbol=symbol,
                )
            except Exception as e:  # noqa: BLE001
                logger.warning("End-of-trade payout failed (non-fatal)", error=str(e))

        try:
            async with async_session() as db:
                # Resolve portfolio_id from device_id
                port_result = await db.execute(
                    select(Portfolio).where(Portfolio.device_id == device_id).limit(1)
                )
                portfolio = port_result.scalar_one_or_none()

                t = Trade(
                    symbol=symbol,
                    side=side,  # buy/sell
                    quantity=qty,
                    price=price,
                    broker="paper",
                    status="filled",
                    agent_name=agent_name,
                    portfolio_id=portfolio.id if portfolio else None,
                    pnl=realized if side == "sell" else None,
                    pnl_percent=((realized / (pos["avg_price"] * qty)) * 100 if side == "sell" and pos and pos.get("avg_price") and qty else None),
                    created_at=_now().replace(tzinfo=None),
                )
                db.add(t)
                await db.commit()
        except Exception as e:  # noqa: BLE001
            logger.error("Failed to store paper trade row", error=str(e))

        # Notify the user's connected Telegram chat about the paper trade.
        await self._notify_telegram(
            device_id,
            {
                "action": side.upper(),
                "shares": qty,
                "symbol": symbol,
                "price": price,
                "total": notional,
                "agent": agent_name,
                "order_type": "PAPER",
                "timestamp": _now().isoformat(),
            },
        )

        return {
            "success": True,
            "mode": "paper",
            "symbol": symbol,
            "side": side,
            "quantity": qty,
            "price": price,
            "commission": round(commission, 6),
            "balance": round(state["current_balance"], 2),
            "realized_pnl": round(state["realized_pnl"], 6),
            "trade_count": state["trade_count"],
        }


    async def _notify_telegram(self, device_id: str, trade: Dict[str, Any]) -> None:
        """Send a trade alert to the user's verified Telegram chat (if any).

        Looks up TelegramUser by device_id; only sends when verified and the
        user has trade notifications enabled. Never raises - alert failures must
        not block the paper fill.
        """
        try:
            from sqlalchemy import select as _sel
            from app.models import TelegramUser
            from app.services.telegram_service import telegram_service

            if not telegram_service.enabled:
                return
            async with async_session() as db:
                result = await db.execute(
                    _sel(TelegramUser).where(TelegramUser.device_id == device_id)
                )
                tg = result.scalar_one_or_none()
            if not tg or not tg.is_verified or not tg.trade_notifications_enabled:
                return
            # Register + send (in-memory cache + direct send).
            telegram_service.register_user(device_id, tg.chat_id)
            await telegram_service.notify_trade_executed(tg.chat_id, trade)
        except Exception as e:  # noqa: BLE001
            logger.debug("Telegram trade alert failed", error=str(e))

    async def get_account(self, device_id: str) -> Dict[str, Any]:
        state = await self._load_state(device_id)
        wins = state.get("wins", 0)
        losses = state.get("losses", 0)
        return {
            "enabled": state.get("enabled", True),
            "initial_capital": state.get("initial_capital"),
            "current_balance": round(state.get("current_balance", 0), 2),
            "currency": state.get("currency"),
            "total_pnl": round(state.get("total_pnl", 0), 6),
            "realized_pnl": round(state.get("realized_pnl", 0), 6),
            "unrealized_pnl": round(state.get("unrealized_pnl", 0), 6),
            "trade_count": state.get("trade_count", 0),
            "wins": wins,
            "losses": losses,
            "win_rate": round(wins / (wins + losses), 4) if (wins + losses) else 0.0,
            "positions": state.get("positions", {}),
        }

    async def _maybe_execute_end_of_trade_payout(
        self, device_id: str, realized_pnl: float, symbol: str,
    ) -> None:
        """Execute auto-payout for a profitable close if frequency == end_of_trade."""
        from app.services.encryption import EncryptionHelper
        from app.models import Portfolio
        from app.services.withdrawal_service import WithdrawalService

        async with async_session() as db:
            ds_result = await db.execute(
                select(DeviceSettings).where(DeviceSettings.device_id == device_id)
            )
            ds = ds_result.scalar_one_or_none()
            if not ds or not ds.payout_config:
                return

            encryption = EncryptionHelper()
            payout_cfg = encryption.decrypt_json(ds.payout_config)
            if not payout_cfg:
                return
            if payout_cfg.get("payout_frequency") != "end_of_trade":
                return
            if not payout_cfg.get("payout_enabled", False):
                return

            threshold = payout_cfg.get("min_payout_threshold", 10.0)
            if realized_pnl < threshold:
                return

            wallet = payout_cfg.get("crypto_wallet")
            if not wallet:
                return

            percentage = payout_cfg.get("payout_percentage", 50.0)
            payout_amount = round(realized_pnl * percentage / 100, 2)
            if payout_amount <= 0:
                return

            # Find portfolio linked to this device
            port_result = await db.execute(
                select(Portfolio).where(Portfolio.device_id == device_id).limit(1)
            )
            portfolio = port_result.scalar_one_or_none()
            if not portfolio:
                return

            ws = WithdrawalService(db)
            try:
                w = await ws.create_withdrawal(
                    portfolio_id=portfolio.id,
                    amount=payout_amount,
                    withdrawal_type="auto_payout",
                    destination_type="crypto_wallet",
                    destination_address=wallet,
                    daily_pnl=realized_pnl,
                    payout_percentage=percentage,
                )
                await ws.process_withdrawal(w.id)
                logger.info(
                    f"End-of-trade payout: ${payout_amount:.2f} for {symbol} "
                    f"(realized PnL=${realized_pnl:.2f}) on device {device_id[:8]}..."
                )
            except Exception as e:  # noqa: BLE001
                logger.warning("End-of-trade payout creation failed", error=str(e))

    async def reset_account(self, device_id: str) -> Dict[str, Any]:
        await self._load_state(device_id)
        fresh = self._new_state()
        await self._save_state(device_id, fresh)
        return {"success": True, "message": "Paper account reset"}

    def clear_cache(self) -> None:
        self._mem.clear()


_paper: Optional[UniversalPaperTradingService] = None


def get_paper_trading_service() -> UniversalPaperTradingService:
    global _paper
    if _paper is None:
        _paper = UniversalPaperTradingService()
    return _paper

