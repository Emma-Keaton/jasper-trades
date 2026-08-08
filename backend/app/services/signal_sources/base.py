"""Signal-source base types.

A "signal source" is something the user plugs in (a Telegram channel, an RSS
feed, a subreddit, or a StockTwits symbol) that we scrape and turn into trade
tips. This replaces the old agent_reach (OpenCLI/rdt-cli) scrapers.
"""
from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import structlog

logger = structlog.get_logger(__name__)


@dataclass
class SignalDraft:
    """A normalized item pulled from a source (a post, tweet, news story...)."""

    source_type: str  # 'telegram' | 'rss' | 'reddit' | 'stocktwits'
    source_id: str    # the specific channel/feed/subreddit/symbol
    title: str
    content: str
    author: Optional[str] = None
    url: Optional[str] = None
    created_at: Optional[float] = None  # epoch seconds
    extras: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source_type": self.source_type,
            "source_id": self.source_id,
            "title": self.title,
            "content": self.content,
            "author": self.author,
            "url": self.url,
            "created_at": self.created_at,
            "extras": self.extras,
        }


SOURCE_TYPES = ("telegram", "rss", "reddit", "stocktwits")


class SignalSourceAdapter(ABC):
    """Base adapter for a signal-source type. One instance in the registry."""

    source_type: str = "base"

    @abstractmethod
    async def fetch(self, config: Dict[str, Any], limit: int = 20) -> List[SignalDraft]:
        """
        Fetch new items for a source configuration.

        `config` is the per-source JSON from the SignalSource row (e.g. the
        channel username, feed URLs, subreddit list, symbols, keywords).
        """

    async def fetch_all(self, configs: List[Dict[str, Any]], limit: int = 20) -> List[SignalDraft]:
        """Fetch across many configs of this source type."""
        out: List[SignalDraft] = []
        for cfg in configs:
            try:
                out.extend(await self.fetch(cfg, limit=limit // max(1, len(configs))))
            except Exception as e:  # noqa: BLE001
                logger.warning("Source fetch failed", source=self.source_type, error=str(e))
        return out
