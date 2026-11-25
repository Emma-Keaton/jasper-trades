"""
Scheduler Service - Background tasks and scheduled job execution.
"""
from typing import Dict, Any, Optional, Callable, Awaitable
from datetime import datetime, timedelta
import asyncio
import structlog

from app.services.portfolio_service import PortfolioService
from app.services.valuation_service import ValuationService
from app.services.signal_service import SignalService
from sqlalchemy import select
from app.models import SignalSource, TelegramAccount
from app.services.signal_sources.registry import get_registry
from app.services.signal_sources.ingest import extract_and_ingest, maybe_auto_execute

logger = structlog.get_logger(__name__)


class SchedulerService:
    """
    Scheduler Service - Manages background tasks and scheduled jobs.

    Scheduled Tasks:
    - Every 1 minute: Update position prices
    - Every 5 minutes: Agent signal generation
    - Every hour: Signal expiration check
    - Daily (market close): PnL calculation
    - Daily (end of day): Cleanup
    """

    def __init__(self, db_session_factory):
        self.db_session_factory = db_session_factory
        self._tasks: Dict[str, asyncio.Task] = {}
        self._running = False
        self._intervals: Dict[str, int] = {
            "update_prices": 60,  # 1 minute
            "generate_signals": 300,  # 5 minutes
            "expire_signals": 3600,  # 1 hour
            "calculate_pnl": 86400,  # 24 hours
            "cleanup": 86400,  # 24 hours
            "daily_summary": 86400,  # 24 hours - runs at 8 PM WAT (7 PM UTC)
            "poll_signal_sources": 120,  # every 2 minutes
            # Kronos predicts but never learns. Scoring recorded predictions
            # against realised prices is the feedback loop that makes
            # `confidence` trustworthy enough to gate trades.
            "score_kronos": 900,  # every 15 minutes
            # Refitting on every scoring pass would rewrite the parameter history
            # constantly for barely any movement in the gates. Hourly keeps the
            # workspace-global thresholds current without churn.
            "refit_learned": 3600,  # hourly
            # Self-evolution: architect proposes + retires strategies every 6h.
            "strategy_evolve": 21600,  # 6 hours
            # Whale pipeline fallback when no Helius webhook is configured.
            "whale_fallback": 300,  # every 5 minutes
        }
        self._daily_summary_time = "19:00"  # 7 PM UTC = 8 PM WAT
        self._last_runs: Dict[str, Any] = {}  # task -> {ts, ok, error, detail}

    async def start(self):
        """Start all scheduled tasks."""
        if self._running:
            logger.warning("Scheduler already running")
            return

        self._running = True
        logger.info("Starting scheduler service")

        # Start tasks
        self._tasks["update_prices"] = asyncio.create_task(
            self._run_periodic("update_prices", self._update_position_prices)
        )

        self._tasks["generate_signals"] = asyncio.create_task(
            self._run_periodic("generate_signals", self._generate_signals)
        )

        self._tasks["expire_signals"] = asyncio.create_task(
            self._run_periodic("expire_signals", self._expire_signals)
        )

        self._tasks["calculate_pnl"] = asyncio.create_task(
            self._run_periodic("calculate_pnl", self._calculate_pnl)
        )

        self._tasks["daily_summary"] = asyncio.create_task(
            self._run_daily_at_time("daily_summary", self._send_daily_summaries, self._daily_summary_time)
        )

        self._tasks["poll_signal_sources"] = asyncio.create_task(
            self._run_periodic("poll_signal_sources", self._poll_signal_sources)
        )

        self._tasks["score_kronos"] = asyncio.create_task(
            self._run_periodic("score_kronos", self._score_kronos_forecasts)
        )

        # Refitting on every scoring pass would rewrite the parameter history
        # constantly for barely any movement in the gates; hourly keeps the global
        # thresholds current without churn.
        self._tasks["refit_learned"] = asyncio.create_task(
            self._run_periodic("refit_learned", self._refit_learned_parameters)
        )

        self._tasks["cleanup"] = asyncio.create_task(
            self._run_periodic("cleanup", self._cleanup)
        )

        self._tasks["strategy_evolve"] = asyncio.create_task(
            self._run_periodic("strategy_evolve", self._strategy_evolve)
        )

        self._tasks["whale_fallback"] = asyncio.create_task(
            self._run_periodic("whale_fallback", self._whale_fallback_dispatch)
        )

        logger.info(f"Started {len(self._tasks)} scheduled tasks")

    async def stop(self):
        """Stop all scheduled tasks."""
        if not self._running:
            return

        self._running = False
        logger.info("Stopping scheduler service")

        # Cancel all tasks
        for name, task in self._tasks.items():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        self._tasks.clear()
        logger.info("Scheduler stopped")

    async def _run_periodic(self, name: str, func: Callable[[], Awaitable[None]]):
        """Run a function periodically."""
        interval = self._intervals.get(name, 60)

        while self._running:
            try:
                await asyncio.sleep(interval)

                if not self._running:
                    break

                logger.debug(f"Running scheduled task: {name}")
                from datetime import datetime, timezone

                try:
                    detail = await func()
                    self._last_runs[name] = {
                        "ts": datetime.now(timezone.utc).isoformat(),
                        "ok": True, "error": None, "detail": detail,
                    }
                except Exception as e:  # noqa: BLE001
                    self._last_runs[name] = {
                        "ts": datetime.now(timezone.utc).isoformat(),
                        "ok": False, "error": str(e)[:200], "detail": None,
                    }
                    raise

            except asyncio.CancelledError:
                logger.debug(f"Task cancelled: {name}")
                break
            except Exception as e:
                logger.error(f"Scheduled task error ({name}): {e}")
                await asyncio.sleep(10)  # Wait before retry on error

    async def _run_daily_at_time(self, name: str, func: Callable[[], Awaitable[None]], time_str: str):
        """Run a function daily at a specific time (HH:MM format)."""
        if not self._running:
            return

        # Parse target time
        try:
            hour, minute = map(int, time_str.split(":"))
        except ValueError:
            logger.error(f"Invalid time format for {name}: {time_str}")
            return

        logger.info(f"Scheduled task {name} to run daily at {time_str} UTC")

        while self._running:
            try:
                now = datetime.utcnow()
                target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)

                # If target time already passed today, schedule for tomorrow
                if now >= target:
                    target = target + timedelta(days=1)

                # Calculate sleep duration
                sleep_seconds = (target - now).total_seconds()

                logger.debug(f"Next {name} run in {sleep_seconds:.0f}s at {target}")

                await asyncio.sleep(sleep_seconds)

                if not self._running:
                    break

                logger.info(f"Running scheduled task: {name}")
                await func()

            except asyncio.CancelledError:
                logger.debug(f"Task cancelled: {name}")
                break
            except Exception as e:
                logger.error(f"Scheduled task error ({name}): {e}")
                await asyncio.sleep(60)  # Wait 1 min before retry

    # ========== Scheduled Jobs ==========

    async def _update_position_prices(self):
        """Update current prices for all positions."""
        try:
            db = self.db_session_factory()
            portfolio_service = PortfolioService(db)
            valuation_service = ValuationService()

            # Get all portfolios
            portfolios = await portfolio_service.get_portfolios()

            updated_count = 0
            for portfolio in portfolios:
                positions = await portfolio_service.get_all_positions(portfolio.id)

                if positions:
                    prices = await valuation_service.get_prices([p.symbol for p in positions])
                    await portfolio_service.update_position_prices(portfolio.id, prices)
                    updated_count += len(positions)

            await db.close()

            logger.debug(f"Updated prices for {updated_count} positions")

        except Exception as e:
            logger.error(f"Error updating prices: {e}")

    async def _generate_signals(self):
        """Generate signals from the Alpha Zoo factor consensus on watchlists."""
        try:
            from app.services.factor_trading import run_factor_sweep

            db = self.db_session_factory()
            try:
                stats = await run_factor_sweep(db)
                logger.info(
                    "Signal generation complete",
                    enabled=stats.get("enabled"),
                    traded=stats.get("traded", 0),
                    skipped=stats.get("skipped", 0),
                )
            finally:
                await db.close()

        except Exception as e:
            logger.error(f"Error generating signals: {e}", exc_info=True)

    async def _score_kronos_forecasts(self):
        """Score recorded Kronos predictions against realised prices.

        Kronos is a forecaster, not a learner. Until something measures its output
        against what actually happened, `confidence` is an unverified number that
        gates trades.
        """
        try:
            from app.services.kronos_remote import kronos_client
            scored = await kronos_client.score_pending()
            if scored:
                logger.info("Scored %d Kronos forecasts", len(scored))
            summary = await kronos_client.calibration_summary()
            if summary.get("scored"):
                logger.info("Kronos calibration: %s", summary)
        except Exception as e:  # noqa: BLE001
            logger.warning("Kronos scoring pass failed: %s", e)

    async def _refit_learned_parameters(self):
        """Refit global thresholds and promote a model on accumulated evidence.

        Learned parameters and the active model are workspace-global, so this runs
        once for the whole workspace rather than per device: every device's scored
        trades count toward the same estimate. Promotion is still gated on a
        statistically significant record, so an early run cannot install a model on
        noise.
        """
        try:
            from app.services.kronos_remote import kronos_client

            outcome = await kronos_client.refit()
        except Exception as e:  # noqa: BLE001
            logger.warning("Learned-parameter refit failed: %s", e)
            return
        logger.info(
            "Refit: %s samples, validated=%s, promoted=%s (%s)",
            outcome.get("sample_size"),
            outcome.get("validated"),
            outcome.get("promoted_model") if outcome.get("promoted") else None,
            outcome.get("reason"),
        )

    def status(self) -> Dict[str, Any]:
        """Task registry + last-run outcome for the pipeline-status endpoint."""
        return {
            "running": self._running,
            "tasks": {
                name: {
                    "interval_s": self._intervals.get(name),
                    "active": name in self._tasks and not self._tasks[name].done(),
                    "last_run": self._last_runs.get(name),
                }
                for name in self._tasks
            },
        }

    async def _strategy_evolve(self) -> Dict[str, Any]:
        """Periodic self-evolution: architect proposes a new strategy per started
        device and retires active strategies whose live hit-rate has decayed."""
        from app.services.strategy_suite import StrategySuiteService
        from app.services.factor_trading import _is_agents_started

        db = self.db_session_factory()
        out: Dict[str, Any] = {"proposed": 0, "retired": 0, "devices": 0}
        try:
            from sqlalchemy import select as _select
            from app.models import DeviceSettings, StrategyRecord

            rows = (await db.execute(_select(DeviceSettings))).scalars().all()
            for row in rows:
                if not await _is_agents_started(db, row.device_id):
                    continue
                out["devices"] += 1
                suite = StrategySuiteService(db)
                try:
                    proposal = await suite.propose_strategy(row.device_id)
                    if proposal.get("success"):
                        out["proposed"] += 1
                except Exception as e:  # noqa: BLE001
                    logger.warning("evolve propose failed", device=row.device_id, error=str(e)[:120])
                # Auto-retire active strategies with enough samples and a losing record.
                for s in await suite.list_strategies(row.device_id):
                    if (
                        s["status"] == "active"
                        and (s.get("sample_size") or 0) >= 30
                        and (s.get("hit_rate") or 1.0) < 0.45
                    ):
                        await suite.set_status(row.device_id, s["id"], "retired")
                        out["retired"] += 1
            await db.commit()
        except Exception as e:  # noqa: BLE001
            logger.warning("strategy_evolve failed: %s", e)
            raise
        finally:
            await db.close()
        logger.info("Strategy evolution pass", **out)
        return out

    async def _whale_fallback_dispatch(self) -> Dict[str, Any]:
        """Whale pipeline fallback when no Helius webhook is configured: keep
        exits managed and surface recent events. (Webhook is the primary feed;
        DexScreener whale-bucket autotrade runs in the dexchain watcher.)"""
        from app.config import settings
        from app.services.solana_whale_service import last_events, manage_whale_exits

        exits = await manage_whale_exits()
        return {
            "helius_webhook": bool(settings.HELIUS_API_KEY),
            "exits": exits,
            "recent_events": len(last_events(100)),
        }

    async def _poll_signal_sources(self):
        """Poll all active signal sources for every device and ingest tips."""
        db = self.db_session_factory()
        try:
            from sqlalchemy import distinct
            rows = await db.execute(select(distinct(SignalSource.device_id)).where(SignalSource.is_active == True))
            device_ids = [r for r in rows.scalars().all()]
            for device_id in device_ids:
                try:
                    await self._poll_one_device(db, device_id)
                except Exception as e:  # noqa: BLE001
                    logger.warning("Poll device failed", device=device_id, error=str(e))
        except Exception as e:  # noqa: BLE001
            logger.error(f"Poll signal sources error: {e}")
        finally:
            await db.close()

    async def _poll_one_device(self, db, device_id: str):
        res = await db.execute(select(SignalSource).where(SignalSource.device_id == device_id, SignalSource.is_active == True))
        sources = res.scalars().all()
        if not sources:
            return 0
        tmpl = {}
        acc_res = await db.execute(select(TelegramAccount).where(TelegramAccount.device_id == device_id))
        acc = acc_res.scalar_one_or_none()
        if acc:
            tmpl = {"tg_session": acc.tg_session or ""}
        cfg_list = []
        for s in sources:
            cfg = {"source_type": s.source_type, "source_id": str(s.id), **(s.config or {})}
            if s.source_type == "telegram":
                cfg.update(tmpl)
            cfg_list.append(cfg)

        reg = get_registry()
        drafts = await reg.fetch_all(cfg_list, limit=50)
        saved = await extract_and_ingest(db, device_id, drafts)
        for sig in saved:
            await maybe_auto_execute(db, device_id, sig)
        if saved:
            await db.commit()
            logger.info("Signal sources polled", device=device_id, new_tips=len(saved))
        return len(saved)

    async def _expire_signals(self):
        """Check and mark expired signals."""
        try:
            db = self.db_session_factory()
            signal_service = SignalService(db)

            expired = await signal_service.expire_signals()

            await db.close()

            if expired > 0:
                logger.info(f"Marked {expired} signals as expired")

        except Exception as e:
            logger.error(f"Error expiring signals: {e}")

    async def _calculate_pnl(self):
        """Calculate daily PnL for all portfolios and persist a snapshot."""
        try:
            from datetime import datetime
            from app.models import PortfolioSnapshot
            from app.services.valuation_service import ValuationService

            db = self.db_session_factory()
            portfolio_service = PortfolioService(db)
            valuation_service = ValuationService()

            portfolios = await portfolio_service.get_portfolios()
            today = datetime.utcnow().strftime("%Y-%m-%d")

            for portfolio in portfolios:
                pnl = await portfolio_service.get_pnl(portfolio.id)
                positions = await portfolio_service.get_all_positions(portfolio.id)

                # Get current market value
                market_value = 0.0
                if positions:
                    prices = await valuation_service.get_prices([p.symbol for p in positions])
                    for pos in positions:
                        price = prices.get(pos.symbol, pos.current_price or pos.avg_price)
                        market_value += pos.quantity * (price or 0)

                total_value = portfolio.cash + market_value

                # Upsert snapshot for today
                from sqlalchemy import select
                result = await db.execute(
                    select(PortfolioSnapshot).where(
                        PortfolioSnapshot.portfolio_id == portfolio.id,
                        PortfolioSnapshot.snapshot_date == today,
                    )
                )
                snap = result.scalar_one_or_none()
                if snap:
                    snap.total_value = total_value
                    snap.cash = portfolio.cash
                    snap.market_value = market_value
                    snap.unrealized_pnl = pnl.get("unrealized_pnl", 0)
                    snap.realized_pnl = pnl.get("realized_pnl", 0)
                else:
                    snap = PortfolioSnapshot(
                        portfolio_id=portfolio.id,
                        device_id=portfolio.device_id,
                        snapshot_date=today,
                        total_value=total_value,
                        cash=portfolio.cash,
                        market_value=market_value,
                        unrealized_pnl=pnl.get("unrealized_pnl", 0),
                        realized_pnl=pnl.get("realized_pnl", 0),
                    )
                    db.add(snap)

                logger.info(
                    f"Portfolio {portfolio.name} PnL",
                    realized=pnl["realized_pnl"],
                    unrealized=pnl["unrealized_pnl"],
                    total=pnl["total_pnl"],
                    snapshot_saved=True,
                )

            await db.commit()
            await db.close()

        except Exception as e:
            logger.error(f"Error calculating PnL: {e}")

    async def _send_daily_summaries(self):
        """Generate and send daily summaries at 8 PM WAT (7 PM UTC)."""
        try:
            from app.services.daily_summary_service import DailySummaryService
            from app.models import Portfolio, TelegramUser
            from sqlalchemy import select

            db = self.db_session_factory()
            
            # Get yesterday's date (summary is for completed trading day)
            yesterday = (datetime.utcnow() - timedelta(days=1)).strftime("%Y-%m-%d")
            
            logger.info(f"Generating daily summaries for {yesterday}")

            # Get all portfolios
            portfolio_query = select(Portfolio)
            portfolios_result = await db.execute(portfolio_query)
            portfolios = list(portfolios_result.scalars().all())

            summaries_generated = 0
            summaries_sent = 0

            for portfolio in portfolios:
                # Generate summary for this portfolio
                summary_service = DailySummaryService(db)
                summary = await summary_service.generate_summary(
                    portfolio_id=portfolio.id,
                    device_id=portfolio.device_id,
                    date=yesterday,
                )

                if summary:
                    summaries_generated += 1
                    
                    # Check if user wants daily summary
                    user_query = select(TelegramUser).where(
                        TelegramUser.device_id == portfolio.device_id,
                        TelegramUser.daily_summary_enabled == True,
                    )
                    user_result = await db.execute(user_query)
                    user = user_result.scalar_one_or_none()

                    if user and user.is_verified:
                        # Send immediately
                        success = await summary_service.send_summary(summary)
                        if success:
                            summaries_sent += 1

            await db.close()

            logger.info(
                f"Daily summaries complete",
                generated=summaries_generated,
                sent=summaries_sent,
            )

        except Exception as e:
            logger.error(f"Error sending daily summaries: {e}", exc_info=True)

    async def _cleanup(self):
        """Daily cleanup: purge expired tips, old snapshots, stale cache entries."""
        try:
            from datetime import datetime, timedelta
            from app.models import SignalTip, PortfolioSnapshot
            from sqlalchemy import delete

            db = self.db_session_factory()
            try:
                cutoff = datetime.utcnow() - timedelta(days=90)

                # Purge expired / old signal tips
                result = await db.execute(
                    delete(SignalTip).where(SignalTip.created_at < cutoff)
                )
                tips_purged = result.rowcount

                # Purge old portfolio snapshots (keep 1 year)
                snap_cutoff = datetime.utcnow() - timedelta(days=365)
                result = await db.execute(
                    delete(PortfolioSnapshot).where(PortfolioSnapshot.created_at < snap_cutoff)
                )
                snaps_purged = result.rowcount

                await db.commit()

                if tips_purged or snaps_purged:
                    logger.info(
                        "Cleanup complete",
                        tips_purged=tips_purged,
                        snapshots_purged=snaps_purged,
                    )
            finally:
                await db.close()

        except Exception as e:
            logger.error(f"Error during cleanup: {e}", exc_info=True)

    # ========== Task Status ==========

    def get_status(self) -> Dict[str, Any]:
        """Get scheduler status."""
        return {
            "running": self._running,
            "tasks": {
                name: {
                    "interval": interval,
                    "running": name in self._tasks and not self._tasks[name].done(),
                }
                for name, interval in self._intervals.items()
            },
            "active_tasks": len([t for t in self._tasks.values() if not t.done()]),
        }

    def set_interval(self, task_name: str, interval_seconds: int) -> bool:
        """
        Update task interval.

        Args:
            task_name: Task name
            interval_seconds: New interval in seconds

        Returns:
            True if updated
        """
        if task_name not in self._intervals:
            return False

        self._intervals[task_name] = interval_seconds
        logger.info(f"Updated {task_name} interval to {interval_seconds}s")
        return True


# Global scheduler instance
scheduler: Optional[SchedulerService] = None


def get_scheduler() -> Optional[SchedulerService]:
    """Get global scheduler instance."""
    return scheduler


def init_scheduler(db_session_factory) -> SchedulerService:
    """Initialize global scheduler."""
    global scheduler
    scheduler = SchedulerService(db_session_factory)
    return scheduler
