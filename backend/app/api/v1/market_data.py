"""
Market Data API - unified pricing, trend detection, and provider status.

Consolidates the market-data backend (CoinGecko / CCXT / CoinMarketCap /
CoinLore router, memecoin discovery, Trove stocks, AKShare CN stocks) behind
one router so the frontend Markets screen has a single stable surface:

  GET /api/v1/market-data/trending         Merged crypto + memecoin trends
  GET /api/v1/market-data/gainers-losers   Top 24h gainers/losers
  GET /api/v1/market-data/prices?symbol=   Single/plural prices (asset-class aware)
  GET /api/v1/market-data/providers        Which data providers are configured
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
import structlog

from app.services.market_data_providers import get_market_data_service
from app.services.market_data_router import get_market_data_router

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/market-data", tags=["market-data"])


@router.get("/trending")
async def get_trending(limit: int = Query(10, ge=1, le=50)) -> Dict[str, Any]:
    """Merged trending feed (crypto + memecoins). Never 404s."""
    try:
        items = await get_market_data_router().get_trending(limit=limit)
        return {"trending": items, "count": len(items)}
    except Exception as e:  # noqa: BLE001
        logger.error("Market-data trending failed", error=str(e))
        raise HTTPException(status_code=502, detail="Trending unavailable")


@router.get("/gainers-losers")
async def get_gainers_losers(limit: int = Query(10, ge=1, le=50)) -> Dict[str, Any]:
    """Top 24h gainers and losers (CoinGecko markets, CMC when keyed)."""
    svc = get_market_data_service()
    result = await svc.get_top_gainers_losers_coingecko()
    if result.get("success"):
        return result["data"]
    try:
        from app.services.coinmarketcap_service import get_coinmarketcap_service

        cmc = get_coinmarketcap_service()
        if cmc.configured:
            res = await cmc.get_trending(limit)
            if res.get("success"):
                return {
                    "top_gainers": res["data"].get("gainers", [])[:limit],
                    "top_losers": res["data"].get("losers", [])[:limit],
                }
    except Exception as e:  # noqa: BLE001
        logger.debug("CMC gainers/losers fallback failed", error=str(e))
    raise HTTPException(status_code=502, detail="Gainers/losers unavailable")


@router.get("/prices")
async def get_prices(
    symbol: str = Query(..., min_length=1),
    asset_class: str = Query("crypto"),
) -> Dict[str, Any]:
    """Price lookup, asset-class aware (crypto chain, Trove stocks, AKShare CN)."""
    cls = (asset_class or "crypto").lower()
    try:
        if cls in ("stock", "stocks", "us-stock", "ngx"):
            return await _stock_price(symbol)
        if cls in ("cn", "akshare", "chinese"):
            return await _cn_price(symbol)
        price = await get_market_data_router().get_price(symbol)
        return {"success": bool(price.get("price")), "data": price}
    except Exception as e:  # noqa: BLE001
        logger.error("Market-data price lookup failed", symbol=symbol, error=str(e))
        raise HTTPException(status_code=502, detail="Price lookup unavailable")


async def _stock_price(symbol: str) -> Dict[str, Any]:
    """Trove stock quote when configured; otherwise returns an explicit miss."""
    from app.services.market_data_providers import get_market_data_service

    svc = get_market_data_service()
    if svc.config.get("finnhub_key"):
        res = await svc.get_stock_price_finnhub(symbol)
        if res.get("success"):
            return {"success": True, "data": {**res["data"], "provider": "finnhub"}}
    if svc.config.get("alphavantage_key"):
        res = await svc.get_stock_price_alphavantage(symbol)
        if res.get("success"):
            return {"success": True, "data": res["data"]}
    return {
        "success": False,
        "data": {"symbol": symbol, "price": 0.0, "provider": "none"},
        "error": "no stock data provider configured",
    }


async def _cn_price(symbol: str) -> Dict[str, Any]:
    """AKShare CN stock quote (paper-data feed)."""
    try:
        from app.brokers.akshare_service import AKShareBrokerService

        service = AKShareBrokerService()
        if not service.is_connected:
            await service.connect()
        exchange = "SSE" if symbol.startswith(("6", "9")) else "SZSE"
        data = await service.get_market_data(symbol, exchange)
        if data:
            return {"success": True, "data": data, "provider": "akshare"}
    except Exception as e:  # noqa: BLE001
        logger.debug("AKShare price lookup failed", symbol=symbol, error=str(e))
    return {"success": False, "data": {"symbol": symbol, "price": 0.0, "provider": "none"}}


@router.get("/providers")
async def get_providers() -> Dict[str, Any]:
    """Which market data providers are configured."""
    svc = get_market_data_service()
    return {"providers": svc.get_available_providers()}