"""Reddit signal source - uses Reddit's public JSON API (no key needed).

Endpoints:
    GET https://www.reddit.com/r/{subreddit}/new.json
    GET https://www.reddit.com/search.json?q=...&limit=...
Free and globally accessible; rate-limited (~60 req/min unauthenticated).
"""
from __future__ import annotations

import time
from typing import Any, Dict, List

import httpx
import structlog

from .base import SignalDraft, SignalSourceAdapter

logger = structlog.get_logger(__name__)

BASE = "https://www.reddit.com"
UA = "jasper-trades/1.0"


class RedditSource(SignalSourceAdapter):
    source_type = "reddit"

    async def fetch(self, config: Dict[str, Any], limit: int = 20) -> List[SignalDraft]:
        subreddits = config.get("subreddits") or []
        search_q = config.get("search")  # optional keyword search
        results: List[SignalDraft] = []

        async with httpx.AsyncClient(headers={"User-Agent": UA}, timeout=15.0) as client:
            for sub in subreddits:
                try:
                    r = await client.get(f"{BASE}/r/{sub}/new.json", params={"limit": limit})
                    r.raise_for_status()
                    for post in r.json().get("data", {}).get("children", [])[:limit]:
                        d = post.get("data", {})
                        results.append(
                            SignalDraft(
                                source_type="reddit",
                                source_id=f"r/{sub}",
                                title=d.get("title", ""),
                                content=d.get("selftext", "") or d.get("title", ""),
                                author=d.get("author"),
                                url=f"{BASE}{d.get('permalink', '')}",
                                created_at=d.get("created_utc"),
                                extras={"score": d.get("score"), "num_comments": d.get("num_comments")},
                            )
                        )
                except Exception as e:  # noqa: BLE001
                    logger.warning("Reddit fetch failed", sub=sub, error=str(e))

            if search_q:
                try:
                    r = await client.get(
                        f"{BASE}/search.json",
                        params={"q": search_q, "sort": "new", "limit": limit},
                    )
                    r.raise_for_status()
                    for post in r.json().get("data", {}).get("children", [])[:limit]:
                        d = post.get("data", {})
                        results.append(
                            SignalDraft(
                                source_type="reddit",
                                source_id=f"search:{search_q}",
                                title=d.get("title", ""),
                                content=d.get("selftext", "") or d.get("title", ""),
                                author=d.get("author"),
                                url=f"{BASE}{d.get('permalink', '')}",
                                created_at=d.get("created_utc"),
                            )
                        )
                except Exception as e:  # noqa: BLE001
                    logger.warning("Reddit search failed", error=str(e))
        return results
