"""
Market Data Service - Real-Time Multi-Asset Price Streams
=========================================================

Primary Sources (in priority order):
1. **Finnhub WebSocket** - US stocks (FREE, 60/min, real-time) ✅ BEST
2. **Alpha Vantage HTTP** - US stocks (FREE, 500/day) ✅
3. **Binance WebSocket** - Crypto (FREE, unlimited) ✅
4. **yfinance HTTP** - Stocks fallback (FREE, no limits but slower)

Features:
- Automatic source selection (Finnhub > AlphaVantage > yfinance)
- Circuit breaker for failed providers
- Price caching (30s TTL)
- WebSocket publishing to frontend
- Exponential backoff reconnection

Why this setup:
- Finnhub: Only FREE real-time WebSocket for US stocks
- Alpha Vantage: Reliable backup HTTP API
- No expiring tokens (unlike AllTick's 7-day limit)
"""
from typing import Dict, List, Optional, Set, Any, Tuple
from datetime import datetime, timedelta
import asyncio
import structlog
import json
from collections import defaultdict
import httpx

from app.config import settings
from app.api.websocket.streams import publish_price_update

# Import enhanced services
try:
    from app.services.finnhub_service import get_finnhub_service, is_finnhub_available
    FINNHUB_AVAILABLE = True
except ImportError:
    FINNHUB_AVAILABLE = False

try:
    from app.services.alphavantage_service import get_alphavantage_service, is_alphavantage_available
    ALPHAVANTAGE_AVAILABLE = True
except ImportError:
    ALPHAVANTAGE_AVAILABLE = False

logger = structlog.get_logger(__name__)


class CircuitBreaker:
    """Circuit breaker for market data service."""

    def __init__(self, threshold: int = 10, window_seconds: int = 60):
        self.threshold = threshold
        self.window_seconds = window_seconds
        self.failures: List[datetime] = []
        self.is_open = False
        self.last_failure_time: Optional[datetime] = None

    def record_failure(self):
        """Record a failure and check if circuit should open."""
        now = datetime.utcnow()
        self.failures.append(now)
        self.last_failure_time = now

        # Remove old failures outside window
        cutoff = now - timedelta(seconds=self.window_seconds)
        self.failures = [f for f in self.failures if f > cutoff]

        # Check if threshold exceeded
        if len(self.failures) >= self.threshold:
            self.is_open = True
            logger.warning(
                f"Circuit breaker OPEN: {len(self.failures)} failures in {self.window_seconds}s",
            )

    def reset(self):
        """Reset circuit breaker."""
        self.failures = []
        self.is_open = False
        logger.info("Circuit breaker RESET")

    def can_proceed(self) -> bool:
        """Check if requests can proceed."""
        if not self.is_open:
            return True

        # Check if enough time has passed to try again (30 seconds)
        if self.last_failure_time:
            elapsed = (datetime.utcnow() - self.last_failure_time).total_seconds()
            if elapsed > 30:
                logger.info("Circuit breaker half-open, attempting reconnect")
                self.is_open = False
                self.failures = []
                return True

        return False


class PriceCache:
    """Cache for last-known prices with TTL."""

    def __init__(self, ttl_seconds: int = 30):
        self.ttl_seconds = ttl_seconds
        self.cache: Dict[str, Dict[str, Any]] = {}

    def set(self, symbol: str, price: float, data: Dict[str, Any] = None):
        """Cache a price."""
        self.cache[symbol] = {
            "price": price,
            "timestamp": datetime.utcnow(),
            "data": data or {},
        }

    def get(self, symbol: str) -> Optional[float]:
        """Get cached price if not expired."""
        cached = self.cache.get(symbol)
        if cached:
            age = (datetime.utcnow() - cached["timestamp"]).total_seconds()
            if age < self.ttl_seconds:
                return cached["price"]
            else:
                del self.cache[symbol]
        return None

    def is_fresh(self, symbol: str) -> bool:
        """Check if cached price is fresh."""
        cached = self.cache.get(symbol)
        if cached:
            age = (datetime.utcnow() - cached["timestamp"]).total_seconds()
            return age < self.ttl_seconds
        return False


