from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class MarketIntelService:
    async def get_news(self, ticker: str = "", limit: int = 10) -> List[Dict[str, Any]]:
        logger.debug("agent_reach stub: get_news(%s)", ticker)
        return []

    async def get_sentiment(self, ticker: str = "") -> Dict[str, Any]:
        logger.debug("agent_reach stub: get_sentiment(%s)", ticker)
        return {"sentiment": "neutral", "score": 0.0}


def get_market_intel_service() -> MarketIntelService:
    return MarketIntelService()