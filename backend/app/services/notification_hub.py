"""Outbound notifications.

This app already had `telegram_service`, `notify_service` (Discord/Slack/email)
and a working `notify_trade_executed`. Rather than add a competing notifier, this
module is the shared, rate-limited, non-blocking wrapper that guarantees two
properties the existing paths lack:

- **A Telegram outage cannot fail a trade.** Sends are scheduled, never awaited
  on the execution path, and every exception is swallowed.
- **A scan loop cannot spam a user.** A per-chat sliding window caps delivery at
  20 messages/minute.

It also fills a real gap: `notify_trade_closed` existed but was never called, so
a closed position was silent even though the function was written.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections import defaultdict, deque
from typing import Any, Deque, Dict, Optional

logger = logging.getLogger(__name__)

WINDOW_SECONDS = 60.0
MAX_PER_WINDOW = 20
MAX_MESSAGE_CHARS = 4096


class NotificationHub:
    """Rate-limited wrapper over the existing channel services."""

    def __init__(self) -> None:
        self._sent: Dict[str, Deque[float]] = defaultdict(deque)
        self._dropped = 0
        self._failed = 0
        self._sent_count = 0

    def _allow(self, key: str) -> bool:
        now = time.monotonic()
        window = self._sent[key]
        while window and now - window[0] > WINDOW_SECONDS:
            window.popleft()
        if len(window) >= MAX_PER_WINDOW:
            return False
        window.append(now)
        return True

    def stats(self) -> Dict[str, int]:
        return {
            "sent": self._sent_count,
            "dropped_rate_limited": self._dropped,
            "failed": self._failed,
        }

    async def _guard(self, key: str, coro_factory) -> bool:
        """Run a channel call under the rate limit, swallowing every failure."""
        if not self._allow(key):
            self._dropped += 1
            return False
        try:
            result = await coro_factory()
            self._sent_count += 1
            return bool(result) if result is not None else True
        except Exception as exc:  # noqa: BLE001
            self._failed += 1
            logger.warning("Notification to %s failed: %s", key, exc)
            return False

    # -- trades --------------------------------------------------------------

    async def trade_executed(self, device_id: str, trade: Dict[str, Any]) -> bool:
        from app.services.telegram_service import telegram_service

        async def send() -> bool:
            chat_id = telegram_service.get_chat_id(device_id)
            if not chat_id:
                return False
            return await telegram_service.notify_trade_executed(chat_id, trade)

        return await self._guard(f"trade:{device_id}", send)

    async def trade_closed(self, device_id: str, trade: Dict[str, Any]) -> bool:
        """Announce a close.

        Previously unwired: `notify_trade_closed` was implemented but never
        invoked, so a closed position produced no notification.
        """
        from app.services.telegram_service import telegram_service

        async def send() -> bool:
            chat_id = telegram_service.get_chat_id(device_id)
            if not chat_id:
                return False
            return await telegram_service.notify_trade_closed(chat_id, trade)

        return await self._guard(f"close:{device_id}", send)

    # -- generic channels ---------------------------------------------------

    async def broadcast(self, device_id: str, title: str, message: str) -> bool:
        """Send to every configured channel via `notify_service`."""
        from app.services.notify_service import notify_service

        async def send() -> bool:
            return await notify_service.send_all_channels(title, message)

        return await self._guard(f"broadcast:{device_id}", send)

    # -- fire and forget ----------------------------------------------------

    def trade_executed_soon(self, device_id: str, trade: Dict[str, Any]) -> None:
        """Schedule a trade-open notification off the execution path."""
        self._schedule(device_id, self.trade_executed(device_id, trade))

    def trade_closed_soon(self, device_id: str, trade: Dict[str, Any]) -> None:
        """Schedule a trade-close notification off the execution path."""
        self._schedule(device_id, self.trade_closed(device_id, trade))

    def _schedule(self, key: str, coro) -> None:
        try:
            task = asyncio.create_task(coro)
            task.add_done_callback(_swallow)
        except RuntimeError:
            # No running loop. Drop rather than block: an execution must never
            # wait on a notification.
            logger.debug("No event loop; skipping notification for %s", key)


def _swallow(task: asyncio.Task) -> None:
    """Retrieve the task's exception so asyncio does not log it as unhandled."""
    try:
        task.exception()
    except asyncio.CancelledError:
        pass


hub = NotificationHub()