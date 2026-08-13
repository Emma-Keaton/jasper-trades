"""Telegram public channel signal source.

Scrapes the public ``t.me/s/<username>`` web feed - no login required. Works
for public channels/groups with "messages preview" enabled. The scheduler
polls this source like any other, so keep-interval friendly by default.
"""
from __future__ import annotations

import html as html_lib
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import httpx
import structlog

from .base import SignalDraft, SignalSourceAdapter

logger = structlog.get_logger(__name__)

PUBLIC_URL_TMPL = "https://t.me/s/{username}"

# Message blocks on the t.me/s page.
_WRAP_RE = re.compile(r'<div class="tgme_widget_message_wrap[^"]*"[^>]*>', re.S)
_TEXT_RE = re.compile(r'<div class="tgme_widget_message_text[^"]*"[^>]*>(.*?)</div>', re.S)
_DATE_RE = re.compile(r'<time[^>]*datetime="([^"]+)"', re.S)
_POST_RE = re.compile(r'data-post="([^"/]+)/(\d+)"')

_TAG_RE = re.compile(r"<[^>]+>")
_TAGWS_RE = re.compile(r"[ \t]+")


class TelegramPublicSource(SignalSourceAdapter):
    """Adapter-compatible public-feed scraper (no Telethon session needed)."""

    source_type = "telegram_public"

    async def fetch(self, config: Dict[str, Any], limit: int = 20) -> List[SignalDraft]:
        username = self._parse_username(config)
        if not username:
            return []

        try:
            async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
                resp = await client.get(PUBLIC_URL_TMPL.format(username=username))
                resp.raise_for_status()
        except Exception as e:  # noqa: BLE001
            logger.warning("t.me/s fetch failed", username=username, error=str(e))
            return []

        drafts: List[SignalDraft] = []
        for block in _WRAP_RE.split(resp.text)[1:]:
            text = self._extract_text(block)
            if not text.strip():
                continue
            post = _POST_RE.search(block)
            post_id = post.group(2) if post else ""
            drafts.append(
                SignalDraft(
                    source_type="telegram_public",
                    source_id=username,
                    title=text[:120],
                    content=text,
                    url=f"https://t.me/{username}/{post_id}" if post_id else None,
                    created_at=self._extract_date(block),
                )
            )
            if len(drafts) >= limit:
                break
        return drafts

    @staticmethod
    def _parse_username(config: Dict[str, Any]) -> Optional[str]:
        raw = (config.get("channel") or config.get("username") or "").strip()
        if not raw:
            return None
        if "t.me/" in raw:  # accept full URLs: https://t.me/<username> or t.me/s/<username>
            raw = raw.split("t.me/", 1)[1]
        raw = raw.rstrip("/")
        if raw.startswith("s/"):  # the t.me/s preview path
            raw = raw[2:]
        raw = raw.split("/")[0].split("?")[0].lstrip("@").strip()
        if not re.match(r"^[A-Za-z0-9_]{3,64}$", raw):
            return None
        return raw

    @staticmethod
    def _extract_text(block: str) -> str:
        m = _TEXT_RE.search(block)
        if not m:
            return ""
        inner = m.group(1)
        inner = inner.replace("<br>", "\n").replace("<br/>", "\n")
        inner = inner.replace("</div>", "\n").replace("</p>", "\n")
        text = _TAG_RE.sub("", inner)
        text = html_lib.unescape(text)
        lines = [_TAGWS_RE.sub(" ", ln).strip() for ln in text.split("\n")]
        return "\n".join(ln for ln in lines if ln)

    @staticmethod
    def _extract_date(block: str) -> Optional[float]:
        m = _DATE_RE.search(block)
        if not m:
            return None
        try:
            iso = m.group(1).replace("Z", "+00:00")
            dt = datetime.fromisoformat(iso)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.timestamp()
        except Exception:  # noqa: BLE001
            return None