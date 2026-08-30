"""StockTwits signal source - free public streaming API (no key required)."""
from __future__ import annotations

import time
from typing import Any, Dict, List

import httpx
import structlog

from .base import SignalDraft, SignalSourceAdapter

logger = structlog.get_logger(__name__)

BASE = "https://api.stocktwits.com/api/2/streams/symbol"
USER_AGENT = "JasperTrades/1.0 (https://github.com/bynara/jasper-trades)"


def _parse_timestamp(msg: Dict[str, Any]) -> float | None:
    """Parse StockTwits created_at into a Unix timestamp float."""
    created = msg.get("created_at")
    if created:
        try:
            from dateutil import parser as du_parser
            dt = du_parser.parse(created)
            return dt.timestamp()
        except Exception:  # noqa: BLE001
            pass
    parsed = msg.get("created_at_parsed")
    if parsed:
        try:
            return time.mktime(tuple(int(v) for v in parsed))
        except Exception:  # noqa: BLE001
            pass
    return None


async def _fetch_with_retry(
    client: httpx.AsyncClient,
    url: str,
    params: dict,
    max_retries: int = 3,
) -> httpx.Response | None:
    """GET with exponential backoff on 429/403."""
    for attempt in range(max_retries):
        try:
            r = await client.get(url, params=params, headers={"User-Agent": USER_AGENT})
            if r.status_code == 429 or r.status_code == 403:
                wait = 2 ** attempt
                logger.warning(
                    "StockTwits rate-limited (429/403), retrying in %ss", wait,
                    status=r.status_code,
                )
                await client.aclose()
                await client.__aenter__()  # reopen via new client
                import asyncio
                await asyncio.sleep(wait)
                continue
            r.raise_for_status()
            return r
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code in (429, 403) and attempt < max_retries - 1:
                wait = 2 ** attempt
                logger.warning("StockTwits error %s, retrying in %ss", exc.response.status_code, wait)
                import asyncio
                await asyncio.sleep(wait)
                continue
            logger.warning("StockTwits fetch failed", url=url, status=exc.response.status_code)
            return None
        except Exception as exc:  # noqa: BLE001
            logger.warning("StockTwits fetch failed", url=url, error=str(exc))
            return None
    return None


class StockTwitsSource(SignalSourceAdapter):
    source_type = "stocktwits"

    async def fetch(self, config: Dict[str, Any], limit: int = 20) -> List[SignalDraft]:
        symbols = config.get("symbols") or []
        if isinstance(symbols, str):
            symbols = [s for s in symbols.replace(",", " ").split() if s]
        results: List[SignalDraft] = []
        async with httpx.AsyncClient(timeout=15.0) as client:
            for sym in symbols:
                r = await _fetch_with_retry(
                    client, f"{BASE}/{sym}.json", {"limit": limit}
                )
                if r is None:
                    continue
                try:
                    for msg in (r.json().get("messages") or [])[:limit]:
                        results.append(
                            SignalDraft(
                                source_type="stocktwits",
                                source_id=sym.upper(),
                                title=msg.get("body", "")[:120],
                                content=msg.get("body", ""),
                                author=((msg.get("user") or {}).get("username")),
                                url=msg.get("link"),
                                created_at=_parse_timestamp(msg),
                            )
                        )
                except Exception as e:  # noqa: BLE001
                    logger.warning("StockTwits parse failed", symbol=sym, error=str(e))
        return results
