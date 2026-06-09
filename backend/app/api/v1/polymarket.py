"""
Polymarket API - Prediction market data and simulated trading
Inspired by AI-Trader Polymarket integration
"""
from fastapi import APIRouter, HTTPException, Query, Body
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
import structlog

from app.services.polymarket_service import polymarket_service, PolymarketMarket, PolymarketOrderbook

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/v1/polymarket", tags=["Polymarket"])


class MarketSummary(BaseModel):
    """Market summary response"""
    market_id: str
    question: str
    slug: str
    outcomes: List[str]
    volume: float
    liquidity: float
    status: str
    best_prices: Dict[str, float]


class OrderbookSummary(BaseModel):
    """Orderbook summary response"""
    token_id: str
    best_bid: float
    best_ask: float
    mid_price: float
    spread: float
    spread_pct: float


class MarketAnalysis(BaseModel):
    """Market analysis response"""
    market_id: str
    question: str
    outcomes: List[str]
    prices: Dict[str, float]
    total_implied_probability: float
    arbitrage_detected: bool
    recommendation: Optional[str]
    confidence: float


@router.get("/search")
async def search_markets(
    query: str = Query(..., description="Search query (e.g., 'BTC', 'election', 'Fed')"),
    limit: int = Query(20, ge=1, le=100, description="Maximum results")
) -> List[Dict[str, Any]]:
    """
    Search for Polymarket markets by keyword.
    
    Returns market metadata including:
    - Question and slug
    - Outcomes and token IDs
    - Volume and liquidity
    - Status and closing date
    """
    try:
        markets = await polymarket_service.search_markets(query, limit)
        
        return [
            {
                "market_id": m.market_id,
                "question": m.question,
                "slug": m.slug,
                "outcomes": m.outcomes,
                "clob_token_ids": m.clob_token_ids,
                "volume": m.volume,
                "liquidity": m.liquidity,
                "status": m.status,
                "closing_date": m.closing_date
            }
            for m in markets
        ]
    
    except Exception as e:
        logger.error(f"Polymarket search failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/market/{slug:path}")
