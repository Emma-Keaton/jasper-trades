"""
MetaTrader 5 Service - Local Windows Integration

This service connects to MetaTrader 5 desktop terminal via the official Python library.
It requires:
1. Windows OS (MT5 is Windows-native)
2. MetaTrader 5 terminal installed
3. Exness broker account configured in MT5 terminal

For cloud hosting (Linux), use Exness REST API service instead.
"""
from typing import Dict, Any, Optional, List
from datetime import datetime
import structlog
import asyncio

logger = structlog.get_logger(__name__)


class MT5Service:
    """MetaTrader 5 integration service for Exness broker."""

    def __init__(self):
        self.mt5 = None
        self.connected = False
        self.account_info: Optional[Dict] = None
        self._initialize()

    def _initialize(self):
        """Initialize MT5 library (only available on Windows with MT5 installed)."""
        try:
            import MetaTrader5 as mt5
            self.mt5 = mt5
            logger.info("MetaTrader5 library loaded successfully")
        except ImportError:
            logger.warning("MetaTrader5 library not available - requires Windows + MT5 installation")
            logger.warning("Use Exness REST API service for cloud/Linux deployment")
        except Exception as e:
            logger.error(f"Failed to load MetaTrader5: {e}")

    async def connect(self, login: int, server: str, password: str, investor_password: str = None) -> bool:
        """
        Connect to MT5 terminal with Exness account.

        Args:
            login: MT5 Login ID (e.g., 87291043)
            server: MT5 server name (e.g., "Exness-MT5-Real6")
            password: Trading password
            investor_password: Investor password (read-only access, optional)

        Returns:
            bool: True if connected successfully
        """
        if not self.mt5:
            logger.error("MT5 library not available")
            return False

        try:
            # Initialize MT5 terminal
            initialized = await asyncio.to_thread(self.mt5.initialize)
            if not initialized:
                error = self.mt5.last_error()
                logger.error(f"MT5 initialization failed: {error}")
                return False

            # Login to account
            logged_in = await asyncio.to_thread(
                self.mt5.login,
                login=login,
                server=server,
                password=password
            )

            if not logged_in:
                error = self.mt5.last_error()
                logger.error(f"MT5 login failed: {error}")
                return False

            # Store account info
            self.connected = True
            self.account_info = await self.get_account_info()

            logger.info(f"Connected to MT5 server: {server}, Account: {login}")
            return True

        except Exception as e:
            logger.error(f"MT5 connection error: {e}")
            self.connected = False
            return False

    def disconnect(self):
        """Disconnect from MT5 terminal."""
        if self.mt5:
            self.mt5.shutdown()
            self.connected = False
            self.account_info = None
            logger.info("Disconnected from MT5")

    async def get_account_info(self) -> Optional[Dict[str, Any]]:
        """Get current account information."""
        if not self.mt5 or not self.connected:
            return None

        account_info = await asyncio.to_thread(self.mt5.account_info)
        if not account_info:
            return None

        return {
            "login": account_info.login,
            "server": account_info.server,
            "balance": account_info.balance,
            "equity": account_info.equity,
            "margin": account_info.margin,
            "free_margin": account_info.margin_free,
            "profit": account_info.profit,
            "currency": account_info.currency,
            "leverage": account_info.leverage,
            "company": account_info.company,
        }

    async def get_positions(self) -> List[Dict[str, Any]]:
        """Get all open positions."""
        if not self.mt5 or not self.connected:
            return []

        positions = await asyncio.to_thread(self.mt5.positions_get)
        if not positions:
            return []

        return [
            {
                "ticket": pos.ticket,
                "symbol": pos.symbol,
                "type": "buy" if pos.type == 0 else "sell",  # 0=buy, 1=sell
                "volume": pos.volume,
                "price_open": pos.price_open,
                "price_current": pos.price_current,
                "sl": pos.sl,
                "tp": pos.tp,
                "profit": pos.profit,
                "time": datetime.fromtimestamp(pos.time),
            }
            for pos in positions
        ]

    async def get_orders(self) -> List[Dict[str, Any]]:
        """Get all pending orders."""
        if not self.mt5 or not self.connected:
            return []

        orders = await asyncio.to_thread(self.mt5.orders_get)
        if not orders:
            return []

        return [
            {
                "ticket": order.ticket,
                "symbol": order.symbol,
                "type": self._get_order_type_name(order.type),
                "volume": order.volume_current,
                "price_open": order.price_open,
                "sl": order.sl,
                "tp": order.tp,
                "time": datetime.fromtimestamp(order.time_setup),
            }
            for order in orders
        ]

    async def market_buy(
        self,
        symbol: str,
        volume: float,
        sl: float = None,
        tp: float = None,
        comment: str = "Jasper Trades"
    ) -> Optional[Dict[str, Any]]:
        """
        Execute market buy order.

        Args:
            symbol: Trading symbol (e.g., "EURUSD")
            volume: Lot size
            sl: Stop loss price (optional)
            tp: Take profit price (optional)
            comment: Order comment

        Returns:
            Order result dict or None
        """
        return await self._execute_order("buy", symbol, volume, sl, tp, comment)

    async def market_sell(
        self,
        symbol: str,
        volume: float,
        sl: float = None,
        tp: float = None,
        comment: str = "Jasper Trades"
    ) -> Optional[Dict[str, Any]]:
        """
        Execute market sell order.

        Args:
            symbol: Trading symbol
            volume: Lot size
            sl: Stop loss price (optional)
            tp: Take profit price (optional)
            comment: Order comment

        Returns:
            Order result dict or None
        """
        return await self._execute_order("sell", symbol, volume, sl, tp, comment)

    async def _execute_order(
        self,
        action: str,
        symbol: str,
        volume: float,
        sl: float = None,
        tp: float = None,
        comment: str = ""
    ) -> Optional[Dict[str, Any]]:
        """Execute order (internal method)."""
        if not self.mt5 or not self.connected:
            logger.error("MT5 not connected")
            return None

        try:
            # Get symbol info
            symbol_info = self.mt5.symbol_info(symbol)
            if not symbol_info or not symbol_info.visible:
                logger.error(f"Symbol {symbol} not available")
                return None

            # Get current price
            tick = self.mt5.symbol_info_tick(symbol)
            price = tick.ask if action == "buy" else tick.bid

            # Prepare order request
            request = {
                "action": self.mt5.TRADE_ACTION_DEAL,
                "symbol": symbol,
                "volume": volume,
                "type": self.mt5.ORDER_TYPE_BUY if action == "buy" else self.mt5.ORDER_TYPE_SELL,
                "price": price,
                "sl": sl if sl else 0,
                "tp": tp if tp else 0,
                "deviation": 20,  # Max price deviation in points
                "magic": 234000,  # Magic number for EA identification
                "comment": comment,
                "type_time": self.mt5.ORDER_TIME_GTC,  # Good till cancelled
                "type_filling": self.mt5.ORDER_FILLING_IOC,  # Immediate or cancel
            }

            # Send order
            result = await asyncio.to_thread(self.mt5.order_send, request)

            if result.retcode != self.mt5.TRADE_RETCODE_DONE:
                logger.error(f"Order failed: {result.comment}")
                return {
                    "success": False,
                    "error": result.comment,
                    "retcode": result.retcode,
                }

            logger.info(f"Order executed: {action} {volume} {symbol} @ {price}")
            return {
                "success": True,
                "ticket": result.order,
                "deal": result.deal,
                "volume": result.volume,
                "price": result.price,
                "profit": result.profit,
            }

        except Exception as e:
            logger.error(f"Order execution error: {e}")
            return {
                "success": False,
                "error": str(e),
            }

    async def close_position(self, ticket: int) -> Optional[Dict[str, Any]]:
        """Close an open position by ticket."""
        if not self.mt5 or not self.connected:
            return None

        try:
            position = self.mt5.positions_get(ticket=ticket)
            if not position:
                return {"success": False, "error": f"Position {ticket} not found"}

            pos = position[0]
            close_volume = pos.volume
            close_price = pos.price_current

            # Prepare close request
            request = {
                "action": self.mt5.TRADE_ACTION_DEAL,
                "symbol": pos.symbol,
                "volume": close_volume,
                "type": self.mt5.ORDER_TYPE_SELL if pos.type == 0 else self.mt5.ORDER_TYPE_BUY,
                "price": close_price,
                "position": ticket,
                "deviation": 20,
                "magic": 234000,
                "comment": "Close position",
                "type_time": self.mt5.ORDER_TIME_GTC,
                "type_filling": self.mt5.ORDER_FILLING_IOC,
            }

            result = await asyncio.to_thread(self.mt5.order_send, request)

            if result.retcode != self.mt5.TRADE_RETCODE_DONE:
                return {
                    "success": False,
                    "error": result.comment,
                    "retcode": result.retcode,
                }

            logger.info(f"Position {ticket} closed: {close_volume} {pos.symbol} @ {close_price}")
            return {
                "success": True,
                "deal": result.deal,
                "profit": result.profit,
            }

        except Exception as e:
            logger.error(f"Close position error: {e}")
            return {"success": False, "error": str(e)}

    async def get_historical_orders(
        self,
        from_date: datetime,
        to_date: datetime = None
    ) -> List[Dict[str, Any]]:
        """Get historical orders within date range."""
        if not self.mt5 or not self.connected:
            return []

        if to_date is None:
            to_date = datetime.now()

        try:
            orders = await asyncio.to_thread(
                self.mt5.history_orders_get,
                from_date,
                to_date
            )

            if not orders:
                return []

            return [
                {
                    "ticket": order.ticket,
                    "symbol": order.symbol,
                    "type": self._get_order_type_name(order.type),
                    "volume": order.volume_current,
                    "price_open": order.price_open,
                    "price_close": order.price_close,
                    "profit": order.profit,
                    "time": datetime.fromtimestamp(order.time_setup),
                    "time_done": datetime.fromtimestamp(order.time_done),
                }
                for order in orders
            ]
        except Exception as e:
            logger.error(f"Get historical orders error: {e}")
            return []

    async def get_symbols(self) -> List[str]:
        """Get list of available symbols."""
        if not self.mt5:
            return []

        symbols = await asyncio.to_thread(self.mt5.symbols_get)
        if not symbols:
            return []

        return [s.name for s in symbols if s.visible]

    def _get_order_type_name(self, order_type: int) -> str:
        """Convert MT5 order type to readable name."""
        if not self.mt5:
            return "unknown"

        type_map = {
            self.mt5.ORDER_TYPE_BUY: "buy",
            self.mt5.ORDER_TYPE_SELL: "sell",
            self.mt5.ORDER_TYPE_BUY_LIMIT: "buy_limit",
            self.mt5.ORDER_TYPE_SELL_LIMIT: "sell_limit",
            self.mt5.ORDER_TYPE_BUY_STOP: "buy_stop",
            self.mt5.ORDER_TYPE_SELL_STOP: "sell_stop",
        }
        return type_map.get(order_type, "unknown")

    def is_available(self) -> bool:
        """Check if MT5 library is available (Windows + installed)."""
        return self.mt5 is not None

    def is_connected(self) -> bool:
        """Check if connected to MT5 terminal."""
        return self.connected


# Singleton instance
_mt5_service: Optional[MT5Service] = None


def get_mt5_service() -> MT5Service:
    """Get MT5 service singleton."""
    global _mt5_service
    if _mt5_service is None:
        _mt5_service = MT5Service()
    return _mt5_service


def is_mt5_available() -> bool:
    """Check if MT5 is available on this system."""
    service = get_mt5_service()
    return service.is_available()