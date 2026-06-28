"""
Market Intelligence API Endpoints

Provides endpoints for:
- News aggregation and search
- Sentiment analysis
- Trending stocks
- Channel health status

Usage:
    GET /api/v1/market-intelligence/news?ticker=AAPL&limit=20
    GET /api/v1/market-intelligence/sentiment?ticker=AAPL
    GET /api/v1/market-intelligence/trending?limit=10
    GET /api/v1/market-intelligence/search?q=earnings
    GET /api/v1/market-intelligence/health
"""

from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app.services.agent_reach.market_intel_service import MarketIntelService, get_market_intel_service

router = APIRouter(prefix="/market-intelligence", tags=["Market Intelligence"])


@router.get("/news")
async def get_news(
    ticker: Optional[str] = Query(None, description="Filter by ticker symbol (e.g., AAPL)"),
    limit: int = Query(20, ge=1, le=100, description="Maximum number of articles"),
    sources: Optional[str] = Query(None, description="Comma-separated list of sources (twitter,reddit,v2ex)"),
    since: Optional[datetime] = Query(None, description="Articles newer than this datetime"),
    service: MarketIntelService = Depends(get_market_intel_service)
):
    """
    Get news articles from multiple sources.
    
    Returns aggregated news from Twitter, Reddit, V2EX, and other configured channels.
    Articles are sorted by timestamp (newest first).
    
    **Example:** Get news about Apple
    ```
    GET /api/v1/market-intelligence/news?ticker=AAPL&limit=20
    ```
    
    **Example:** Get news from specific sources
    ```
    GET /api/v1/market-intelligence/news?sources=twitter,reddit&limit=50
    ```
    """
    try:
        sources_list = sources.split(',') if sources else None
        news = await service.get_news(
            ticker=ticker,
            limit=limit,
            sources=sources_list,
            since=since
        )
        
        return {
            'success': True,
            'count': len(news),
            'news': news
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sentiment")
async def get_sentiment(
    ticker: str = Query(..., description="Ticker symbol for sentiment analysis"),
    service: MarketIntelService = Depends(get_market_intel_service)
):
    """
    Get sentiment analysis for a specific ticker.
    
    Aggregates sentiment from all configured channels and returns:
    - Overall sentiment score (0-100, 50=neutral)
    - Per-source sentiment breakdown
    - Recent article count
    
    **Example:**
    ```
    GET /api/v1/market-intelligence/sentiment?ticker=AAPL
    ```
    
    **Response:**
    ```json
    {
      "symbol": "AAPL",
      "overall_score": 65,
      "source_scores": {
        "twitter": 70,
        "reddit": 60,
        "v2ex": 65
      },
      "recent_articles": 15,
      "last_updated": "2026-06-26T10:30:00"
    }
    ```
    """
    try:
        sentiment = await service.get_sentiment(ticker.upper())
        return {
            'success': True,
            'sentiment': sentiment
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/trending")
async def get_trending(
    limit: int = Query(10, ge=1, le=50, description="Number of trending stocks to return"),
    service: MarketIntelService = Depends(get_market_intel_service)
):
    """
    Get trending stocks based on social media volume and sentiment.
    
    Ranks stocks by:
    - Mention count across all channels
    - Sentiment momentum
    - Cross-platform consensus
    
    **Example:**
    ```
    GET /api/v1/market-intelligence/trending?limit=20
    ```
    
    **Response:**
    ```json
    {
      "success": true,
      "trending": [
        {
          "symbol": "NVDA",
          "mention_count": 45,
          "sentiment": "positive"
        },
        ...
      ]
    }
    ```
    """
    try:
        trending = await service.get_trending_stocks(limit=limit)
        return {
            'success': True,
            'count': len(trending),
            'trending': trending
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/search")
async def search_news(
    q: str = Query(..., description="Search query keywords"),
    limit: int = Query(20, ge=1, le=100, description="Maximum results"),
    service: MarketIntelService = Depends(get_market_intel_service)
):
    """
    Search news articles by keywords.
    
    Searches across all aggregated news from configured channels.
    
    **Example:**
    ```
    GET /api/v1/market-intelligence/search?q=earnings+beat&limit=20
    ```
    
    **Example:**
    ```
    GET /api/v1/market-intelligence/search?q=FDA+approval+stock&limit=30
    ```
    """
    try:
        results = await service.search_news(query=q, limit=limit)
        return {
            'success': True,
            'query': q,
            'count': len(results),
            'results': results
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
async def health_check(
    service: MarketIntelService = Depends(get_market_intel_service)
):
    """
    Check health status of market intelligence channels.
    
    Returns status of all configured channels and cache information.
    
    **Example:**
    ```
    GET /api/v1/market-intelligence/health
    ```
    
    **Response:**
    ```json
    {
      "enabled": true,
      "channels": {
        "twitter": {"enabled": true, "status": "ok"},
        "reddit": {"enabled": false, "status": "off"},
        "v2ex": {"enabled": true, "status": "ok"}
      },
      "last_update": "2026-06-26T10:30:00",
      "cached_news_count": 150
    }
    ```
    """
    try:
        status = await service.health_check()
        return {
            'success': True,
            'health': status
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/refresh")
async def refresh_news(
    service: MarketIntelService = Depends(get_market_intel_service)
):
    """
    Manually trigger news refresh from all channels.
    
    Bypasses the normal polling interval and fetches fresh data immediately.
    
    **Example:**
    ```
    POST /api/v1/market-intelligence/refresh
    ```
    """
    try:
        await service._fetch_all_news()
        return {
            'success': True,
            'message': 'News refresh initiated'
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))