"""Real-time Telegram listener (auto-receive) per device.

For every connected ``TelegramAccount`` we keep ONE Telethon client running
``events.NewMessage(incoming=True)``. Messages whose chat is a followed
``telegram`` SignalSource get pushed through the shared ingest +
auto-execution pipeline instantly, instead of waiting for the 120s scheduler
poll (which stays as a safety-net fallback; slug dedupe prevents duplicates).

Lifecycle (all re-entrant / idempotent):
    get_listener().start(device_id)   -> on connect complete / app startup
    get_listener().sync(device_id)    -> after follow/unfollow/delete/connect
    get_listener().stop(device_id)    -> on telegram disconnect / shutdown
"""
from __future__ import annotations

import asyncio
from typing import Any, Dict, Optional, Set

import structlog
from sqlalchemy import select
from telethon import TelegramClient, events
from telethon.sessions import StringSession

from app.database import async_session
from app.models import SignalSource, TelegramAccount

from .base import SignalDraft
from .ingest import extract_and_ingest, maybe_auto_execute

logger = structlog.get_logger(__name__)

_MESSAGE_TEXT_LIMIT = 3000


class TelegramListenerManager:
    """Manages one long-lived Telethon client per connected device."""

    def __init__(self) -> None:
        self._clients: Dict[str, TelegramClient] = {}
        self._tasks: Dict[str, asyncio.Task] = {}
        self._followed: Dict[str, Set[int]] = {}
        self._lock = asyncio.Lock()

    # ---- public API ----

    async def start(self, device_id: str) -> bool:
        """Start (or refresh) the live listener for one device."""
        async with self._lock:
            return await self._ensure(device_id)

    async def sync(self, device_id: str) -> bool:
        """Reload followed chats and (re)start the listener for a device."""
        async with self._lock:
            await self._stop_client(device_id)
            return await self._ensure(device_id)

    async def stop(self, device_id: str) -> None:
        """Stop a device's listener (idempotent)."""
        async with self._lock:
            await self._stop_client(device_id)

    async def stop_all(self) -> None:
        for device_id in list(self._tasks):
            await self.stop(device_id)

    def is_running(self, device_id: str) -> bool:
        client = self._clients.get(device_id)
        task = self._tasks.get(device_id)
        return bool(client and client.is_connected() and task and not task.done())

    def followed_count(self, device_id: str) -> int:
        return len(self._followed.get(device_id, set()))

    # ---- internals ----

    async def _ensure(self, device_id: str) -> bool:
        if self.is_running(device_id):
            return True
        await self._stop_client(device_id)

        async with async_session() as db:
            acc_res = await db.execute(
                select(TelegramAccount).where(TelegramAccount.device_id == device_id)
            )
            acc = acc_res.scalar_one_or_none()
            if not acc or not acc.tg_session:
                return False

            src_res = await db.execute(
                select(SignalSource).where(
                    SignalSource.device_id == device_id,
                    SignalSource.source_type == "telegram",
                    SignalSource.is_active == True,  # noqa: E712
                )
            )
            chat_ids: Set[int] = set()
            for s in src_res.scalars().all():
                try:
                    cid = int((s.config or {}).get("channel_id") or 0)
                except (TypeError, ValueError):
                    continue
                if cid:
                    chat_ids.add(cid)
            if not chat_ids:
                return False

        try:
            from app.services.signal_sources.telegram_source import _api_cfg

            api_id, api_hash, _ = _api_cfg()
            client = TelegramClient(
                StringSession(acc.tg_session),
                api_id,
                api_hash,
                system_version="Jasper Trades",
            )
            await client.connect()
            if not await client.is_user_authorized():
                logger.warning("Telegram listener session unauthorized", device=device_id)
                await client.disconnect()
                return False

            self._followed[device_id] = chat_ids
            self._clients[device_id] = client

            async def _on_message(event: events.NewMessage.Event) -> None:
                await self._handle(device_id, event)

            client.add_event_handler(_on_message, events.NewMessage(incoming=True))
            self._tasks[device_id] = asyncio.create_task(self._run(client, device_id))
            logger.info("Telegram listener started", device=device_id, chats=len(chat_ids))
            return True
        except Exception as e:  # noqa: BLE001
            logger.warning("Telegram listener start failed", device=device_id, error=str(e))
            await self._stop_client(device_id)
            return False

    async def _run(self, client: TelegramClient, device_id: str) -> None:
        try:
            await client.run_until_disconnected()
        except asyncio.CancelledError:
            pass
        except Exception as e:  # noqa: BLE001
            logger.warning("Telegram listener disconnected", device=device_id, error=str(e))
        finally:
            self._clients.pop(device_id, None)
            self._tasks.pop(device_id, None)
            logger.info("Telegram listener stopped", device=device_id)

    async def _stop_client(self, device_id: str) -> None:
        task = self._tasks.pop(device_id, None)
        if task and not task.done():
            task.cancel()
            try:
                await task
            except Exception:  # noqa: BLE001
                pass
        client = self._clients.pop(device_id, None)
        if client:
            try:
                await client.disconnect()
            except Exception:  # noqa: BLE001
                pass
        self._followed.pop(device_id, None)

    async def _handle(self, device_id: str, event: events.NewMessage.Event) -> None:
        msg = event.message
        if not msg or not getattr(msg, "text", None):
            return
        followed = self._followed.get(device_id)
        if not followed:
            return
        chat_id = int(getattr(event, "chat_id", 0) or 0)
        if chat_id not in followed:
            return

        text = msg.text[:_MESSAGE_TEXT_LIMIT]
        if not text.strip():
            return

        draft = SignalDraft(
            source_type="telegram",
            source_id="0",  # replaced by the real DB source id below
            title=text[:120],
            content=text,
            url=f"https://t.me/c/{chat_id}/{msg.id}" if msg.id else None,
            created_at=msg.date.timestamp() if msg.date else None,
        )

        async with async_session() as db:
            src_res = await db.execute(
                select(SignalSource).where(
                    SignalSource.device_id == device_id,
                    SignalSource.source_type == "telegram",
                    SignalSource.is_active == True,  # noqa: E712
                )
            )
            source = None
            for s in src_res.scalars().all():
                try:
                    if int((s.config or {}).get("channel_id") or 0) == chat_id:
                        source = s
                        break
                except (TypeError, ValueError):
                    continue
            if source is None:
                return
            draft.source_id = str(source.id)

            saved = await extract_and_ingest(db, device_id, [draft])
            if not saved:
                await db.rollback()
                return
            for tip in saved:
                await maybe_auto_execute(db, device_id, tip)
            await db.commit()
            logger.info(
                "Telegram listener ingested",
                device=device_id,
                chat=chat_id,
                tips=len(saved),
            )


_LISTENER: Optional[TelegramListenerManager] = None


def get_listener() -> TelegramListenerManager:
    global _LISTENER
    if _LISTENER is None:
        _LISTENER = TelegramListenerManager()
    return _LISTENER