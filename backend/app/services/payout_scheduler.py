"""
Auto-Payout Scheduler - CRYPTO WALLET & NAIRA BANK PAYOUTS

Background scheduler for automated profit distribution.
Runs every hour, checks if portfolios should execute auto-payout.

Payout Destinations:
1. Crypto Wallet (USDT sent directly on-chain; see `app/services/payout_rail.py`)
2. Nigerian Bank Account (NGN via Paystack/Flutterwave + Trove)

Configuration (encrypted JSON in DeviceSettings):
{
    "payout_enabled": true,
    "payout_percentage": 50.0,  // Configurable: 0-100
    "payout_schedule_hour": 20,  // 0-23 WAT (Africa/Lagos)
    "payout_schedule_minute": 0,
    "payout_frequency": "custom_time",  // or "end_of_trade"
    "payout_chain": "tron",  // tron | bsc | polygon | ethereum | solana
    "crypto_wallet": "T...",  // USDT address on the selected network
    "min_payout_threshold": 10.0  // Minimum profit before payout
}

For Naira bank payouts, also requires:
{
    "naira_bank_enabled": true,
    "bank_account_number": "0123456789",
    "bank_code": "058",  # Nigerian bank code
    "account_name": "John Doe",
    "bank_name": "Guaranty Trust Bank"
}
"""
import asyncio
import structlog
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import pytz

from app.database import async_session
from app.models import Portfolio, DeviceSettings
from app.services.withdrawal_service import WithdrawalService
from sqlalchemy import select

logger = structlog.get_logger(__name__)


class PayoutScheduler:
    """
    Flexible Auto-Payout Scheduler with multiple destination support.
    
    Destination logic:
    1. crypto_wallet -> USDT to an external wallet, signed locally
    """

    def __init__(self):
        self.is_running = False
        self._task: Optional[asyncio.Task] = None
        self.wat_timezone = pytz.timezone('Africa/Lagos')  # WAT = UTC+1

    async def start(self):
        """Start the background scheduler."""
        if self.is_running:
            logger.warning("Payout scheduler already running")
            return

        logger.info("Starting auto-payout scheduler (checking every hour)")
        self.is_running = True
        self._task = asyncio.create_task(self._run_scheduler())

    async def stop(self):
        """Stop the background scheduler."""
        if not self.is_running:
            return

        logger.info("Stopping auto-payout scheduler")
        self.is_running = False

        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def _run_scheduler(self):
        """Main scheduler loop - check every hour."""
        while self.is_running:
            try:
                await self._check_and_execute_payouts()
            except Exception as e:
                logger.error(f"Payout scheduler error: {e}")

            # Wait 1 hour
            await asyncio.sleep(3600)

    async def _check_and_execute_payouts(self):
        """
        Check all portfolios and execute auto-payouts if conditions met.

        Conditions:
        1. Payout enabled
        2. Current hour (ET) matches scheduled hour
        3. Positive daily profit above threshold
        4. Hasn't paid out today
        """
        now_wat = datetime.now(self.wat_timezone)
        current_hour_wat = now_wat.hour
        current_minute_wat = now_wat.minute

        logger.debug(f"Payout scheduler check - current WAT: {current_hour_wat}:{current_minute_wat:02d}")

        async with async_session() as session:
            settings_query = select(DeviceSettings).where(
                DeviceSettings.payout_config.isnot(None)
            )
            settings_result = await session.execute(settings_query)
            settings_list = list(settings_result.scalars().all())

            executed_count = 0
            skipped_count = 0
            total_count = len(settings_list)

            for settings in settings_list:
                try:
                    from app.services.encryption import EncryptionHelper
                    encryption = EncryptionHelper()
                    payout_config = encryption.decrypt_json(settings.payout_config)
                    if not payout_config:
                        continue

                    if not payout_config.get("payout_enabled", False):
                        skipped_count += 1
                        continue

                    # End-of-trade mode is handled in paper_trading_service; skip daily pass
                    if payout_config.get("payout_frequency") == "end_of_trade":
                        skipped_count += 1
                        continue

                    scheduled_hour = payout_config.get("payout_schedule_hour", 20)
                    scheduled_minute = payout_config.get("payout_schedule_minute", 0)
                    if current_hour_wat != scheduled_hour or current_minute_wat != scheduled_minute:
                        continue

                    # Get portfolio for this device's settings
                    #
                    # This previously did `select(Portfolio).limit(1)`, so every
                    # device's payout configuration was evaluated against the
                    # first portfolio in the database. On a multi-device
                    # deployment that paid the wrong portfolio's profit to the
                    # wrong wallet. Match on the device instead.
                    portfolios_query = select(Portfolio).where(
                        Portfolio.device_id == settings.device_id
                    )
                    portfolios_result = await session.execute(portfolios_query)
                    portfolios = list(portfolios_result.scalars().all())

                    if not portfolios:
                        logger.warning(
                            "No portfolio for device %s; skipping payout",
                            settings.device_id,
                        )
                        skipped_count += 1
                        continue

                    # A device may legitimately hold several portfolios (one per
                    # broker), and each has its own profit. Payout every one of
                    # them rather than silently paying only the first.
                    for portfolio in portfolios:
                        withdrawal_service = WithdrawalService(session)
                        result = await withdrawal_service.execute_auto_payout(
                            portfolio.id,
                            payout_config,
                        )

                        if result:
                            executed_count += 1
                            logger.info(
                                f"Auto-payout executed for portfolio {portfolio.id}",
                                amount=result.amount,
                                daily_pnl=result.daily_pnl,
                                destination=result.destination_type,
                                payout_type=result.withdrawal_type,
                            )
                        else:
                            skipped_count += 1

                except Exception as e:
                    logger.error(
                        f"Error checking payout for settings: {e}",
                        exc_info=True
                    )
                    continue

            if total_count > 0:
                logger.info(
                    f"Auto-payout check complete - {executed_count} executed, {skipped_count} skipped, {total_count} total",
                )

    async def execute_immediate_payout(
        self,
        portfolio_id: int,
        payout_config: Optional[Dict] = None,
    ) -> bool:
        """
        Execute auto-payout immediately (for testing or manual trigger).

        Args:
            portfolio_id: Portfolio ID
            payout_config: Optional config override

        Returns:
            True if payout executed, False otherwise
        """
        async with async_session() as session:
            # Get settings if config not provided
            if not payout_config:
                settings_result = await session.execute(select(DeviceSettings).limit(1))
                settings = settings_result.scalar_one_or_none()
                if settings and settings.payout_config:
                    from app.services.encryption import EncryptionHelper
                    encryption = EncryptionHelper()
                    payout_config = encryption.decrypt_json(settings.payout_config)
            
            if not payout_config:
                logger.warning("No payout config available")
                return False

            withdrawal_service = WithdrawalService(session)
            result = await withdrawal_service.execute_auto_payout(portfolio_id, payout_config)
            return result is not None

    def get_status(self) -> dict:
        """Get scheduler status."""
        now_wat = datetime.now(self.wat_timezone)
        return {
            "is_running": self.is_running,
            "current_hour_wat": now_wat.hour,
            "current_time_wat": now_wat.strftime("%Y-%m-%d %H:%M:%S %Z"),
            "next_check": "Within 1 hour",
        }


# Singleton instance
payout_scheduler = PayoutScheduler()


def get_payout_scheduler() -> PayoutScheduler:
    """Get the payout scheduler instance."""
    return payout_scheduler