"""
cTrader OAuth Token Refresh Scheduler

Background service that automatically refreshes OAuth access tokens before they expire.

cTrader OAuth tokens:
- Access tokens: Valid for 30 days
- Refresh tokens: Valid indefinitely (until revoked)

This service:
1. Runs every 6 hours via APScheduler
2. Checks all connected cTrader accounts
3. Refreshes tokens expiring within 24 hours
4. Logs refresh attempts (success/failure)
5. Marks accounts as "expired" if refresh fails repeatedly

Architecture:
- Integrated with main.py lifespan manager
- Uses async scheduler for non-blocking execution
- Logs all refresh attempts to token_refresh_logs table
"""

from datetime import datetime, timedelta
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from contextlib import asynccontextmanager
import structlog

from app.models_ext.ctrader import TradingAccount, TokenRefreshLog
from app.services.ctrader_oauth import CTraderOAuthService
from app.config import settings

logger = structlog.get_logger(__name__)


class CTraderTokenRefreshScheduler:
    """
    Background scheduler for refreshing cTrader OAuth tokens.

    Runs every 6 hours to check for expiring tokens and refresh them proactively.
    """

    def __init__(self, engine):
        """
        Initialize scheduler.

        Args:
            engine: SQLAlchemy async engine for database connections
        """
        self.engine = engine
        self.oauth_service = CTraderOAuthService()
        self.refresh_interval_hours = 6
        self.expiry_threshold_hours = 24  # Refresh if <24h left

    async def refresh_expiring_tokens(self):
        """
        Check all cTrader accounts and refresh tokens expiring soon.

        This is the main task that runs on a schedule.
        """
        logger.info("Starting cTrader token refresh check...")

        async with AsyncSession(self.engine) as db:
            # Fetch all connected cTrader accounts
            result = await db.execute(
                select(TradingAccount).where(
                    TradingAccount.is_connected == True,
                    TradingAccount.connection_status == "connected",
                    TradingAccount.encrypted_access_token.isnot(None),
                    TradingAccount.encrypted_refresh_token.isnot(None),
                )
            )

            accounts = result.scalars().all()
            refreshed_count = 0
            failed_count = 0

            for account in accounts:
                try:
                    # Check if token needs refresh
                    if self._should_refresh_token(account.token_expires_at):
                        success = await self._refresh_account_token(db, account)
                        if success:
                            refreshed_count += 1
                        else:
                            failed_count += 1
                            # Mark account as needing attention
                            account.connection_status = "expired"
                            account.is_connected = False
                            await db.commit()

                except Exception as e:
                    logger.error(
                        f"Error refreshing token for account {account.id}: {e}",
                        account_id=account.id,
                    )
                    failed_count += 1

            logger.info(
                f"cTrader token refresh complete: {refreshed_count} refreshed, {failed_count} failed",
                refreshed_count=refreshed_count,
                failed_count=failed_count,
            )

    def _should_refresh_token(self, token_expires_at: datetime | None) -> bool:
        """
        Check if token should be refreshed (expires within threshold).

        Args:
            token_expires_at: When the access token expires

        Returns:
            True if refresh needed, False otherwise
        """
        if not token_expires_at:
            return True  # No expiry set, should refresh

        # Refresh if less than 24 hours remaining
        expiry_threshold = datetime.utcnow() + timedelta(hours=self.expiry_threshold_hours)
        return token_expires_at < expiry_threshold

    async def _refresh_account_token(
        self,
        db: AsyncSession,
        account: TradingAccount,
    ) -> bool:
        """
        Refresh OAuth token for a single account.

        Args:
            db: Database session
            account: TradingAccount record

        Returns:
            True if refresh successful, False otherwise
        """
        from app.services.token_encryption import decrypt_token, encrypt_token

        old_token_expires_at = account.token_expires_at

        try:
            # Decrypt refresh token
            refresh_token = decrypt_token(account.encrypted_refresh_token)

            # Request new access token
            token_data = self.oauth_service.refresh_access_token(refresh_token)

            # Encrypt new access token
            new_encrypted_access = self.oauth_service.encrypt_token(
                token_data["access_token"]
            )

            # Update account
            account.encrypted_access_token = new_encrypted_access
            account.token_expires_at = token_data["expires_at"]
            account.token_last_refreshed = datetime.utcnow()
            account.connection_status = "connected"
            account.is_connected = True

            await db.commit()

            # Log successful refresh
            log_entry = TokenRefreshLog(
                trading_account_id=account.id,
                old_token_expires_at=old_token_expires_at,
                new_token_expires_at=token_data["expires_at"],
                refresh_successful=True,
                error_message=None,
            )
            db.add(log_entry)
            await db.commit()

            logger.info(
                f"Successfully refreshed token for account {account.id}",
                account_id=account.id,
                new_expires_at=token_data["expires_at"].isoformat(),
            )

            return True

        except Exception as e:
            logger.error(
                f"Failed to refresh token for account {account.id}: {e}",
                account_id=account.id,
                error=str(e),
            )

            # Log failed refresh
            log_entry = TokenRefreshLog(
                trading_account_id=account.id,
                old_token_expires_at=old_token_expires_at,
                new_token_expires_at=old_token_expires_at,  # Unchanged
                refresh_successful=False,
                error_message=str(e),
            )
            db.add(log_entry)

            try:
                await db.commit()
            except Exception:
                pass

            return False


async def start_token_refresh_scheduler(engine):
    """
    Start the token refresh scheduler.

    This function is called from main.py lifespan manager.
    Runs token refresh every 6 hours.

    Args:
        engine: SQLAlchemy async engine
    """
    from apscheduler.schedulers.asyncio import AsyncIOScheduler

    scheduler = AsyncIOScheduler()
    refresh_service = CTraderTokenRefreshScheduler(engine)

    # Schedule token refresh every 6 hours
    scheduler.add_job(
        refresh_service.refresh_expiring_tokens,
        trigger="interval",
        hours=refresh_service.refresh_interval_hours,
        id="ctrader_token_refresh",
        name="Refresh cTrader OAuth tokens",
        replace_existing=True,
    )

    # Run immediately on startup
    await refresh_service.refresh_expiring_tokens()

    scheduler.start()

    logger.info(
        "Started cTrader token refresh scheduler",
        interval_hours=refresh_service.refresh_interval_hours,
    )

    return scheduler


@asynccontextmanager
async def token_refresh_lifespan(engine):
    """
    Lifespan context manager for token refresh scheduler.

    Usage in main.py:
        async with token_refresh_lifespan(engine) as scheduler:
            # App runs here
    """
    scheduler = await start_token_refresh_scheduler(engine)
    try:
        yield scheduler
    finally:
        scheduler.shutdown()
        logger.info("Stopped cTrader token refresh scheduler")