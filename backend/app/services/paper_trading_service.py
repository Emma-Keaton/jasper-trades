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
from app.models import DeviceSettings, Position, Trade, Portfolio

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
                        # Merge per key, unconditionally.
                        #
                        # This used to be gated on `cfg.get("current_balance")
                        # is not None`, which meant a config that only set
                        # `enabled` was discarded wholesale: toggling paper
                        # trading off in Settings did nothing at all, silently,
                        # because the flag was never read.
                        if isinstance(cfg, dict):
                            for key in state:
                                if key in cfg:
                                    state[key] = cfg[key]
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

    async def _sync_portfolio(
        self,
        db: AsyncSession,
        *,
        portfolio: Optional[Portfolio],
        symbol: str,
        side: str,
        qty: float,
        price: float,
        notional: float,
        commission: float,
        asset_class: str,
        pos_snapshot: Optional[Dict[str, Any]],
    ) -> None:
        """Apply one paper fill to `Portfolio.cash` and the `Position` table.

        The live path does this in `api/v1/trading.py`; paper had no equivalent,
        which is why a paper portfolio reported a flat $10,000 no matter how many
        trades it made.

        Weighted-average cost basis is carried in `Position.avg_price`, matching
        the JSON ledger, so the two never disagree on what a position cost.

        `pos_snapshot` is the position *after* the fill, used so the caller does
        not have to re-read the ledger. It is `None` once a position is fully
        closed and removed.
        """
        if portfolio is None:
            logger.warning(
                "No portfolio for this device; paper fill not mirrored",
                device_id=getattr(portfolio, "device_id", None),
            )
            return

        if side == "buy":
            # Debit cash including commission.
            portfolio.cash = float(portfolio.cash or 0.0) - (notional + commission)

            existing = (
                await db.execute(
                    select(Position).where(
                        Position.portfolio_id == portfolio.id,
                        Position.symbol == symbol,
                    )
                )
            ).scalar_one_or_none()

            if existing is None:
                db.add(
                    Position(
                        portfolio_id=portfolio.id,
                        symbol=symbol,
                        quantity=qty,
                        avg_price=price,
                        current_price=price,
                        market_value=qty * price,
                    )
                )
            else:
                prior_qty = float(existing.quantity or 0.0)
                total_qty = prior_qty + qty
                if total_qty > 0:
                    # Weighted-average cost basis, matching the JSON ledger so the
                    # two never disagree on what a position cost.
                    existing.avg_price = (
                        float(existing.avg_price or 0.0) * prior_qty + price * qty
                    ) / total_qty
                existing.quantity = total_qty
                existing.current_price = price
                existing.market_value = total_qty * price
        else:
            # Credit cash net of commission.
            portfolio.cash = float(portfolio.cash or 0.0) + (notional - commission)

            existing = (
                await db.execute(
                    select(Position).where(
                        Position.portfolio_id == portfolio.id,
                        Position.symbol == symbol,
                    )
                )
            ).scalar_one_or_none()

            if existing is not None:
                remaining = float(existing.quantity or 0.0) - qty
                if remaining <= 1e-9:
                    # Fully closed. Removed rather than left at zero quantity,
                    # matching the JSON ledger which pops the position: an
                    # open-position listing full of 0-quantity rows is noise, and
                    # the closed trade is already recorded as a Trade row.
                    await db.delete(existing)
                else:
                    existing.quantity = remaining
                    existing.current_price = price
                    existing.market_value = remaining * price

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
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None,
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
            # Bracket levels for the signal-exit monitor (buy-side only).
            if stop_loss and stop_loss > 0:
                pos["stop_loss"] = float(stop_loss)
            if take_profit and take_profit > 0:
                pos["take_profit"] = float(take_profit)
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

                # Mirror the fill into the authoritative tables.
                #
                # The JSON ledger above is the paper engine's own bookkeeping, but
                # everything a user or a downstream decision reads comes from
                # `Portfolio` and `Position`: /trading/positions, the portfolio
                # total, the mark-to-market job, the daily equity snapshot, and
                # the auto-payout source. Writing only the JSON meant a successful
                # $1,000 buy left Portfolio.cash at 10,000 with zero Position
                # rows, so paper trading produced no evidence at all - which is
                # the entire reason to run it.
                #
                # A failure here must not lose the fill: the trade is already
                # recorded in the JSON ledger, so it is logged and the fill stands
                # rather than being rolled back into an inconsistent state.
                try:
                    await self._sync_portfolio(
                        db,
                        portfolio=portfolio,
                        symbol=symbol,
                        side=side,
                        qty=qty,
                        price=price,
                        notional=notional,
                        commission=commission,
                        asset_class=asset_class,
                        pos_snapshot=dict(pos) if pos else None,
                    )
                    await db.commit()
                except Exception as exc:  # noqa: BLE001
                    await db.rollback()
                    logger.error(
                        "Paper fill not mirrored into portfolio/positions",
                        error=str(exc),
                        symbol=symbol,
                        side=side,
                    )

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
                try:
                    await db.refresh(t)
                except Exception:  # noqa: BLE001
                    pass

                # Train the pattern model on this trade's outcome (paper trading
                # is the primary source of closed-trade experiences).
                if side == "sell" and realized is not None:
                    try:
                        from types import SimpleNamespace

                        from app.services.trade_monitor import trade_monitor

                        now_iso = _now().isoformat()
                        ns = SimpleNamespace(
                            id=t.id if t.id is not None else 0,
                            symbol=symbol,
                            type="SELL",
                            entry_price=float(pos["avg_price"]) if pos and pos.get("avg_price") else 0.0,
                            exit_price=price,
                            shares=qty,
                            pnl=realized,
                            created_at=now_iso,
                            filled_at=now_iso,
                            agent_name=agent_name,
                            metadata={},
                        )
                        await trade_monitor.on_trade_closed(ns)
                    except Exception as e:  # noqa: BLE001
                        logger.warning("Trade learning hook failed (non-fatal)", error=str(e)[:200])
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


    async def check_brackets(self, device_id: str) -> List[Dict[str, Any]]:
        """Close paper positions that breach their stop-loss / take-profit.

        Uses the same market price source as signal execution so a bracket is
        checked against the same number the entry was sized at. Failures on a
        single symbol never abort the rest of the device's positions.
        """
        from app.services.valuation_service import ValuationService

        state = await self._load_state(device_id)
        closed: List[Dict[str, Any]] = []
        if not state.get("enabled", True):
            return closed

        val = ValuationService()
        for symbol, pos in list(state.get("positions", {}).items()):
            sl = pos.get("stop_loss")
            tp = pos.get("take_profit")
            if not sl and not tp:
                continue
            try:
                price = await val.get_price(symbol)
            except Exception:  # noqa: BLE001
                price = None
            if not price or price <= 0:
                continue

            trigger = None
            if sl and price <= float(sl):
                trigger = "stop_loss"
            elif tp and price >= float(tp):
                trigger = "take_profit"
            if not trigger:
                continue

            qty = float(pos["qty"])
            result = await self.place_trade(
                device_id=device_id,
                symbol=symbol,
                side="sell",
                qty=qty,
                price=price,
                asset_class=pos.get("asset_class", "crypto"),
                agent_name="signal-exit",
                reasoning=f"Auto-close on {trigger}",
            )
            if result.get("error"):
                logger.warning(
                    "Bracket close failed", symbol=symbol, trigger=trigger, error=result["error"]
                )
                continue
            closed.append(
                {
                    "symbol": symbol,
                    "trigger": trigger,
                    "price": price,
                    "qty": qty,
                    "realized_pnl": result.get("realized_pnl"),
                }
            )
            logger.info(
                "Paper bracket closed",
                symbol=symbol,
                trigger=trigger,
                price=price,
                realized_pnl=result.get("realized_pnl"),
            )
        return closed

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

            # The payout network the user selected. Without it the on-chain
            # transfer cannot be signed, so this trade's payout would be skipped
            # and only logged as an error.
            payout_chain = payout_cfg.get("payout_chain")
            if not payout_chain:
                logger.warning(
                    "End-of-trade payout skipped for device %s: no payout_chain "
                    "configured. Set the payout network in Settings.",
                    device_id,
                )
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
                    destination_chain=payout_chain,
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