async def get_market(slug: str) -> Dict[str, Any]:
    """
    Get market metadata by slug.
    
    Example slug: `will-btc-be-above-120k-on-june-30`
    
    Use this endpoint to:
    - Resolve market details
    - Get outcome token IDs
    - Read volume and liquidity
    """
    try:
        market = await polymarket_service.get_market_by_slug(slug)
        
        if not market:
            raise HTTPException(status_code=404, detail="Market not found")
        
        return {
            "market_id": market.market_id,
            "question": market.question,
            "slug": market.slug,
            "condition_id": market.condition_id,
            "outcomes": market.outcomes,
            "clob_token_ids": market.clob_token_ids,
            "volume": market.volume,
            "liquidity": market.liquidity,
            "open_interest": market.open_interest,
            "status": market.status,
            "closing_date": market.closing_date,
            "resolved_prices": market.resolved_prices
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get market {slug}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/market/by-condition/{condition_id}")
async def get_market_by_condition(condition_id: str) -> Dict[str, Any]:
    """
    Get market by on-chain condition ID.
    
    Condition IDs are Ethereum identifiers for prediction markets.
    """
    try:
        market = await polymarket_service.get_market_by_condition_id(condition_id)
        
        if not market:
            raise HTTPException(status_code=404, detail="Market not found")
        
        return asdict(market)
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get market by condition {condition_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/orderbook/{token_id}")
async def get_orderbook(token_id: str) -> Dict[str, Any]:
    """
    Get orderbook for a specific outcome token.
    
    Returns:
    - Bid/ask orders with prices and sizes
    - Best bid/ask prices
    - Mid price (fair value estimate)
    - Spread (bid-ask difference)
    """
    try:
        orderbook = await polymarket_service.get_orderbook(token_id)
        
        if not orderbook:
            raise HTTPException(status_code=404, detail="Orderbook not found")
        
        return {
            "token_id": orderbook.token_id,
            "bids": orderbook.bids[:10],  # Top 10 bids
            "asks": orderbook.asks[:10],  # Top 10 asks
            "best_bid": orderbook.best_bid,
            "best_ask": orderbook.best_ask,
            "mid_price": orderbook.mid_price,
            "spread": orderbook.spread,
            "last_update": orderbook.last_update
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get orderbook for {token_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/price/{token_id}")
async def get_price(token_id: str) -> Dict[str, Any]:
    """
    Get current mid price for an outcome token.
    
    Price represents implied probability (0.0-1.0):
    - 0.65 = 65% probability
    - 0.50 = 50/50 coin flip
    - 0.25 = 25% probability
    
    Example: A "Yes" token at 0.70 means the market assigns
    70% probability to that outcome occurring.
    """
    try:
        price = await polymarket_service.get_outcome_price(token_id)
        
        if price is None:
            raise HTTPException(status_code=404, detail="Price not available")
        
        return {
            "token_id": token_id,
            "mid_price": price,
            "implied_probability": f"{price:.1%}"
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get price for {token_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/analyze/{slug:path}")
async def analyze_market(slug: str) -> Dict[str, Any]:
    """
    Analyze a Polymarket for trading opportunities.
    
    Analysis includes:
    - Current outcome prices
    - Total implied probability check
    - Arbitrage detection (sum != 1.0)
    - Value recommendation
    - Confidence score
    
    **Example opportunity**: If all outcomes sum to <0.90,
    buying all outcomes guarantees profit (arbitrage).
    """
    try:
        analysis = await polymarket_service.analyze_market(slug)
        
        if not analysis:
            raise HTTPException(status_code=404, detail="Market not found or analysis failed")
        
        return {
            "market_id": analysis["market_id"],
            "question": analysis["question"],
            "outcomes": analysis["outcomes"],
            "prices": analysis["prices"],
            "total_implied_probability": analysis["total_implied_probability"],
            "arbitrage_detected": analysis["arbitrage_detected"],
            "recommendation": analysis["recommendation"],
            "confidence": analysis["confidence"]
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Market analysis failed for {slug}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/trending")
async def get_trending_markets(limit: int = Query(10, ge=1, le=50)) -> List[Dict[str, Any]]:
    """
    Get trending/volatile markets.
    
    Useful for discovering active prediction markets with high volume.
    """
    try:
        markets = await polymarket_service.get_trending_markets(limit)
        
        return [
            {
                "market_id": m.market_id,
                "question": m.question,
                "slug": m.slug,
                "outcomes": m.outcomes,
                "volume": m.volume,
                "liquidity": m.liquidity,
                "status": m.status
            }
            for m in markets
        ]
    
    except Exception as e:
        logger.error(f"Failed to get trending markets: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/category/{category}")
async def get_markets_by_category(
    category: str,
    limit: int = Query(20, ge=1, le=100)
) -> List[Dict[str, Any]]:
    """
    Get markets by category.
    
    **Categories:**
    - `crypto`: Bitcoin, Ethereum, crypto price predictions
    - `politics`: Elections, policy decisions
    - `sports`: Game outcomes, championships
    - `economics`: Fed rates, GDP, inflation
    - `current-events`: News events
    """
    try:
        markets = await polymarket_service.get_markets_by_category(category, limit)
        
        return [
            {
                "market_id": m.market_id,
                "question": m.question,
                "slug": m.slug,
                "outcomes": m.outcomes,
                "volume": m.volume,
                "liquidity": m.liquidity,
                "status": m.status
            }
            for m in markets
        ]
    
    except Exception as e:
        logger.error(f"Failed to get {category} markets: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status")
async def get_polymarket_status():
    """Get Polymarket service status"""
    return polymarket_service.get_cache_status()


@router.post("/cache/refresh")
async def refresh_cache():
    """Refresh cached market data"""
    try:
        await polymarket_service.refresh_cache()
        return {"status": "success", "message": "Cache refreshed"}
    
    except Exception as e:
        logger.error(f"Cache refresh failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))