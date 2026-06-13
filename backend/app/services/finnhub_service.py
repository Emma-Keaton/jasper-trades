"""
Finnhub Market Data Service - Real-time US Stocks WebSocket
=============================================================

Real-time stock market data with WebSocket support.

Features:
- ✅ WebSocket for real-time trades (FREE - 60 calls/min!)
- ✅ Global Quote API for latest price
- ✅ US, HK, Japan stocks
- ✅ Forex, crypto support

API Docs: https://finnhub.io/docs/api
Free Tier: 60 API calls/minute, 30 API calls/SECOND for WebSocket
Notes:
  - Completely FREE - no daily limit (unlike Alpha Vantage)
  - Only requires email signup for token
  - WebSocket streams real-time trades

This is your BEST option for US stock real-time data!
"""
import asyncio
import websockets
import structlog
import httpx
from typing import Dict, Any, Optional, List, Callable
from datetime import datetime
import json

logger = structlog.get_logger(__name__)


class FinnhubService:
    """
    Finnhub Market Data Service.
    
    Real-time WebSocket and HTTP API for US stocks.
    """
    
    # API Endpoints
    WS_URL = "wss://ws.finnhub.io"
    HTTP_URL = "https://finnhub.io/api/v1"
    
    def __init__(self, api_token: Optional[str] = None):
        """
        Initialize Finnhub service.
        
        Args:
            api_token: Finnhub API token (FREE at https://finnhub.io/dashboard)
        """
        self.api_token = api_token
        self.ws = None
        self.connected = False
        self.subscriptions: Dict[str, Callable] = {}  # symbol -> callback
        self._cache: Dict[str, Dict[str, Any]] = {}  # symbol -> latest trade
        self._running = False
        
    async def connect(self) -> bool:
        """
        Connect to Finnhub WebSocket.
        
        Returns:
            bool: True if connected
        """
        if not self.api_token:
            logger.warning("Finnhub API token not configured")
            return False
        
        try:
            self.ws = await websockets.connect(self.WS_URL)
            self.connected = True
            self._running = True
            
            logger.info("Connected to Finnhub WebSocket")
            
            # Authenticate
            auth_msg = {
                "type": "access",
                "token": self.api_token
            }
            await self.ws.send(json.dumps(auth_msg))
            
            # Start message handler
            asyncio.create_task(self._handle_messages())
            
            return True
            
        except Exception as e:
            logger.error(f"Finnhub connection failed: {e}")
            self.connected = False
            return False
    
    async def disconnect(self):
        """Disconnect from Finnhub WebSocket."""
        self._running = False
        self.connected = False
        
        if self.ws:
            # Send close message
            try:
                close_msg = {
                    "type": "close",
                    "token": self.api_token
                }
                await self.ws.send(json.dumps(close_msg))
            except:
                pass
            
            await self.ws.close()
            self.ws = None
            
        logger.info("Disconnected from Finnhub")
    
    async def _handle_messages(self):
        """Handle incoming WebSocket messages."""
        try:
            async for message in self.ws:
                if not self._running:
                    break
                    
                data = json.loads(message)
                await self._process_message(data)
                
        except websockets.ConnectionClosed:
            logger.warning("Finnhub WebSocket closed")
            self.connected = False
            
            # Auto-reconnect
            if self._running:
                await asyncio.sleep(5)
                await self.connect()
                
        except Exception as e:
            logger.error(f"Finnhub message error: {e}")
    
    async def _process_message(self, data: Dict[str, Any]):
        """Process incoming Finnhub message."""
        msg_type = data.get("type")
        
        if msg_type == "trade":
            # Real-time trade data
            trades = data.get("data", [])
            for trade in trades:
                symbol = trade.get("s", "").upper()
                
                # Store latest trade
                self._cache[symbol] = {
                    "price": trade.get("p", 0),
                    "volume": trade.get("v", 0),
                    "timestamp": trade.get("t", 0),  # Unix timestamp in ms
                    "source": "finnhub_ws"
                }
                
                # Call subscription callback
                if symbol in self.subscriptions:
                    await self.subscriptions[symbol](self._cache[symbol])
        
        elif msg_type == "error":
            error_msg = data.get("data", "Unknown error")
            logger.error(f"Finnhub error: {error_msg}")
    
    async def subscribe(self, symbols: List[str]):
        """
        Subscribe to real-time trades for symbols.
        
        Args:
            symbols: List of US stock symbols (e.g., ["AAPL", "TSLA"])
        """
        if not self.connected:
            await self.connect()
        
        for symbol in symbols:
            subscribe_msg = {
                "type": "subscribe",
                "symbol": symbol.upper()
            }
            
            await self.ws.send(json.dumps(subscribe_msg))
            self.subscriptions[symbol.upper()] = lambda data: None  # Placeholder
        
        logger.info(f"Subscribed to {len(symbols)} symbols on Finnhub")
    
    async def set_callback(self, symbol: str, callback: Callable[[Dict[str, Any]], None]):
        """
        Set callback for symbol updates.
        
        Args:
            symbol: Stock symbol
            callback: Async function to call with trade data
        """
        symbol = symbol.upper()
        self.subscriptions[symbol] = callback
        logger.debug(f"Set callback for {symbol}")
    
    async def unsubscribe(self, symbols: List[str]):
        """
        Unsubscribe from symbols.
        
        Args:
            symbols: List of symbols to unsubscribe
        """
        for symbol in symbols:
            unsubscribe_msg = {
                "type": "unsubscribe",
                "symbol": symbol.upper()
            }
            
            await self.ws.send(json.dumps(unsubscribe_msg))
            self.subscriptions.pop(symbol.upper(), None)
        
        logger.info(f"Unsubscribed from {len(symbols)} symbols")
    
    async def get_quote(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Get latest quote via HTTP API.
        
        Args:
            symbol: Stock symbol
            
        Returns:
            Quote dict or None
        """
        if not self.api_token:
            return None
        
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(
                    f"{self.HTTP_URL}/quote",
                    params={
                        "symbol": symbol.upper(),
                        "token": self.api_token
                    }
                )
                
                if response.status_code == 200:
                    data = response.json()
                    return {
                        "price": data.get("c"),  # Current price
                        "high": data.get("h"),
                        "low": data.get("l"),
                        "open": data.get("o"),
                        "previous_close": data.get("pc"),
                        "timestamp": data.get("t"),
                    }
                    
                return None
                
        except Exception as e:
            logger.debug(f"Finnhub quote failed: {e}")
            return None
    
    def get_price(self, symbol: str) -> Optional[float]:
        """
        Get latest cached price from WebSocket.
        
        Args:
            symbol: Stock symbol
            
        Returns:
            Latest price or None
        """
        trade = self._cache.get(symbol.upper())
        return trade.get("price") if trade else None
    
    def is_connected(self) -> bool:
        """Check if connected to Finnhub."""
        return self.connected and self.ws is not None


# Singleton instance
_finnhub_service: Optional[FinnhubService] = None


def get_finnhub_service(api_token: Optional[str] = None) -> FinnhubService:
    """Get or create Finnhub service instance."""
    global _finnhub_service
    if _finnhub_service is None:
        _finnhub_service = FinnhubService(api_token)
    return _finnhub_service


def is_finnhub_available() -> bool:
    """Check if Finnhub is configured and connected."""
    service = get_finnhub_service()
    return service.is_connected()