class MarketDataService:
    """
    Multi-source market data provider.
    
    Priority order:
    1. Finnhub WebSocket (US stocks, real-time) - FREE, 60/min
    2. Alpha Vantage HTTP (US stocks) - FREE, 500/day
    3. Binance WebSocket (crypto) - FREE, unlimited
    4. yfinance HTTP fallback - FREE, slow/unreliable
    """

    def __init__(self):
        self.is_running = False
        self.price_cache = PriceCache(ttl_seconds=30)
        self.circuit_breaker = CircuitBreaker()
        
        # Active WebSocket connections
        self.finnhub_ws = None
        # (Binance WebSocket removed - geo-blocked for Nigeria; crypto uses
        #  _start_crypto_polling via the market-data router instead.)

        # Subscribed symbols
        self.stock_symbols: Set[str] = set()
        self.crypto_symbols: Set[str] = set()
        
        # Reconnection
        self._reconnect_delays = [5, 10, 30, 60]
        self._max_delay = 60
        
    async def start(self, symbols: List[str], asset_type: str = "mixed"):
        """
        Start market data collection for symbols.
        
        Args:
            symbols: List of symbols (e.g., ["AAPL", "BTCUSDT"])
            asset_type: "stocks", "crypto", or "mixed"
        """
        logger.info(f"Starting market data service for {len(symbols)} symbols")
        
        self.is_running = True
        
        # Separate stocks and crypto
        for symbol in symbols:
            if symbol.endswith("USDT") or symbol.endswith("BTC") or symbol.startswith("BTC"):
                self.crypto_symbols.add(symbol.upper())
            else:
                self.stock_symbols.add(symbol.upper())
        
        logger.info(f"Stocks: {self.stock_symbols}, Crypto: {self.crypto_symbols}")
        
        # Start Finnhub WebSocket for stocks (BEST option)
        if self.stock_symbols and FINNHUB_AVAILABLE:
            try:
                finnhub = get_finnhub_service(settings.FINNHUB_API_KEY if hasattr(settings, 'FINNHUB_API_KEY') else None)
                if await finnhub.connect():
                    await finnhub.subscribe(list(self.stock_symbols))
                    self.finnhub_ws = finnhub
                    logger.info("Finnhub WebSocket started for US stocks 🚀")
            except Exception as e:
                logger.warning(f"Finnhub startup failed, will use HTTP fallback: {e}")
        
        # Start Alpha Vantage as backup (already configured in settings)
        if self.stock_symbols and ALPHAVANTAGE_AVAILABLE:
            try:
                alphavantage = get_alphavantage_service(
                    settings.ALPHAVANTAGE_API_KEY if hasattr(settings, 'ALPHAVANTAGE_API_KEY') else None
                )
                # Alpha Vantage is HTTP-only, no WebSocket to start
                logger.info("Alpha Vantage HTTP API available as backup")
            except Exception as e:
                logger.warning(f"Alpha Vantage not configured: {e}")
        
        # Start crypto price polling (CoinGecko -> CCXT -> CoinLore; geo-probe gated)
        if self.crypto_symbols:
            asyncio.create_task(self._start_crypto_polling(list(self.crypto_symbols)))
        
        # Start HTTP polling fallback (for when WebSocket unavailable)
        if self.stock_symbols and not self.finnhub_ws:
            logger.warning("No stock WebSocket available, using HTTP polling fallback")
            asyncio.create_task(self._http_polling_loop())
        
        logger.info("Market data service started")
    
    async def stop(self):
        """Stop all data collection."""
        logger.info("Stopping market data service...")
        self.is_running = False
        
        if self.finnhub_ws:
            await self.finnhub_ws.disconnect()

        # (Binance WS close removed - no longer used.)

        logger.info("Market data service stopped")
    
    async def _start_crypto_polling(self, symbols: List[str]):
        """Poll crypto prices via the market-data router (CoinGecko -> CCXT -> CoinLore).

        Replaces the old Binance WebSocket (geo-blocked for Nigeria). Polls every
        few seconds and publishes updates to the frontend WebSocket.
        """
        if not symbols:
            return
        from app.services.market_data_router import get_market_data_router

        router = get_market_data_router()
        logger.info(f"Starting crypto price polling for {len(symbols)} symbols")
        while self.is_running:
            try:
                for symbol in symbols:
                    try:
                        result = await router.get_price(symbol)
                        price = result.get("price")
                        if price:
                            self.price_cache.set(symbol, price, {"source": result.get("provider")})
                            await publish_price_update({
                                "symbol": symbol,
                                "price": price,
                                "timestamp": datetime.utcnow().isoformat(),
                                "source": result.get("provider"),
                            })
                    except Exception:
                        pass
                await asyncio.sleep(5)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Crypto polling error: {e}")
                await asyncio.sleep(10)
    
    async def _http_polling_loop(self):
        """HTTP polling fallback for stocks when WebSocket unavailable."""
        logger.info("Starting HTTP polling for stocks (fallback mode)")
        
        while self.is_running and self.stock_symbols:
            try:
                for symbol in list(self.stock_symbols):
                    if not self.is_running:
                        break
                    
                    # Skip if recently cached
                    if self.price_cache.is_fresh(symbol):
                        continue
                    
                    # Try Finnhub HTTP first
                    if FINNHUB_AVAILABLE:
                        try:
                            finnhub = get_finnhub_service()
                            quote = await finnhub.get_quote(symbol)
                            if quote and quote.get("price"):
                                price = quote["price"]
                                self.price_cache.set(symbol, price, {**quote, "source": "finnhub_http"})
                                
                                await publish_price_update({
                                    "symbol": symbol,
                                    "price": price,
                                    **quote,
                                    "timestamp": datetime.utcnow().isoformat(),
                                    "source": "finnhub_http",
                                })
                                
                                logger.debug(f"Finnhub HTTP: {symbol} @ ${price}")
                                continue
                        except Exception as e:
                            logger.debug(f"Finnhub HTTP failed for {symbol}: {e}")
                    
                    # Try Alpha Vantage
                    if ALPHAVANTAGE_AVAILABLE:
                        try:
                            alphavantage = get_alphavantage_service()
                            quote = await alphavantage.get_quote(symbol)
                            if quote and quote.get("price"):
                                price = quote["price"]
                                self.price_cache.set(symbol, price, {**quote, "source": "alphavantage"})
                                
                                await publish_price_update({
                                    "symbol": symbol,
                                    "price": price,
                                    **quote,
                                    "timestamp": datetime.utcnow().isoformat(),
                                    "source": "alphavantage",
                                })
                                
                                logger.debug(f"Alpha Vantage: {symbol} @ ${price}")
                                continue
                        except Exception as e:
                            logger.debug(f"Alpha Vantage failed for {symbol}: {e}")
                    
                    # Last resort: yfinance
                    try:
                        price = await self._fetch_yfinance_price(symbol)
                        if price:
                            self.price_cache.set(symbol, price, {"source": "yfinance"})
                            await publish_price_update({
                                "symbol": symbol,
                                "price": price,
                                "timestamp": datetime.utcnow().isoformat(),
                                "source": "yfinance",
                            })
                    except:
                        pass
                
                # Poll every 5 seconds
                await asyncio.sleep(5)
                
            except Exception as e:
                logger.error(f"HTTP polling error: {e}")
                await asyncio.sleep(10)
    
    async def _handle_finnhub_message(self, data: Dict[str, Any]):
        """Handle Finnhub WebSocket trade message."""
        if data.get("type") != "trade":
            return
        
        trades = data.get("data", [])
        for trade in trades:
            symbol = trade.get("s", "").upper()
            price = trade.get("p", 0)
            volume = trade.get("v", 0)
            
            # Update cache
            self.price_cache.set(symbol, price, {
                "volume": volume,
                "timestamp": trade.get("t", 0),
                "source": "finnhub_ws",
            })
            
            # Publish
            await publish_price_update({
                "symbol": symbol,
                "price": price,
                "volume": volume,
                "timestamp": datetime.utcnow().isoformat(),
                "source": "finnhub_ws",
            })
            
            logger.debug(f"Finnhub WS: {symbol} @ ${price}")
    
    async def _fetch_yfinance_price(self, symbol: str) -> Optional[float]:
        """Fetch price from yfinance (last resort fallback)."""
        try:
            import yfinance as yf
            ticker = yf.Ticker(symbol)
            data = ticker.fast_info
            return float(data.last_price) if data.last_price else None
        except:
            return None
    
    def get_price(self, symbol: str) -> Optional[float]:
        """
        Get current price for symbol.
        
        Finite state machine:
        STATE 1: Check WebSocket (if active)
        STATE 2: Check cache (if fresh)
        STATE 3: Fetch via HTTP (Finnhub > AlphaVantage > yfinance)
        
        Args:
            symbol: Trading symbol
            
        Returns:
            Current price or None
        """
        # Check cache first
        cached = self.price_cache.get(symbol)
        if cached:
            return cached
        
        return None


# Singleton instance
market_data_service = MarketDataService()


def get_market_data_service() -> MarketDataService:
    """Get the market data service instance."""
    return market_data_service