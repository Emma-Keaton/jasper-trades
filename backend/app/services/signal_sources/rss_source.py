"""RSS / Atom news-feed signal source (feedparser) - reliable, no auth."""
from __future__ import annotations

import time
from typing import Any, Dict, List

import feedparser
import structlog

from .base import SignalDraft, SignalSourceAdapter

logger = structlog.get_logger(__name__)


class RSSFeedSource(SignalSourceAdapter):
    source_type = "rss"

    async def fetch(self, config: Dict[str, Any], limit: int = 20) -> List[SignalDraft]:
        urls = config.get("urls") or []
        if isinstance(urls, str):
            urls = [urls]
        drafts: List[SignalDraft] = []
        for url in urls:
            try:
                feed = feedparser.parse(url)
                for entry in feed.entries[:limit]:
                    title = entry.get("title", "")
                    content = entry.get("summary", "") or entry.get("description", "") or title
                    drafts.append(
                        SignalDraft(
                            source_type="rss",
                            source_id=url,
                            title=title,
                            content=content,
                            author=entry.get("author"),
                            url=entry.get("link"),
                            created_at=_entry_ts(entry),
                        )
                    )
            except Exception as e:  # noqa: BLE001
                logger.warning("RSS fetch failed", url=url, error=str(e))
        return drafts


def _entry_ts(entry: Dict[str, Any]) -> float:
    ts = entry.get("published_parsed") or entry.get("updated_parsed")
    if ts:
        return time.mktime(ts)
    return None
