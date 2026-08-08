"""StockTwits signal source - free public streaming API (no key required)."""
from __future__ import annotations

import time
from typing import Any, Dict, List

import httpx
import structlog

from .base import SignalDraft, SignalSourceAdapter

logger = structlog.get_logger(__name__)

BASE = "https://api.stocktwits.com/api/2/streams/symbol"


class StockTwitsSource(SignalSourceAdapter):
    source_type = "stocktwits"

    async def fetch(self, config: Dict[str, Any], limit: int = 20) -> List[SignalDraft]:
        symbols = config.get("symbols") or []
        if isinstance(symbols, str):
            symbols = [s for s in symbols.replace(",", " ").split() if s]
        results: List[SignalDraft] = []
        async with httpx.AsyncClient(timeout=15.0) as client:
            for sym in symbols:
                try:
                    r = await client.get(f"{BASE}/{sym}.json", params={"limit": limit})
                    r.raise_for_status()
                    for msg in (r.json().get("messages") or [])[:limit]:
                        results.append(
                            SignalDraft(
                                source_type="stocktwits",
                                source_id=sym.upper(),
                                title=msg.get("body", "")[:120],
                                content=msg.get("body", ""),
                                author=((msg.get("user") or {}).get("username")),
                                url=msg.get("link"),
                                created_at=time.mktime(msg.get("created_at_parsed", (0,)))
                                if msg.get("created_at_parsed")
                                else None,
                            )
                        )
                except Exception as e:  # noqa: BLE001
                    logger.warning("StockTwits fetch failed", symbol=sym, error=str(e))
        return results
