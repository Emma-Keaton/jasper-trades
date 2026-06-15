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
from app.agents import agent_registry

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
        }
        self._daily_summary_time = "19:00"  # 7 PM UTC = 8 PM WAT

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
                await func()

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
        """Generate new signals from active agents."""
        try:
            db = self.db_session_factory()
            signal_service = SignalService(db)

            # Get active agents
            active_agents = agent_registry.get_active()

            generated_count = 0
            for agent_name in active_agents:
                # Each agent generates signals based on its strategy
                logger.debug(f"Agent {agent_name} generating signals")
                # Agents generate signals via their analyze() method
                # Would call agent.analyze() and agent.generate_signal()

            await db.close()

            logger.info(f"Generated {generated_count} new signals")

        except Exception as e:
            logger.error(f"Error generating signals: {e}", exc_info=True)

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
        """Calculate daily PnL for all portfolios."""
        try:
            db = self.db_session_factory()
            portfolio_service = PortfolioService(db)

            portfolios = await portfolio_service.get_portfolios()

            for portfolio in portfolios:
                pnl = await portfolio_service.get_pnl(portfolio.id)

                logger.info(
                    f"Portfolio {portfolio.name} PnL",
                    realized=pnl["realized_pnl"],
                    unrealized=pnl["unrealized_pnl"],
                    total=pnl["total_pnl"],
                )

            await db.close()

        except Exception as e:
            logger.error(f"Error calculating PnL: {e}")

    async def _send_daily_summaries(self):
        """Generate and send daily summaries at 8 PM WAT (7 PM UTC)."""
        try:
            from app.services.daily_summary_service import DailySummaryService
            from app.models import Portfolio, WhatsappUser
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
                    user_query = select(WhatsappUser).where(
                        WhatsappUser.device_id == portfolio.device_id,
                        WhatsappUser.daily_summary_enabled == True,
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