"""
Auto Executor — self-improving paper-trading loop.
==================================================

Wires together the keyless market data feed, Kronos forecasting, the
self-improving strategy learner, and the universal paper-trading engine:

    market movement (keyless)
        -> Kronos forecast (predicted return + confidence)
        -> strategy learner gates the trade (confidence threshold / band width)
        -> trade_gate.execute_paper -> universal paper ledger
        -> TP/SL close -> experience recorded -> learner refit

The loop is paper-only by default (trade_gate resolves paper unless the device is
explicitly configured for live). Every filled trade is stored as an Experience so
the pattern analyzer and /learning endpoints reflect auto-executor activity.

The learned parameters start unvalidated and fall back to the configured base
values, so early paper trading is conservative and only relaxes as scored
forecasts accumulate statistical evidence.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import structlog

from app.config import settings
from app.services.unified_market_data import (
    DEFAULT_WATCHLIST,
    get_unified_market_data,
)
from app.services.strategy_learner import (
    MIN_SAMPLES,
    apply,
    fit,
    should_trade,
)
from app.services.strategy_learner import ScoredForecast
from app.services.trade_gate import PAPER, execute_paper
from app.services.trade_monitor import trade_monitor
from app.services.experience_buffer import Experience
from app.database import async_session
from app.models import TelegramUser, WatchlistItem
from sqlalchemy import select
from app.services.telegram_service import telegram_service

logger = structlog.get_logger(__name__)

AUTO_EXECUTOR_DEVICE_ID = "auto-executor"

KRONOS_HORIZON = 5
FORECAST_CACHE_TTL_SECONDS = 300

DEFAULT_CONFIG: Dict[str, Any] = {
    "enabled": True,
    "interval_seconds": 60,
    "forecast_horizon": KRONOS_HORIZON,
    "watchlist": dict(DEFAULT_WATCHLIST),
    "position_size_usd": 100.0,
    "take_profit_pct": 1.5,
    "stop_loss_pct": 1.0,
    "max_positions": 5,
    "base_confidence_threshold": 70.0,
    "base_band_tolerance": 0.06,
    "base_sample_penalty": 0.0,
    "min_kronos_confidence": 40.0,
    # Top-performers watchlist sync: periodically pull the top 24h performers
    # and make the top 15 the traded + watched universe.
    "top_performers_enabled": True,
    "top_performers_limit": 15,
    "watchlist_sync_interval_seconds": 3600,
    # Rotation: "gradual" replaces only the entries that fell out of the top
    # list (typically 1-2 per hour); "full" always replaces everything. A full
    # replace also triggers automatically in gradual mode when the overlap
    # with the top list drops below the threshold (regime shift).
    "watchlist_rotation_mode": "gradual",
    "watchlist_rotation_full_replace_threshold": 0.5,
}


@dataclass
class PositionInfo:
    symbol: str
    asset_class: str
    side: str  # "buy" or "sell"
    entry_price: float
    qty: float
    notional_usd: float
    opened_at: str
    take_profit: float
    stop_loss: float
    forecast: Dict[str, Any]
    forecast_confidence: int


@dataclass
class PendingForecast:
    """A forecast that opened a position, awaiting its realised outcome."""
    symbol: str
    confidence: int
    probability_up: float
    last_close: float
    side: str
    opened_at: str
    horizon: int


class AutoExecutor:
    """
    Background auto-executor for paper trading.

    Each tick:
      1. Refreshes keyless market data (price + movement) for the watchlist.
      2. Gets a Kronos forecast for symbols without a fresh cached forecast.
      3. Applies the strategy learner to gate entries.
      4. Opens paper positions when a signal clears the learned threshold.
      5. Closes positions on take-profit / stop-loss and records outcomes.
      6. Periodically refits the learner on resolved scored forecasts.
    """

    def __init__(self) -> None:
        self._task: Optional[asyncio.Task] = None
        self._running = False
        self._lock = asyncio.Lock()
        self.config: Dict[str, Any] = dict(DEFAULT_CONFIG)
        self._market_data = get_unified_market_data()

        # Runtime state
        self._positions: Dict[str, PositionInfo] = {}  # symbol -> position
        self._pending: List[PendingForecast] = []  # forecasts awaiting realised outcome
        self._resolved: List[ScoredForecast] = []  # scored forecasts for learner fit
        self._learner_sample_size = 0
        self._fitted_state: Optional[Any] = None  # fitted LearnedState from strategy_learner.fit
        self._forecast_cache: Dict[str, Tuple[Dict[str, Any], float]] = {}
        self._started_at: Optional[str] = None
        self._ticks = 0
        self._trades_opened = 0
        self._trades_closed = 0
        self._last_refit = 0.0
        self._telegram_chat_ids: List[str] = []
        self._last_summary_date: Optional[str] = None
        self._last_watchlist_sync = 0.0
        self._watchlist_source = "top-performers"
        self._last_rotation: Optional[Dict[str, Any]] = None

    @property
    def running(self) -> bool:
        return self._running

    async def start(self, config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Start the auto-executor background loop (paper trading)."""
        if self._running:
            return {"status": "already_running", "device_id": AUTO_EXECUTOR_DEVICE_ID}

        if config:
            self.config.update(config)
        self.config.setdefault("watchlist", dict(DEFAULT_WATCHLIST))
        self._running = True
        self._started_at = datetime.now(timezone.utc).isoformat()
        # Force an immediate top-performers watchlist sync on the first tick.
        self._last_watchlist_sync = 0.0
        await self._load_telegram_users()
        self._task = asyncio.create_task(self._loop())
        logger.info(
            "Auto executor started",
            device_id=AUTO_EXECUTOR_DEVICE_ID,
            interval=self.config["interval_seconds"],
        )
        return {
            "status": "started",
            "device_id": AUTO_EXECUTOR_DEVICE_ID,
            "config": self.config,
        }

    async def stop(self) -> Dict[str, Any]:
        """Stop the auto-executor loop (open positions are left in place)."""
        if not self._running:
            return {"status": "not_running"}
        self._running = False
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        logger.info("Auto executor stopped")
        return {"status": "stopped", "device_id": AUTO_EXECUTOR_DEVICE_ID}

    def status(self) -> Dict[str, Any]:
        return {
            "running": self._running,
            "device_id": AUTO_EXECUTOR_DEVICE_ID,
            "mode": PAPER,
            "started_at": self._started_at,
            "ticks": self._ticks,
            "trades_opened": self._trades_opened,
            "trades_closed": self._trades_closed,
            "open_positions": len(self._positions),
            "pending_forecasts": len(self._pending),
            "resolved_forecasts": len(self._resolved),
            "learner_sample_size": self._learner_sample_size,
            "config": self.config,
            "last_watchlist_rotation": self._last_rotation,
            "positions": [p.__dict__ for p in self._positions.values()],
        }

    async def update_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        was_running = self._running
        if was_running:
            await self.stop()
        self.config.update(config)
        self.config.setdefault("watchlist", dict(DEFAULT_WATCHLIST))
        if was_running:
            await self.start()
        return {"status": "updated", "config": self.config}

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------
    async def _loop(self) -> None:
        interval = float(self.config.get("interval_seconds", 60))
        while self._running:
            try:
                await self._tick()
            except asyncio.CancelledError:
                break
            except Exception as e:  # noqa: BLE001
                logger.exception("Auto executor tick failed", error=str(e))
            if self._running:
                await asyncio.sleep(interval)

    async def _tick(self) -> None:
        if not self.config.get("enabled", False):
            return  # paper auto-executor is armed but not activated
        self._ticks += 1
        now = time.time()

        # 0. Periodically come to the top performers and refresh the watchlist.
        await self._maybe_sync_watchlist(now)

        # 1. Refresh market movement for the whole watchlist (keyless).
        watchlist = self.config.get("watchlist", DEFAULT_WATCHLIST)
        movements: Dict[str, Dict[str, Any]] = {}
        for asset_class, symbols in watchlist.items():
            for symbol in symbols:
                try:
                    movements[symbol] = await self._market_data.get_market_movement(
                        symbol, asset_class
                    )
                except Exception as e:  # noqa: BLE001
                    logger.debug("market movement failed", symbol=symbol, error=str(e))
                    movements[symbol] = {
                        "symbol": symbol,
                        "asset_class": asset_class,
                        "price": None,
                        "error": str(e),
                    }

        # 2. Manage existing positions (TP/SL exits) using latest prices.
        await self._manage_positions(movements)

        # 3. Resolve pending forecasts whose horizon has elapsed (score for learner).
        await self._resolve_pending(movements)

        # 4. Evaluate symbols without a position for new entries.
        max_positions = int(self.config.get("max_positions", 5))
        for asset_class, symbols in watchlist.items():
            if len(self._positions) >= max_positions:
                break
            for symbol in symbols:
                if symbol in self._positions:
                    continue
                if movements.get(symbol, {}).get("price") is None:
                    continue
                await self._evaluate_entry(symbol, asset_class, movements[symbol])
                if len(self._positions) >= max_positions:
                    break

        # 5. Periodically refit the learner on resolved scored forecasts.
        if now - self._last_refit > 900:  # every 15 minutes
            await self._refit_learner()
            self._last_refit = now

        # 6. Send daily summary (once per UTC day).
        await self._send_daily_summary()

    # ------------------------------------------------------------------
    # Top-performers watchlist sync (top 15 assets to watch and trade)
    # ------------------------------------------------------------------
    async def _maybe_sync_watchlist(self, now: float) -> None:
        """Refresh the traded/watched universe from the top 24h performers."""
        if not self.config.get("top_performers_enabled", True):
            return
        # An empty watchlist always triggers an immediate sync (e.g. right
        # after Start on the dashboard) instead of waiting for the interval.
        watchlist = self.config.get("watchlist") or {}
        is_empty = not any(symbols for symbols in watchlist.values())
        interval = float(self.config.get("watchlist_sync_interval_seconds", 3600))
        if not is_empty and now - self._last_watchlist_sync < interval:
            return
        self._last_watchlist_sync = now
        try:
            limit = int(self.config.get("top_performers_limit", 15))
            top = await build_top_performers(limit)
            if not top:
                return
            rotated, rotation = self._rotate_watchlist(top, is_empty)
            current_symbols = [
                s for syms in (self.config.get("watchlist") or {}).values() for s in syms
            ]
            if rotated == current_symbols and not is_empty:
                logger.info("Top-performers rotation: no changes", overlap=rotation["overlap"])
                return
            await self._apply_watchlist({"crypto": rotated}, rotation=rotation)
            logger.info(
                "Auto executor watchlist rotated from top performers",
                mode=rotation["mode"],
                added=rotation["added"],
                removed=rotation["removed"],
                count=len(rotated),
            )
        except Exception as e:  # noqa: BLE001
            logger.warning("Top-performers watchlist sync failed", error=str(e))

    def _rotate_watchlist(
        self, top: List[str], is_empty: bool
    ) -> Tuple[List[str], Dict[str, Any]]:
        """Blend the current watchlist with the fresh top performers.

        gradual: keep current members still in the top list, backfill with the
                 best newcomers (usually replaces just 1-2 assets per hour).
        full:    replace the whole list. Also forced in gradual mode when the
                 overlap drops below `watchlist_rotation_full_replace_threshold`.
        """
        current: List[str] = []
        for syms in (self.config.get("watchlist") or {}).values():
            for s in syms:
                if s not in current:
                    current.append(s)

        if is_empty or not current:
            rotation = {"mode": "full", "added": list(top), "removed": [], "overlap": 0.0}
            return list(top), rotation

        top_set = set(top)
        kept = [s for s in current if s in top_set]
        overlap = len(kept) / len(current)
        mode = str(self.config.get("watchlist_rotation_mode", "gradual")).lower()
        threshold = float(self.config.get("watchlist_rotation_full_replace_threshold", 0.5))

        if mode == "full" or overlap < threshold:
            rotation = {
                "mode": "full",
                "added": [s for s in top if s not in kept],
                "removed": [s for s in current if s not in top_set],
                "overlap": overlap,
            }
            return list(top), rotation

        rotated = kept + [s for s in top if s not in kept]
        rotated = rotated[: len(top)]
        rotation = {
            "mode": "gradual",
            "added": [s for s in rotated if s not in current],
            "removed": [s for s in current if s not in rotated],
            "overlap": overlap,
        }
        return rotated, rotation

    async def _apply_watchlist(
        self, watchlist: Dict[str, List[str]], rotation: Optional[Dict[str, Any]] = None
    ) -> None:
        """Swap the traded watchlist and persist the diff as the device watchlist."""
        new_symbols = {s for syms in watchlist.values() for s in syms}
        self.config["watchlist"] = watchlist
        self._last_rotation = rotation or self._last_rotation
        # Positions on departed symbols stay open and are managed by TP/SL.
        for symbol in list(self._positions.keys()):
            if symbol not in new_symbols:
                logger.info("Symbol left top-performers universe; leaving position", symbol=symbol)
        self._forecast_cache = {
            s: v for s, v in self._forecast_cache.items() if s in new_symbols
        }

        # Persist only the diff (max 15, source-tagged) so gradual rotations
        # touch one or two rows instead of rewriting the whole watchlist.
        try:
            async with async_session() as db:
                existing = (
                    await db.execute(
                        select(WatchlistItem).where(
                            WatchlistItem.device_id == AUTO_EXECUTOR_DEVICE_ID,
                            WatchlistItem.source == self._watchlist_source,
                        )
                    )
                ).scalars().all()
                existing_syms = {r.symbol for r in existing}
                removed = existing_syms - new_symbols
                added = new_symbols - existing_syms
                for row in existing:
                    if row.symbol in removed:
                        await db.delete(row)
                for asset_class, symbols in watchlist.items():
                    for symbol in symbols[:15]:
                        if symbol in added:
                            db.add(
                                WatchlistItem(
                                    device_id=AUTO_EXECUTOR_DEVICE_ID,
                                    symbol=symbol,
                                    asset_class=asset_class,
                                    source=self._watchlist_source,
                                )
                            )
                await db.commit()
        except Exception as e:  # noqa: BLE001
            logger.debug("Watchlist persistence failed", error=str(e))

    # ------------------------------------------------------------------
    # Entry evaluation
    # ------------------------------------------------------------------
    async def _evaluate_entry(
        self, symbol: str, asset_class: str, movement: Dict[str, Any]
    ) -> None:
        price = movement.get("price")
        if not price:
            return

        # Kronos forecast (cached where fresh).
        forecast = await self._get_kronos_forecast(symbol, asset_class)
        if forecast.get("status") != "success":
            return

        predicted_return = float(forecast.get("predicted_return") or 0.0)
        predictions = forecast.get("predictions") or []

        # Kronos confidence: magnitude of the predicted move, 0..100.
        kronos_confidence = int(min(100, max(0, abs(predicted_return) * 1000)))
        if kronos_confidence < float(self.config.get("min_kronos_confidence", 40)):
            return

        # Band width from prediction spread (wider = undecided).
        band_width: Optional[float] = None
        if predictions and price:
            spread = float(max(predictions) - min(predictions))
            band_width = spread / price

        # Learner-resolved trading parameters.
        params = apply(
            self._learner_state(),
            configured_threshold=float(self.config.get("base_confidence_threshold", 70)),
            configured_band_tolerance=float(self.config.get("base_band_tolerance", 0.06)),
            configured_sample_penalty=float(self.config.get("base_sample_penalty", 0.0)),
        )

        allowed, reason = should_trade(
            forecast_confidence=kronos_confidence,
            params=params,
            distribution_valid=True,
            band_width=band_width,
        )
        if not allowed:
            logger.debug(
                "Entry gated by learner",
                symbol=symbol,
                confidence=kronos_confidence,
                reason=reason,
            )
            return

        side = "buy" if predicted_return > 0 else "sell"
        probability_up = min(0.99, max(0.01, 0.5 + predicted_return * 5.0))

        position_size_usd = float(self.config.get("position_size_usd", 100.0))
        qty = position_size_usd / price
        take_profit = price * (1 + self.config["take_profit_pct"] / 100)
        stop_loss = price * (1 - self.config["stop_loss_pct"] / 100)
        if side == "sell":
            take_profit, stop_loss = stop_loss, take_profit

        try:
            result = await execute_paper(
                device_id=AUTO_EXECUTOR_DEVICE_ID,
                symbol=symbol,
                side=side,
                qty=qty,
                price=price,
                asset_class=asset_class,
                agent_name="auto-executor",
                reasoning=(
                    f"auto-executor: kronos_conf={kronos_confidence} "
                    f"pred_return={predicted_return:.2%} ({reason})"
                ),
            )
        except Exception as e:  # noqa: BLE001
            logger.warning("Paper entry failed", symbol=symbol, error=str(e))
            return

        if not result.get("success") and not result.get("placed"):
            logger.debug("Paper entry not placed", symbol=symbol, result=result)
            return

        self._positions[symbol] = PositionInfo(
            symbol=symbol,
            asset_class=asset_class,
            side=side,
            entry_price=price,
            qty=qty,
            notional_usd=position_size_usd,
            opened_at=datetime.now(timezone.utc).isoformat(),
            take_profit=take_profit,
            stop_loss=stop_loss,
            forecast=forecast,
            forecast_confidence=kronos_confidence,
        )
        self._pending.append(
            PendingForecast(
                symbol=symbol,
                confidence=kronos_confidence,
                probability_up=probability_up,
                last_close=price,
                side=side,
                opened_at=self._positions[symbol].opened_at,
                horizon=int(self.config.get("forecast_horizon", KRONOS_HORIZON)),
            )
        )
        self._trades_opened += 1
        logger.info(
            "Auto position opened",
            symbol=symbol,
            side=side,
            price=price,
            confidence=kronos_confidence,
            pred_return=predicted_return,
        )
        await self._notify_trade_opened(self._positions[symbol])

    def _learner_state(self):
        """Return the current fitted learner state (or a fresh unvalidated one)."""
        from app.services.strategy_learner import LearnedState

        if self._fitted_state is not None:
            return self._fitted_state
        return LearnedState()

    def _cached_forecast(self, symbol: str) -> Optional[Dict[str, Any]]:
        entry = self._forecast_cache.get(symbol)
        if not entry:
            return None
        forecast, ts = entry
        if time.time() - ts > FORECAST_CACHE_TTL_SECONDS:
            return None
        return forecast

    async def _get_kronos_forecast(self, symbol: str, asset_class: str) -> Dict[str, Any]:
        cached = self._cached_forecast(symbol)
        if cached is not None:
            return cached
        try:
            ohlcv = await self._market_data.get_ohlcv(
                symbol, asset_class, limit=200
            )
            if len(ohlcv) < 30:
                return {"status": "error", "error": "insufficient history"}
            # Lazy import: Kronos needs torch which may not be installed.
            from app.services.kronos.hybrid_service import hybrid_kronos_service

            forecast = await hybrid_kronos_service.predict(
                symbol, ohlcv, forecast_horizon=int(self.config.get("forecast_horizon", KRONOS_HORIZON))
            )
            if forecast.get("status") == "success":
                self._forecast_cache[symbol] = (forecast, time.time())
            return forecast
        except Exception as e:  # noqa: BLE001
            logger.debug("Kronos forecast failed", symbol=symbol, error=str(e))
            return {"status": "error", "error": str(e)}

    # ------------------------------------------------------------------
    # Position management (TP / SL exits)
    # ------------------------------------------------------------------
    async def _manage_positions(self, movements: Dict[str, Dict[str, Any]]) -> None:
        for symbol, position in list(self._positions.items()):
            movement = movements.get(symbol, {})
            price = movement.get("price")
            if not price:
                continue
            side = position.side
            hit_tp = False
            hit_sl = False
            if side == "buy":
                if price >= position.take_profit:
                    hit_tp = True
                elif price <= position.stop_loss:
                    hit_sl = True
            else:  # sell
                if price <= position.take_profit:
                    hit_tp = True
                elif price >= position.stop_loss:
                    hit_sl = True

            if hit_tp or hit_sl:
                reason = "take_profit" if hit_tp else "stop_loss"
                await self._close_position(symbol, price, reason)

    async def _close_position(self, symbol: str, exit_price: float, reason: str) -> None:
        position = self._positions.pop(symbol, None)
        if position is None:
            return
        side = position.side
        if side == "buy":
            pnl_percent = (exit_price - position.entry_price) / position.entry_price * 100
        else:
            pnl_percent = (position.entry_price - exit_price) / position.entry_price * 100
        pnl = pnl_percent / 100 * position.notional_usd

        # Close via paper engine (opposite side, same qty).
        close_side = "sell" if side == "buy" else "buy"
        try:
            await execute_paper(
                device_id=AUTO_EXECUTOR_DEVICE_ID,
                symbol=symbol,
                side=close_side,
                qty=position.qty,
                price=exit_price,
                asset_class=position.asset_class,
                agent_name="auto-executor",
                reasoning=f"auto-executor close: {reason} pnl={pnl_percent:.2f}%",
            )
        except Exception as e:  # noqa: BLE001
            logger.warning("Paper close failed", symbol=symbol, error=str(e))

        # Record experience for self-learning / pattern analyzer.
        hold_minutes = 0
        try:
            opened = datetime.fromisoformat(position.opened_at)
            hold_minutes = int((datetime.now(timezone.utc) - opened).total_seconds() / 60)
        except Exception:  # noqa: BLE001
            pass

        experience = Experience(
            trade_id=f"auto-{symbol}-{int(time.time())}",
            symbol=symbol,
            action=side.upper(),
            entry_price=position.entry_price,
            exit_price=exit_price,
            shares=position.qty,
            pnl=pnl,
            pnl_percent=pnl_percent,
            hold_duration_minutes=hold_minutes,
            agent="auto-executor",
            market_conditions={
                "direction": movements.get(symbol, {}).get("direction", "flat"),
                "source": movements.get(symbol, {}).get("source", "keyless"),
            },
            technical_features={
                "kronos_confidence": position.forecast_confidence,
                "pred_return": float(position.forecast.get("predicted_return") or 0),
            },
        )
        try:
            trade_monitor.exp_buffer.add(experience)
        except Exception as e:  # noqa: BLE001
            logger.debug("experience record skipped", error=str(e))

        self._trades_closed += 1
        logger.info(
            "Auto position closed",
            symbol=symbol,
            side=side,
            reason=reason,
            pnl_percent=pnl_percent,
        )
        await self._notify_trade_closed(
            symbol=symbol,
            side=side,
            exit_price=exit_price,
            reason=reason,
            pnl_percent=pnl_percent,
            pnl_usd=pnl,
        )

    # ------------------------------------------------------------------
    # Telegram notifications (trades + daily summary)
    # ------------------------------------------------------------------
    async def _load_telegram_users(self) -> None:
        """Load verified Telegram chat IDs from the database."""
        try:
            async with async_session() as db:
                result = await db.execute(
                    select(TelegramUser.chat_id).where(
                        TelegramUser.is_verified == True,  # noqa: E712
                        TelegramUser.trade_notifications_enabled == True,  # noqa: E712
                    )
                )
                self._telegram_chat_ids = [row[0] for row in result.all()]
                logger.info(
                    "Telegram users loaded for auto-executor notifications",
                    count=len(self._telegram_chat_ids),
                )
        except Exception as e:  # noqa: BLE001
            logger.debug("Telegram user load failed", error=str(e))
            self._telegram_chat_ids = []

    async def _notify_telegram(self, message: str, title: Optional[str] = None) -> None:
        """Broadcast a message to all registered Telegram chat IDs."""
        if not self._telegram_chat_ids or not telegram_service.enabled:
            return
        for chat_id in self._telegram_chat_ids:
            try:
                await telegram_service.send_message(
                    chat_id=chat_id, message=message, title=title
                )
            except Exception as e:  # noqa: BLE001
                logger.debug("Telegram notify failed", chat_id=chat_id[:5], error=str(e))

    async def _notify_trade_opened(self, position: PositionInfo) -> None:
        if not self._telegram_chat_ids or not telegram_service.enabled:
            return
        side_emoji = "🟢" if position.side == "buy" else "🔴"
        message = (
            f"{side_emoji} *AUTO TRADE OPENED*\n\n"
            f"Symbol: {position.symbol}\n"
            f"Side: {position.side.upper()}\n"
            f"Entry: ${position.entry_price:.2f}\n"
            f"Qty: {position.qty:.6f}\n"
            f"Notional: ${position.notional_usd:.2f}\n"
            f"Asset class: {position.asset_class}\n"
            f"Kronos confidence: {position.forecast_confidence}\n"
            f"Mode: Paper Trading"
        )
        await self._notify_telegram(message, title="🤖 Jasper Auto Executor")

    async def _notify_trade_closed(
        self, symbol: str, side: str, exit_price: float, reason: str, pnl_percent: float, pnl_usd: float
    ) -> None:
        if not self._telegram_chat_ids or not telegram_service.enabled:
            return
        emoji = "✅" if pnl_percent > 0 else ("❌" if pnl_percent < 0 else "➖")
        outcome = "WIN" if pnl_percent > 0 else ("LOSS" if pnl_percent < 0 else "BREAKEVEN")
        close_side = "sell" if side == "buy" else "buy"
        message = (
            f"{emoji} *AUTO TRADE CLOSED - {outcome}*\n\n"
            f"Symbol: {symbol}\n"
            f"Exit side: {close_side}\n"
            f"Exit price: ${exit_price:.2f}\n"
            f"Reason: {reason}\n"
            f"PnL: ${pnl_usd:.2f} ({pnl_percent:+.2f}%)\n"
            f"Mode: Paper Trading"
        )
        await self._notify_telegram(message, title="📉 Jasper Auto Executor")

    async def _send_daily_summary(self) -> None:
        """Send a daily summary to all registered Telegram users (once per UTC day)."""
        if not self._telegram_chat_ids or not telegram_service.enabled:
            return
        today = datetime.now(timezone.utc).date().isoformat()
        if self._last_summary_date == today:
            return  # already sent today

        # Aggregate PnL from resolved/experienced trades for today
        total_pnl = 0.0
        total_pnl_percent = 0.0
        wins = 0
        losses = 0
        try:
            recent = trade_monitor.exp_buffer.experiences
            today_trades = [
                e for e in recent
                if e.timestamp and e.timestamp.startswith(today)
            ]
            for e in today_trades:
                total_pnl += e.pnl
                total_pnl_percent += e.pnl_percent
                if e.outcome == "WIN":
                    wins += 1
                elif e.outcome == "LOSS":
                    losses += 1
        except Exception as e:  # noqa: BLE001
            logger.debug("daily summary aggregation failed", error=str(e))

        total_trades = wins + losses
        win_rate = (wins / total_trades * 100) if total_trades else 0.0

        message = (
            f"📅 *DAILY SUMMARY - {today}*\n\n"
            f"💰 Total PnL: ${total_pnl:+,.2f}\n"
            f"📈 Return: {total_pnl_percent:+,.2f}%\n"
            f"📊 Win Rate: {win_rate:.1f}%\n"
            f"🎯 Trades: {total_trades} (W: {wins}, L: {losses})\n"
            f"🤖 Jasper Auto Executor (Paper)"
        )
        await self._notify_telegram(message, title="📊 Jasper Daily Summary")
        self._last_summary_date = today


    # ------------------------------------------------------------------
    # Forecast resolution (score Kronos against realised prices)
    # ------------------------------------------------------------------
    async def _resolve_pending(self, movements: Dict[str, Dict[str, Any]]) -> None:
        """Convert resolved pending forecasts into ScoredForecasts for the learner."""
        still_pending: List[PendingForecast] = []
        for pf in self._pending:
            movement = movements.get(pf.symbol, {})
            price = movement.get("price")
            if price is None:
                still_pending.append(pf)
                continue

            # A forecast resolves once we have a realised price after entry.
            realised = price
            scored = ScoredForecast(
                symbol=pf.symbol,
                horizon=pf.horizon,
                interval_seconds=int(self.config.get("interval_seconds", 60)),
                confidence=pf.confidence,
                probability_up=pf.probability_up,
                last_close=pf.last_close,
                realised=realised,
            )
            self._resolved.append(scored)
            logger.debug(
                "Forecast resolved",
                symbol=pf.symbol,
                confidence=pf.confidence,
                hit=scored.hit,
                realised=realised,
            )

        self._pending = still_pending

        # Cap resolved history so fit() stays fast.
        if len(self._resolved) > 2000:
            self._resolved = self._resolved[-2000:]

    # ------------------------------------------------------------------
    # Learner refit (self-improvement)
    # ------------------------------------------------------------------
    async def _refit_learner(self) -> None:
        """Refit the strategy learner on all resolved scored forecasts."""
        try:
            state = fit(
                self._resolved,
                base_threshold=float(self.config.get("base_confidence_threshold", 70)),
                base_band_tolerance=float(self.config.get("base_band_tolerance", 0.06)),
                base_sample_penalty=float(self.config.get("base_sample_penalty", 0.0)),
            )
            self._fitted_state = state
            self._learner_sample_size = state.sample_size
            logger.info(
                "Learner refit",
                sample_size=state.sample_size,
                hit_rate=state.hit_rate,
                validated=state.validated,
                threshold=state.values.get("confidence_threshold"),
                reason=state.reason,
            )
        except Exception as e:  # noqa: BLE001
            logger.warning("Learner refit failed", error=str(e))

    def get_learner_summary(self) -> Dict[str, Any]:
        from app.services.strategy_learner import summary

        params = apply(
            self._learner_state(),
            configured_threshold=float(self.config.get("base_confidence_threshold", 70)),
            configured_band_tolerance=float(self.config.get("base_band_tolerance", 0.06)),
            configured_sample_penalty=float(self.config.get("base_sample_penalty", 0.0)),
        )
        state = self._fitted_state
        from app.services.strategy_learner import LearnedState

        if not isinstance(state, LearnedState):
            state = LearnedState()
        return summary(state, params)



