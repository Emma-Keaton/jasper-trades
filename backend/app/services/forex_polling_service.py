"""
Forex Polling Service - Real-Time NGN/USD Rate Updates

Polls Trove API (or Alpha Vantage fallback) every 60 seconds for forex rates.
Broadcasts updates via WebSocket to frontend.

Features:
- 60-second polling interval (user-requested)
- Trove API primary, Alpha Vantage fallback
- WebSocket broadcast to "forex_rates" room
- Rate caching with timestamp
- Background scheduler integration
"""
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
import asyncio
import structlog

from app.database import async_session
from app.models import DeviceSettings
from app.services.encryption import EncryptionHelper
from app.services.market_data_providers import get_market_data_service
from app.api.websocket.streams import publish_forex_update

logger = structlog.get_logger(__name__)


class ForexPollingService:
    """
    Forexe rate polling service.

    Polls forex rates every 60 seconds and broadcasts via WebSocket.
    """

    def __init__(self):
        self.is_running = False
        self.polling_interval = 60  # seconds (as per user request)
        self._task: Optional[asyncio.Task] = None
        self._last_rates: Dict[str, Any] = {}
        self._last_update: Optional[datetime] = None

        # Currency pairs to track
        self.pairs = [
            ("NGN", "USD"),  # Nigerian Naira to USD (primary)
            ("USD", "NGN"),  # USD to Naira
            ("EUR", "USD"),  # Major pairs
            ("GBP", "USD"),
            ("USD", "JPY"),
        ]

    async def start(self):
        """Start the forex polling service."""
        if self.is_running:
            logger.warning("Forex polling service already running")
            return

        self.is_running = True
        self._task = asyncio.create_task(self._polling_loop())
        logger.info(f"Forex polling service started (interval: {self.polling_interval}s)")

    async def stop(self):
        """Stop the forex polling service."""
        self.is_running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Forex polling service stopped")

    async def _polling_loop(self):
        """Main polling loop - runs every 60 seconds."""
        while self.is_running:
            try:
                await self._fetch_and_broadcast_rates()
                await asyncio.sleep(self.polling_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Forex polling error: {e}")
                # Wait before retrying on error
                await asyncio.sleep(30)

    async def _fetch_and_broadcast_rates(self):
        """Fetch rates from API and broadcast via WebSocket."""
        # Load Trove settings
        trove_api_key = None
        trove_base_url = None
        trove_enabled = False

        try:
            async with async_session() as session:
                result = await session.execute(
                    DeviceSettings.__table__.select()
                    .where(DeviceSettings.trove_enabled == True)
                    .limit(1)
                )
                settings = result.scalar_one_or_none()

                if settings and settings.trove_api_key:
                    trove_enabled = True
                    encryption = EncryptionHelper()
                    trove_api_key = encryption.decrypt(settings.trove_api_key)
                    trove_base_url = settings.trove_base_url
        except Exception as e:
            logger.warning(f"Failed to load Trove settings: {e}")

        # Fetch rates
        market_data = get_market_data_service()
        rates = {}

        for from_curr, to_curr in self.pairs:
            pair_key = f"{from_curr}/{to_curr}"

            # Try Trove first
            if trove_enabled and trove_api_key and trove_base_url:
                result = await market_data._get_forex_rate_trove(
                    from_curr, to_curr, trove_api_key, trove_base_url
                )
                if result.get('success'):
                    rates[pair_key] = result['data']
                    continue

            # Fallback to Alpha Vantage
            result = await market_data.get_forex_rate_alphavantage(from_curr, to_curr)
            if result.get('success'):
                rates[pair_key] = result['data']

        # Update state
        if rates:
            self._last_rates = rates
            self._last_update = datetime.utcnow()

            # Broadcast via WebSocket
            await publish_forex_update({
                "rates": rates,
                "timestamp": self._last_update.isoformat(),
                "source": "trove" if trove_enabled else "alphavantage",
            })

            logger.info(
                f"Forex rates updated: NGN/USD = {rates.get('NGN/USD', {}).get('rate', 'N/A')}",
            )

    def get_latest_rates(self) -> Dict[str, Any]:
        """Get the latest cached forex rates."""
        return self._last_rates.copy()

    def get_last_update(self) -> Optional[datetime]:
        """Get the timestamp of the last update."""
        return self._last_update

    def get_rate(self, from_currency: str, to_currency: str) -> Optional[float]:
        """Get a specific exchange rate."""
        pair_key = f"{from_currency}/{to_currency}"
        rate_data = self._last_rates.get(pair_key)
        if rate_data:
            return rate_data.get('rate')
        return None


# Singleton instance
_forex_polling_service: Optional[ForexPollingService] = None


def get_forex_polling_service() -> ForexPollingService:
    """Get the forex polling service instance."""
    global _forex_polling_service
    if _forex_polling_service is None:
        _forex_polling_service = ForexPollingService()
    return _forex_polling_service


async def start_forex_polling():
    """Start the forex polling service on application startup."""
    service = get_forex_polling_service()
    await service.start()


async def stop_forex_polling():
    """Stop the forex polling service on application shutdown."""
    service = get_forex_polling_service()
    await service.stop()