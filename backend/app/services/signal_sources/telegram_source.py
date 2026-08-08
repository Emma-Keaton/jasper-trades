"""Telegram channel signal source (Telethon).

Sessions are persisted in ``SignalSource.tg_session`` so users don't lose
them on redeploy. During the OTP flow we keep a short-lived in-memory
client keyed by phone number.
"""
from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

import structlog
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError
from telethon.sessions import StringSession

from .base import SignalDraft, SignalSourceAdapter

logger = structlog.get_logger(__name__)

# Pending sign-in clients (short-lived, in-memory only)
_PENDING: Dict[str, TelegramClient] = {}


def _api_cfg() -> tuple[int, str, str]:
    api_id = int(os.getenv("TELEGRAM_API_ID", "12345"))
    api_hash = os.getenv("TELEGRAM_API_HASH", "x")
    session_name = os.getenv("TELEGRAM_SESSION_NAME", "jasper")
    return api_id, api_hash, session_name


def _make_client(session_string: Optional[str] = None) -> TelegramClient:
    api_id, api_hash, _ = _api_cfg()
    if session_string:
        return TelegramClient(StringSession(session_string), api_id, api_hash, system_version="Jasper Trades")
    return TelegramClient(":memory:", api_id, api_hash, system_version="Jasper Trades")


class TelegramSource(SignalSourceAdapter):
    """
    Manages Telegram sign-in (phone/OTP/2FA) and channel enumeration, and
    fetches posts from watched channels. Sessions are returned as strings and
    must be persisted by the caller (we store them in ``TelegramAccount``).
    """

    source_type = "telegram"

    async def send_code(self, phone: str) -> Dict[str, Any]:
        client = _make_client()
        await client.connect()
        await client.send_code_request(phone)
        _PENDING[phone] = client
        return {"ok": True, "phone": phone}

    async def sign_in(self, phone: str, code: str, password: Optional[str] = None) -> Dict[str, Any]:
        client = _PENDING.pop(phone, None)
        if client is None:
            client = _make_client()
            await client.connect()
        try:
            await client.sign_in(phone=phone, code=code)
        except SessionPasswordNeededError:
            if not password:
                raise ValueError("2FA required")
            await client.sign_in(password=password)
        user = await client.get_me()
        session = StringSession.save(client.session)
        await client.disconnect()
        return {"ok": True, "user": _user_to_dict(user), "session": session}

    async def list_channels(self, session_string: Optional[str] = None) -> List[Dict[str, Any]]:
        client = _make_client(session_string)
        await client.connect()
        try:
            if not await client.is_user_authorized():
                return []
            out: List[Dict[str, Any]] = []
            async for dialog in client.iter_dialogs():
                if dialog.is_channel or dialog.is_group:
                    entity = dialog.entity
                    out.append(
                        {
                            "id": getattr(entity, "id", None),
                            "username": getattr(entity, "username", None),
                            "title": getattr(entity, "title", None),
                            "type": "channel" if dialog.is_channel else "group",
                            "joined": dialog.date.isoformat() if getattr(dialog, "date", None) else None,
                        }
                    )
            return out
        finally:
            await client.disconnect()

    async def fetch_channel_posts(self, session_string: str, channel_id: int, limit: int = 30) -> List[Dict[str, Any]]:
        client = _make_client(session_string)
        await client.connect()
        try:
            if not await client.is_user_authorized():
                return []
            out: List[Dict[str, Any]] = []
            async for msg in client.iter_messages(channel_id, limit=limit):
                if msg.text:
                    out.append(
                        {
                            "id": msg.id,
                            "text": msg.text,
                            "date": msg.date.isoformat() if msg.date else None,
                            "author_id": getattr(msg.sender_id, "user_id", msg.sender_id) if msg.sender_id else None,
                        }
                    )
            return out
        except Exception as e:  # noqa: BLE001
            logger.warning("Telegram fetch channel failed", channel=channel_id, error=str(e))
            return []
        finally:
            await client.disconnect()

    async def fetch(self, config: Dict[str, Any], limit: int = 20) -> List[SignalDraft]:
        """Adapter-compatible fetch: reads posts from one watched channel."""
        session = config.get("tg_session")
        channel_id = config.get("channel_id")
        if not session or not channel_id:
            return []
        try:
            posts = await self.fetch_channel_posts(session, int(channel_id), limit=limit)
        except Exception as e:  # noqa: BLE001
            logger.warning("Telegram fetch failed", channel=channel_id, error=str(e))
            return []
        drafts: List[SignalDraft] = []
        for post in posts:
            text = post.get("text") or ""
            if not text.strip():
                continue
            drafts.append(
                SignalDraft(
                    source_type="telegram",
                    source_id=str(channel_id),
                    title=text[:120],
                    content=text,
                    url=f"https://t.me/c/{channel_id}/{post.get('id', '')}",
                    created_at=post.get("date"),
                )
            )
        return drafts


def _user_to_dict(user: Any) -> Dict[str, Any]:
    return {
        "id": user.id,
        "first_name": getattr(user, "first_name", ""),
        "last_name": getattr(user, "last_name", ""),
        "username": getattr(user, "username", None),
        "phone": getattr(user, "phone", None),
    }