# ---------------------------------------------------------------------------
# Shared top-performers helpers (used by the executor, the watchlist API and
# the agent-start flow so "Start with an empty watchlist" populates the same
# top 15 assets everywhere).
# ---------------------------------------------------------------------------

TOP_PERFORMERS_SOURCE = "top-performers"


async def build_top_performers(limit: int = 15) -> List[str]:
    """Top 24h performing assets as trading symbols (gainers first, then
    losers for shorts), deduped and capped at `limit`."""
    from app.services.market_data_providers import get_market_data_service

    result = await get_market_data_service().get_top_gainers_losers_coingecko(limit=limit)
    if not result.get("success"):
        logger.debug("Top-performers fetch failed", error=result.get("error"))
        return []
    data = result.get("data", {})
    gainers = data.get("top_gainers", []) or []
    losers = data.get("top_losers", []) or []

    top: List[str] = []
    seen = set()
    for entry in list(gainers) + list(losers):
        sym = str(entry.get("symbol") or "").strip().upper()
        if not sym or sym in seen:
            continue
        seen.add(sym)
        top.append(f"{sym}USDT" if not sym.endswith(("USDT", "USDC")) else sym)
        if len(top) >= limit:
            break
    return top


async def populate_device_watchlist(
    device_id: str, limit: int = 15, *, only_if_empty: bool = True
) -> Dict[str, Any]:
    """Populate a device's durable watchlist with the top performers.

    When `only_if_empty` is true (default) an existing watchlist is left
    untouched — the user's starred assets always win. Returns what happened.
    """
    from sqlalchemy import delete

    async with async_session() as db:
        existing = (
            await db.execute(
                select(WatchlistItem).where(WatchlistItem.device_id == device_id)
            )
        ).scalars().all()
        if only_if_empty and existing:
            return {
                "success": True,
                "populated": False,
                "reason": "watchlist_not_empty",
                "symbols": [r.symbol for r in existing],
            }

        top = await build_top_performers(limit)
        if not top:
            return {"success": False, "populated": False, "reason": "top_performers_unavailable"}

        # Replace any previous top-performers rows, then pin the fresh top 15.
        await db.execute(
            delete(WatchlistItem).where(
                WatchlistItem.device_id == device_id,
                WatchlistItem.source == TOP_PERFORMERS_SOURCE,
            )
        )
        for symbol in top[:15]:
            db.add(
                WatchlistItem(
                    device_id=device_id,
                    symbol=symbol,
                    asset_class="crypto",
                    source=TOP_PERFORMERS_SOURCE,
                )
            )
        await db.commit()
        return {"success": True, "populated": True, "symbols": top[:15], "count": len(top[:15])}


# ---------------------------------------------------------------------------
# Module singleton
# ---------------------------------------------------------------------------

_auto_executor: Optional[AutoExecutor] = None


def get_auto_executor() -> AutoExecutor:
    """Return the singleton auto-executor instance."""
    global _auto_executor
    if _auto_executor is None:
        _auto_executor = AutoExecutor()
    return _auto_executor


async def start_auto_executor(config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Lifespan warm-up: start the paper auto-executor."""
    return await get_auto_executor().start(config)


async def stop_auto_executor() -> Dict[str, Any]:
    """Lifespan shutdown: stop the auto-executor loop."""
    return await get_auto_executor().stop()

