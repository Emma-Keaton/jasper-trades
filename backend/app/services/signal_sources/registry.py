"""Signal-source registry and orchestrator.

Usage:
    registry = SignalSourceRegistry(settings)
    drafts   = await registry.fetch_all(limit=50)
    tips     = await registry.extract_tips(drafts, db)
"""
from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from .base import SignalDraft, SignalSourceAdapter, SOURCE_TYPES
from .rss_source import RSSFeedSource
from .reddit_source import RedditSource
from .stocktwits_source import StockTwitsSource
from .telegram_source import TelegramSource
from .telegram_public_source import TelegramPublicSource

logger = structlog.get_logger(__name__)


class SignalSourceRegistry:
    """
    Central registry of all supported signal source types. Holds one adapter
    instance per type. `fetch_all` fans out to all active adapters.
    """

    def __init__(self) -> None:
        self._telegram = TelegramSource()
        self._telegram_public = TelegramPublicSource()
        self._adapters: Dict[str, SignalSourceAdapter] = {
            "rss": RSSFeedSource(),
            "reddit": RedditSource(),
            "stocktwits": StockTwitsSource(),
            "telegram": self._telegram,
            "telegram_public": self._telegram_public,
        }

    @property
    def telegram(self) -> TelegramSource:
        return self._telegram

    def adapter(self, source_type: str) -> Optional[SignalSourceAdapter]:
        return self._adapters.get(source_type)

    async def fetch_all(
        self,
        configs: List[Dict[str, Any]],
        limit: int = 50,
    ) -> List[SignalDraft]:
        by_type: Dict[str, List[Dict[str, Any]]] = {t: [] for t in SOURCE_TYPES}
        for cfg in configs:
            by_type.setdefault(cfg.get("source_type", ""), []).append(cfg)

        out: List[SignalDraft] = []
        for stype, cfgs in by_type.items():
            if not cfgs:
                continue
            adapter = self._adapters.get(stype)
            if adapter is None:
                logger.warning("Unknown source type skipped", source_type=stype)
                continue
            try:
                raw = await adapter.fetch_all(cfgs, limit=limit)
                for d in raw:
                    # Preserve the DB source_id from config so we can
                    # attribute the resulting Signal back to SignalSource.id.
                    cfg_src_id = next(
                        (c.get("source_id") for c in cfgs if _cfg_matches(d, c)), None
                    )
                    if cfg_src_id is not None and not d.source_id:
                        d.source_id = str(cfg_src_id)
                out.extend(raw)
            except Exception as e:  # noqa: BLE001
                logger.warning("fetch_all failed", source_type=stype, error=str(e))
        return out


def _cfg_matches(d: SignalDraft, cfg: Dict[str, Any]) -> bool:
    """Best-effort: did this draft come from this config?"""
    cfg_src = cfg.get("source_id")
    if cfg_src is None:
        return True
    return str(d.source_id) == str(cfg_src) or d.source_id in str(cfg_src)


_REGISTRY: Optional[SignalSourceRegistry] = None


def get_registry() -> SignalSourceRegistry:
    global _REGISTRY
    if _REGISTRY is None:
        _REGISTRY = SignalSourceRegistry()
    return _REGISTRY
