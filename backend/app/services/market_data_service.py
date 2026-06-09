"""
Market Data Service - Real-Time Price Streams with Robust Error Handling
Provides WebSocket connections to market data providers (Alpaca, Binance)
with exponential backoff reconnection and HTTP fallback.

Features:
- Exponential backoff reconnection (5s, 10s, 30s, 60s max)
- HTTP fallback if WebSocket unavailable
- Price caching (30 seconds) to handle outages
- Circuit breaker: pause if 10+ timeouts in 1 minute
- Publishes to WebSocket streams for frontend
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
        self.prices: Dict[str, Tuple[float, datetime]] = {}
    
    def set(self, symbol: str, price: float):
        """Cache price."""
        self.prices[symbol.upper()] = (price, datetime.utcnow())
    
    def get(self, symbol: str) -> Optional[float]:
        """Get cached price if not expired."""
        symbol = symbol.upper()
        if symbol not in self.prices:
            return None
        
        price, timestamp = self.prices[symbol]
        age = (datetime.utcnow() - timestamp).total_seconds()
        
        if age > self.ttl_seconds:
            logger.debug(f"Price cache expired for {symbol}")
            del self.prices[symbol]
            return None
        
        return price
    
    def get_all(self) -> Dict[str, float]:
        """Get all valid cached prices."""
        now = datetime.utcnow()
        valid = {}
        expired = []
        
        for symbol, (price, timestamp) in self.prices.items():
            age = (now - timestamp).total_seconds()
            if age <= self.ttl_seconds:
                valid[symbol] = price
            else:
                expired.append(symbol)
        
        # Clean up expired
        for symbol in expired:
            del self.prices[symbol]
        
        return valid


class MarketDataService:
    """
    Market Data Service - Real-time price streams with robust error handling.
    
    Features:
    - Alpaca WebSocket for stocks/crypto
    - Binance WebSocket for crypto
    - Exponential backoff reconnection
    - HTTP fallback polling
    - Price caching for outage resilience
    - Circuit breaker for repeated failures
    """
    
    def __init__(self):
        self.is_running = False
        self.subscribed_symbols: Set[str] = set()
        self.alpaca_ws = None
        self.binance_ws = None
        self._ws_task = None
        self._http_fallback_task = None
        
        # Reconnection settings
        self._reconnect_delays = [5, 10, 30, 60]  # Exponential backoff
        self._max_delay = 60
        
        # Circuit breaker and cache
        self.circuit_breaker = CircuitBreaker(threshold=10, window_seconds=60)
        self.price_cache = PriceCache(ttl_seconds=30)
        
        # Connectivity tracking
        self.last_successful_connection: Optional[datetime] = None
        self.connection_attempts = 0
        
        # Alpaca WebSocket URL
        self.alpaca_ws_url = "wss://stream.data.alpaca.markets/v2/iex"
        
        # Binance WebSocket URL
        self.binance_ws_url = "wss://stream.binance.com:9443/ws"
        
        logger.info("Market Data Service initialized with robust error handling")
    
    async def start(self, symbols: Optional[List[str]] = None):
        """
        Start WebSocket connections to market data providers.
        
        Args:
            symbols: List of symbols to subscribe to
        """
        if self.is_running:
            logger.warning("Market Data Service already running")
            return
        
        self.is_running = True
        
        if symbols:
            self.subscribed_symbols = set(s.upper() for s in symbols)
            logger.info(f"Subscribed to {len(self.subscribed_symbols)} symbols")
        
        # Start Alpaca WebSocket (primary for stocks)
        if settings.ALPACA_API_KEY and settings.ALPACA_API_SECRET:
            if self.circuit_breaker.can_proceed():
                self._ws_task = asyncio.create_task(self._run_alpaca_ws())
                logger.info("Alpaca WebSocket task started")
            else:
                logger.warning("Circuit breaker open, skipping WebSocket start")
        else:
            logger.warning("Alpaca credentials not configured, starting HTTP fallback")
            self._http_fallback_task = asyncio.create_task(self._run_http_fallback())
    
    async def stop(self):
        """Stop all WebSocket connections."""
        self.is_running = False
        
        if self._ws_task:
            self._ws_task.cancel()
            try:
                await self._ws_task
            except asyncio.CancelledError:
                pass
        
        if self._http_fallback_task:
            self._http_fallback_task.cancel()
            try:
                await self._http_fallback_task
            except asyncio.CancelledError:
                pass
        
        logger.info("Market Data Service stopped")
    
    def subscribe(self, symbols: List[str]):
        """Add symbols to subscription list."""
        for symbol in symbols:
            self.subscribed_symbols.add(symbol.upper())
        logger.info(f"Subscribed to new symbols", total=len(self.subscribed_symbols))
    
    def unsubscribe(self, symbols: List[str]):
        """Remove symbols from subscription list."""
        for symbol in symbols:
            self.subscribed_symbols.discard(symbol.upper())
        logger.info(f"Unsubscribed from symbols", total=len(self.subscribed_symbols))
    
    async def _run_alpaca_ws(self):
        """
        Alpaca WebSocket V2 protocol with exponential backoff.
        """
        attempt = 0
        
        while self.is_running:
            try:
                # Import websockets library
                try:
                    from websockets import connect
                except ImportError:
                    logger.error("websockets library not installed. Run: pip install websockets")
                    # Fall back to HTTP polling
                    await self._run_http_fallback()
                    return
                
                self.connection_attempts += 1
                
                async with connect(
                    self.alpaca_ws_url,
                    extra_headers={
                        "Apca-Api-Key-Id": settings.ALPACA_API_KEY,
                        "Apca-Api-Secret-Key": settings.ALPACA_API_SECRET,
                    },
                    close_timeout=10,
                    ping_timeout=10,
                    ping_interval=30,
                ) as websocket:
                    # Success - reset circuit breaker and attempt counter
                    self.circuit_breaker.reset()
                    self.last_successful_connection = datetime.utcnow()
                    attempt = 0
                    
                    logger.info("Connected to Alpaca WebSocket")
                    
                    # Subscribe to quotes and trades
                    if self.subscribed_symbols:
                        subscribe_msg = {
                            "action": "subscribe",
                            "quotes": list(self.subscribed_symbols),
                            "trades": list(self.subscribed_symbols),
                        }
                        await websocket.send(json.dumps(subscribe_msg))
                        logger.info(f"Subscribed to {len(self.subscribed_symbols)} symbols")
                    
                    # Listen for messages
                    await self._listen_loop(websocket)
                    
            except asyncio.CancelledError:
                logger.info("Alpaca WebSocket task cancelled")
                break
            except Exception as e:
                logger.error(f"Alpaca WebSocket error: {e}")
                self.circuit_breaker.record_failure()
                
                if self.is_running:
                    # Exponential backoff
                    delay = min(self._reconnect_delays[min(attempt, len(self._reconnect_delays)-1)], self._max_delay)
                    logger.info(f"Reconnecting in {delay}s (attempt {attempt + 1})")
                    await asyncio.sleep(delay)
                    attempt += 1
                    
                    # If circuit breaker is open, wait longer
                    if self.circuit_breaker.is_open:
                        logger.warning("Circuit breaker open, waiting 60s before retry")
                        await asyncio.sleep(60)
    
    async def _listen_loop(self, websocket):
        """Listen for WebSocket messages."""
        try:
            async for message in websocket:
                if not self.is_running:
                    break
                
                try:
                    data = json.loads(message)
                    await self._handle_alpaca_message(data)
                except json.JSONDecodeError:
                    logger.warning(f"Invalid JSON from Alpaca: {message}")
        except Exception as e:
            logger.error(f"WebSocket listen error: {e}")
            raise  # Re-raise to trigger reconnection
    
    async def _handle_alpaca_message(self, data: dict):
        """
        Handle incoming Alpaca WebSocket message.
        """
        try:
            if isinstance(data, list):
                # Alpaca sends arrays of messages
                for msg in data:
                    await self._process_single_message(msg)
            else:
                await self._process_single_message(data)
        except Exception as e:
            logger.error(f"Error processing Alpaca message: {e}")
    
    async def _process_single_message(self, msg: dict):
        """Process a single Alpaca message."""
        if not isinstance(msg, dict):
            return
        
        msg_type = msg.get("T")
        symbol = msg.get("S", "").upper()
        
        if not symbol or symbol not in self.subscribed_symbols:
            return
        
        # Handle quotes
        if msg_type == "q":
            bid_price = msg.get("b", 0)
            ask_price = msg.get("a", 0)
            
            # Use mid-price as representative price
            if bid_price > 0 and ask_price > 0:
                price = (bid_price + ask_price) / 2
            else:
                price = ask_price if ask_price > 0 else bid_price
            
            if price > 0:
                # Update cache
                self.price_cache.set(symbol, price)
                await self._publish_price(symbol, price)
        
        # Handle trades
        elif msg_type == "t":
            price = msg.get("p", 0)
            size = msg.get("s", 0)
            
            if price > 0:
                # Update cache
                self.price_cache.set(symbol, price)
                await self._publish_price(symbol, price, volume=size)
    
    async def _publish_price(self, symbol: str, price: float, volume: float = 0):
        """
        Publish price update to WebSocket clients.
        """
        # Calculate price change (simplified - would track previous price)
        cached = self.price_cache.get(symbol)
        if cached:
            change = price - cached
            change_percent = (change / cached * 100) if cached > 0 else 0
        else:
            change = 0
            change_percent = 0
        
        try:
            await publish_price_update(
                symbol=symbol,
                price=price,
                change=change,
                change_percent=change_percent,
                volume=volume,
            )
        except Exception as e:
            logger.error(f"Failed to publish price update: {e}")
    
    async def _run_http_fallback(self):
        """
        HTTP polling fallback when WebSocket unavailable.
        Polls every 5 seconds for subscribed symbols.
        """
        logger.info("Starting HTTP fallback polling (5s interval)")
        
        while self.is_running:
            try:
                if not self.subscribed_symbols:
                    await asyncio.sleep(5)
                    continue
                
                for symbol in list(self.subscribed_symbols):
                    try:
                        price = await self._fetch_price_http(symbol)
                        if price:
                            self.price_cache.set(symbol, price)
                            await self._publish_price(symbol, price)
                    except Exception as e:
                        logger.debug(f"HTTP fetch failed for {symbol}: {e}")
                
                await asyncio.sleep(5)  # Poll every 5 seconds
                
            except asyncio.CancelledError:
                logger.info("HTTP fallback task cancelled")
                break
            except Exception as e:
                logger.error(f"HTTP fallback error: {e}")
                await asyncio.sleep(10)  # Wait longer on error
    
    async def _fetch_price_http(self, symbol: str) -> Optional[float]:
        """
        Fetch price via HTTP API (fallback).
        
        Args:
            symbol: Trading symbol
            
        Returns:
            Current price or None
        """
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(
                    f"https://data.alpaca.markets/v2/stocks/{symbol}/quotes/latest",
                    headers={
                        "Apca-Api-Key-Id": settings.ALPACA_API_KEY,
                        "Apca-Api-Secret-Key": settings.ALPACA_API_SECRET,
                    }
                )
                
                if response.status_code == 200:
                    data = response.json()
                    quote = data.get('quote', {})
                    # Use ask price as representative
                    price = quote.get('askPrice', quote.get('bidPrice', 0))
                    return float(price) if price else None
                    
        except Exception as e:
            logger.debug(f"HTTP price fetch failed: {e}")
        
        return None
    
    async def start_binance_ws(self, symbols: List[str]):
        """
        Start Binance WebSocket for crypto prices.
        
        Args:
            symbols: Crypto symbols (e.g., ["BTCUSDT", "ETHUSDT"])
        """
        if not symbols:
            return
        
        binance_symbols = [s.lower() + "@trade" for s in symbols]
        ws_url = f"{self.binance_ws_url}/{'/'.join(binance_symbols)}"
        
        logger.info(f"Starting Binance WebSocket for {len(symbols)} symbols")
        
        attempt = 0
        while self.is_running:
            try:
                try:
                    from websockets import connect
                except ImportError:
                    logger.error("websockets library not installed")
                    return
                
                async with connect(ws_url) as websocket:
                    logger.info("Connected to Binance WebSocket")
                    
                    async for message in websocket:
                        if not self.is_running:
                            break
                        
                        try:
                            data = json.loads(message)
                            await self._handle_binance_message(data)
                        except:
                            pass
                            
            except Exception as e:
                logger.error(f"Binance WebSocket error: {e}")
                if self.is_running:
                    delay = min(self._reconnect_delays[min(attempt, len(self._reconnect_delays)-1)], self._max_delay)
                    await asyncio.sleep(delay)
                    attempt += 1
    
    async def _handle_binance_message(self, data: dict):
        """Handle Binance trade message."""
        # Binance format:
        # {"e":"trade","E":123456789,"s":"BTCUSDT","t":12345,"p":"40000.00","q":"0.001"}
        symbol = data.get("s", "").upper()
        price_str = data.get("p", "0")
        volume_str = data.get("q", "0")
        
        try:
            price = float(price_str)
            volume = float(volume_str)
        except ValueError:
            return
        
        # Update cache and publish
        self.price_cache.set(symbol, price)
        await self._publish_price(symbol, price, volume)
    
    def get_price(self, symbol: str) -> Optional[float]:
        """
        Get current price for symbol (from cache or WebSocket).
        
        Args:
            symbol: Trading symbol
            
        Returns:
            Current price or None
        """
        # Try cache first
        price = self.price_cache.get(symbol)
        if price:
            return price
        
        # No price available
        logger.warning(f"No price available for {symbol}")
        return None
    
    def get_status(self) -> Dict[str, Any]:
        """Get service status."""
        return {
            "is_running": self.is_running,
            "subscribed_symbols": list(self.subscribed_symbols),
            "subscription_count": len(self.subscribed_symbols),
            "connected": self.last_successful_connection is not None,
            "last_connection": self.last_successful_connection.isoformat() if self.last_successful_connection else None,
            "circuit_breaker_open": self.circuit_breaker.is_open,
            "connection_attempts": self.connection_attempts,
            "cached_prices_count": len(self.price_cache.prices),
            "using_http_fallback": self._ws_task is None and self._http_fallback_task is not None,
        }


# Singleton instance
market_data_service = MarketDataService()


def get_market_data_service() -> MarketDataService:
    """Get the market data service instance."""
    return market_data_service