"""
Alpha Vantage Market Data Service - Enhanced US Stocks HTTP API
================================================================

Free stock market data API (500 calls/day free tier).
Used as primary source for US stock prices when WebSocket unavailable.

Features:
- Global Quote (real-time price)
- Time Series (intraday, daily)
- Company overview, quotes
- Forex/crypto support

API Docs: https://www.alphavantage.co/documentation/
Free Tier: 500 calls/day, 5 calls/min
"""
import asyncio
import structlog
import httpx
from typing import Dict, Any, Optional, List
from datetime import datetime

logger = structlog.get_logger(__name__)


class AlphaVantageService:
    """
    Alpha Vantage Market Data Service.
    
    Provides US stock, forex, and crypto data via HTTP API.
    """
    
    BASE_URL = "https://www.alphavantage.co/query"
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize Alpha Vantage service.
        
        Args:
            api_key: Alpha Vantage API key (free at https://www.alphavantage.co/support/#api-key)
        """
        self.api_key = api_key
        self._cache: Dict[str, Dict[str, Any]] = {}  # symbol -> {price, timestamp}
        self._cache_ttl = 30  # Cache for 30 seconds
        
    async def get_quote(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Get latest quote for symbol using GLOBAL_QUOTE endpoint.
        
        Args:
            symbol: Stock symbol (e.g., "AAPL", "TSLA")
            
        Returns:
            Quote dict with price, volume, change or None
        """
        if not self.api_key:
            logger.warning("Alpha Vantage API key not configured")
            return None
        
        params = {
            "function": "GLOBAL_QUOTE",
            "symbol": symbol,
            "apikey": self.api_key
        }
        
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(self.BASE_URL, params=params)
                
                if response.status_code == 200:
                    data = response.json()
                    quote = data.get("Global Quote", {})
                    
                    # Check for rate limit
                    if "Note" in quote:
                        logger.warning(f"Alpha Vantage rate limited: {quote['Note']}")
                        return None
                    
                    # Parse quote data
                    result = {
                        "price": float(quote.get("05. price", 0)),
                        "volume": int(quote.get("06. volume", 0)),
                        "change": float(quote.get("09. change", 0)),
                        "change_percent": quote.get("10. changePercent", "0%"),
                        "high": float(quote.get("03. high", 0)),
                        "low": float(quote.get("04. low", 0)),
                        "open": float(quote.get("02. open", 0)),
                        "previous_close": float(quote.get("01. open", 0)),
                        "timestamp": quote.get("07. latest trading day", ""),
                    }
                    
                    # Cache the result
                    self._cache[symbol] = {
                        "price": result["price"],
                        "timestamp": datetime.utcnow(),
                        "data": result
                    }
                    
                    return result
                    
                else:
                    logger.error(f"Alpha Vantage API error: {response.status_code}")
                    return None
                    
        except Exception as e:
            logger.debug(f"Alpha Vantage quote fetch failed: {e}")
            # Return cached price if available
            cached = self.get_cached_price(symbol)
            if cached:
                return {"price": cached, "from_cache": True}
            return None
    
    async def get_time_series_intraday(
        self,
        symbol: str,
        interval: str = "5min",
        output_size: str = "compact"
    ) -> Optional[List[Dict[str, Any]]]:
        """
        Get intraday time series data.
        
        Args:
            symbol: Stock symbol
            interval: 1min, 5min, 15min, 30min, 60min
            output_size: "compact" (last 100) or "full" (all)
            
        Returns:
            List of OHLCV data points or None
        """
        if not self.api_key:
            return None
        
        params = {
            "function": "TIME_SERIES_INTRADAY",
            "symbol": symbol,
            "interval": interval,
            "outputsize": output_size,
            "datatype": "json",
            "apikey": self.api_key
        }
        
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(self.BASE_URL, params=params)
                
                if response.status_code == 200:
                    data = response.json()
                    time_series = data.get("Time Series (5min)", {})
                    
                    # Convert to list format
                    result = []
                    for timestamp, ohlcv in time_series.items():
                        result.append({
                            "timestamp": timestamp,
                            "open": float(ohlcv.get("1. open", 0)),
                            "high": float(ohlcv.get("2. high", 0)),
                            "low": float(ohlcv.get("3. low", 0)),
                            "close": float(ohlcv.get("4. close", 0)),
                            "volume": int(ohlcv.get("5. volume", 0))
                        })
                    
                    return result
                    
                return None
                
        except Exception as e:
            logger.debug(f"Alpha Vantage time series failed: {e}")
            return None
    
    async def get_company_overview(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Get company overview/fundamentals.
        
        Args:
            symbol: Stock symbol
            
        Returns:
            Company overview dict or None
        """
        if not self.api_key:
            return None
        
        params = {
            "function": "OVERVIEW",
            "symbol": symbol,
            "apikey": self.api_key
        }
        
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(self.BASE_URL, params=params)
                
                if response.status_code == 200:
                    return response.json()
                    
                return None
                
        except Exception as e:
            logger.debug(f"Alpha Vantage overview failed: {e}")
            return None
    
    def get_cached_price(self, symbol: str) -> Optional[float]:
        """
        Get cached price if not expired.
        
        Args:
            symbol: Stock symbol
            
        Returns:
            Last known price or None
        """
        cached = self._cache.get(symbol)
        if cached:
            age = (datetime.utcnow() - cached["timestamp"]).total_seconds()
            if age < self._cache_ttl:
                return cached["price"]
            else:
                # Expired
                del self._cache[symbol]
        return None
    
    def get_price(self, symbol: str) -> Optional[float]:
        """
        Get current price (from cache or fetch).
        
        Args:
            symbol: Stock symbol
            
        Returns:
            Current price or None
        """
        # Try cache first
        cached = self.get_cached_price(symbol)
        if cached:
            return cached
        
        # Note: For fresh price, use get_quote()
        return None


# Singleton instance
_alphavantage_service: Optional[AlphaVantageService] = None


def get_alphavantage_service(api_key: Optional[str] = None) -> AlphaVantageService:
    """
    Get or create Alpha Vantage service instance.
    
    Args:
        api_key: Alpha Vantage API key
        
    Returns:
        AlphaVantageService instance
    """
    global _alphavantage_service
    if _alphavantage_service is None:
        _alphavantage_service = AlphaVantageService(api_key)
    return _alphavantage_service


def is_alphavantage_available() -> bool:
    """Check if Alpha Vantage service is configured."""
    service = get_alphavantage_service()
    return service.api_key is not None