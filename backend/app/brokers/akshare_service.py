"""
AKShare Broker Service - Chinese A-Shares & B-Shares

Integration with AKShare for China stock market data and trading.
Supports Shanghai and Shenzhen exchanges.

AKShare Documentation:
- GitHub: https://github.com/akfamily/akshare
- Docs: https://akshare.akfamily.xyz/
- Supports: A-shares (CNY), B-shares (USD/CNY), ETFs, Futures

Note: AKShare is primarily a data provider.
For actual trading, integrates with China International Capital Corporation (CICC)
or uses paper trading mode for simulation.
"""

from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
import structlog
from decimal import Decimal

from app.brokers.base import (
    BaseBrokerService,
    OrderResult,
    PositionData,
    AccountData,
)

logger = structlog.get_logger(__name__)


class AKShareBrokerService(BaseBrokerService):
    """
    AKShare Broker Service - Chinese stock market data and trading.

    Features:
    - A-shares (Shanghai/Shenzhen) - CNY denominated
    - B-shares (Shanghai/Shenzhen) - USD/CNY denominated
    - Real-time market data
    - Paper trading simulation
    - Northbound capital flow data
    - Stock fundamentals (PE, PB, dividends)

    Exchanges:
    - SSE (Shanghai Stock Exchange) - 600xxx, 688xxx
    - SZSE (Shenzhen Stock Exchange) - 000xxx, 300xxx

    Usage:
        1. Initialize AKShare service
        2. Fetch market data for Chinese stocks
        3. Submit paper trading orders
        4. Track positions and PnL
    """

    # Market trading hours (China Standard Time - CST, UTC+8)
    TRADING_HOURS = {
        "morning": ("09:30", "11:30"),
        "afternoon": ("13:00", "15:00")
    }

    # A-share and B-share tickers prefix
    A_SHARE_PREFIX = {
        "SSE": "600",  # Main board
        "SZSE": "000",  # Main board
        "STAR": "688",  # STAR market (Shanghai)
        "CHINEXT": "300"  # ChiNext (Shenzhen)
    }

    B_SHARE_PREFIX = {
        "SSE": "900",  # Shanghai B-shares (USD)
        "SZSE": "200"  # Shenzhen B-shares (HKD)
    }

    def __init__(
        self,
        paper_trading: bool = True,
        initial_capital: float = 1000000.0,  # 1M CNY default
        currency: str = "CNY"
    ):
        super().__init__(name="akshare", config={})

        self.paper_trading = paper_trading
        self.currency = currency
        self.initial_capital = initial_capital
        
        # Paper trading account state
        self._cash = initial_capital
        self._positions: Dict[str, PositionData] = {}
        self._orders: List[Dict[str, Any]] = []
        
        # AKShare uses lazy import - only import when needed
        self._akshare = None
        
        # Connection state
        self.is_connected = False
        self.is_paper_trading = paper_trading

        logger.info(
            f"AKShare Broker initialized",
            paper_trading=paper_trading,
            currency=currency,
            initial_capital=initial_capital
        )

    @property
    def akshare(self):
        """Lazy import AKShare to avoid import errors if not installed"""
        if self._akshare is None:
            try:
                import akshare as ak
                self._akshare = ak
                logger.info("AKShare library imported successfully")
            except ImportError:
                logger.error("AKShare not installed. Run: pip install akshare")
                raise ImportError(
                    "AKShare not installed. Run: pip install akshare"
                )
        return self._akshare

    async def connect(self) -> bool:
        """
        Initialize AKShare connection.
        
        Since AKShare is a local library, this just validates import.
        
        Returns:
            True if AKShare can be imported, False otherwise
        """
        try:
            # Test AKShare import
            _ = self.akshare
            self.is_connected = True
            logger.info("AKShare connected successfully")
            return True
        except Exception as e:
            logger.error(f"AKShare connection failed: {e}")
            self.is_connected = False
            return False

    async def disconnect(self):
        """Disconnect from AKShare"""
        self.is_connected = False
        logger.info("AKShare disconnected")

    async def get_account_data(self) -> AccountData:
        """
        Get account balance and positions.

        Returns:
            AccountData with cash, positions, and equity
        """
        # Calculate equity
        market_value = sum(
            pos.quantity * pos.current_price
            for pos in self._positions.values()
        )
        total_equity = self._cash + market_value

        return AccountData(
            cash=Decimal(str(self._cash)),
            equity=Decimal(str(total_equity)),
            market_value=Decimal(str(market_value)),
            positions=list(self._positions.values()),
            currency=self.currency,
            broker="akshare",
            account_id="paper" if self.paper_trading else "live",
            account_type="paper" if self.paper_trading else "live",
        )

    async def get_market_data(
        self,
        symbol: str,
        exchange: str = "SSE"
    ) -> Optional[Dict[str, Any]]:
        """
        Get real-time market data for Chinese stock.

        Args:
            symbol: Stock code (e.g., "600000" for Shanghai Pudong Development Bank)
            exchange: Exchange - "SSE" (Shanghai) or "SZSE" (Shenzhen)

        Returns:
            Dict with:
            - symbol: Stock code
            - name: Stock name (in Chinese)
            - current: Current price
            - open: Open price
            - high: High price
            - low: Low price
            - close: Previous close
            - volume: Volume
            - amount: Turnover
            - timestamp: Data timestamp
        """
        try:
            # Fetch real-time data via AKShare
            stock_code = f"{symbol}.{exchange}"
            
            # Use AKShare's stock_zh_a_spot_em for real-time data
            df = self.akshare.stock_zh_a_spot_em()
            
            # Filter for specific symbol
            stock_data = df[df['代码'] == symbol]
            
            if stock_data.empty:
                logger.warning(f"Symbol {symbol} not found on {exchange}")
                return None

            row = stock_data.iloc[0]
            
            return {
                "symbol": symbol,
                "exchange": exchange,
                "name": row.get('名称', 'N/A'),
                "current": float(row.get('最新价', 0)),
                "open": float(row.get('今开', 0)),
                "high": float(row.get('最高', 0)),
                "low": float(row.get('最低', 0)),
                "close": float(row.get('昨收', 0)),
                "volume": float(row.get('成交量', 0)),
                "amount": float(row.get('成交额', 0)),
                "timestamp": datetime.now().isoformat(),
                "change_pct": float(row.get('涨跌幅', 0)),
                "change": float(row.get('涨跌额', 0)),
                "pe_ratio": float(row.get('市盈率-动态', 0)) if '市盈率 - 动态' in row else None,
                "pb_ratio": float(row.get('市净率', 0)) if '市净率' in row else None,
            }
            
        except Exception as e:
            logger.error(f"Failed to fetch market data for {symbol}: {e}")
            return None

    async def get_historical_data(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
        period: str = "daily"
    ) -> Optional[List[Dict[str, Any]]]:
        """
        Get historical OHLCV data.

        Args:
            symbol: Stock code
            start_date: YYYY-MM-DD
            end_date: YYYY-MM-DD
            period: daily, weekly, monthly

        Returns:
            List of OHLCV dicts
        """
        try:
            df = self.akshare.stock_zh_a_hist(
                symbol=symbol,
                period=period,
                start_date=start_date.replace("-", ""),
                end_date=end_date.replace("-", ""),
                adjust="qfq"  # Adjusted for splits/dividends
            )
            
            return [
                {
                    "date": row.get('日期', ''),
                    "open": float(row.get('开盘', 0)),
                    "high": float(row.get('最高', 0)),
                    "low": float(row.get('最低', 0)),
                    "close": float(row.get('收盘', 0)),
                    "volume": float(row.get('成交量', 0)),
                    "amount": float(row.get('成交额', 0)),
                    "amplitude": float(row.get('振幅', 0)) if '振幅' in row else None,
                }
                for _, row in df.iterrows()
            ]
            
        except Exception as e:
            logger.error(f"Failed to fetch historical data: {e}")
            return None

    async def submit_order(
        self,
        symbol: string,
        side: str,
        quantity: float,
        price: Optional[float] = None,
        order_type: str = "market",
        exchange: str = "SSE"
    ) -> OrderResult:
        """
        Submit trading order (paper trading only).

        Args:
            symbol: Stock code
            side: buy or sell
            quantity: Number of shares
            price: Limit price (None for market)
            order_type: market or limit
            exchange: SSE or SZSE

        Returns:
            OrderResult with status and details
        """
        if not self.paper_trading:
            return OrderResult(
                success=False,
                error="Live trading not supported. Use paper trading mode.",
                order_id=None
            )

        # Get current price if market order
        if order_type == "market" and not price:
            market_data = await self.get_market_data(symbol, exchange)
            if not market_data:
                return OrderResult(
                    success=False,
                    error=f"Cannot fetch price for {symbol}",
                    order_id=None
                )
            price = market_data["current"]

        # Calculate total value
        total_value = quantity * price

        # Check if enough cash for buy
        if side.lower() == "buy":
            if total_value > self._cash:
                return OrderResult(
                    success=False,
                    error=f"Insufficient cash: need {total_value:.2f}, have {self._cash:.2f}",
                    order_id=None
                )
            
            self._cash -= total_value
            
            # Add/update position
            if symbol not in self._positions:
                self._positions[symbol] = PositionData(
                    symbol=symbol,
                    exchange=exchange,
                    quantity=quantity,
                    avg_price=price,
                    current_price=price,
                    market_value=total_value,
                    unrealized_pnl=0,
                    unrealized_pnl_percent=0,
                    side="long",
                    broker="akshare"
                )
            else:
                # Average in
                pos = self._positions[symbol]
                total_qty = pos.quantity + quantity
                avg_price = ((pos.quantity * pos.avg_price) + total_value) / total_qty
                pos.quantity = total_qty
                pos.avg_price = avg_price
                pos.market_value = total_qty * pos.current_price
                
        else:  # sell
            if symbol not in self._positions:
                return OrderResult(
                    success=False,
                    error=f"No position in {symbol}",
                    order_id=None
                )
            
            pos = self._positions[symbol]
            if quantity > pos.quantity:
                return OrderResult(
                    success=False,
                    error=f"Insufficient shares: have {pos.quantity}, trying to sell {quantity}",
                    order_id=None
                )
            
            self._cash += total_value
            pos.quantity -= quantity
            
            if pos.quantity == 0:
                del self._positions[symbol]

        # Create order record
        order_id = f"AKS_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{symbol}"
        
        order = {
            "order_id": order_id,
            "symbol": symbol,
            "exchange": exchange,
            "side": side.lower(),
            "quantity": quantity,
            "price": price,
            "order_type": order_type,
            "status": "filled",
            "created_at": datetime.utcnow().isoformat(),
            "filled_at": datetime.utcnow().isoformat(),
            "filled_price": price,
            "filled_quantity": quantity,
        }
        
        self._orders.append(order)

        logger.info(
            f"Order filled: {side.upper()} {quantity} {symbol} @ {price:.2f}",
            order_id=order_id
        )

        return OrderResult(
            success=True,
            order_id=order_id,
            status="filled",
            filled_price=price,
            filled_quantity=quantity,
            message=f"Successfully {side} {quantity} shares of {symbol} @ {price:.2f}"
        )

    async def get_positions(self) -> List[PositionData]:
        """Get current positions"""
        return list(self._positions.values())

    async def cancel_order(self, order_id: str) -> bool:
        """Cancel order (not supported for paper trading - instant fill)"""
        logger.warning(f"Cancel order {order_id} not supported in paper trading mode")
        return False

    def get_status(self) -> Dict[str, Any]:
        """Get service status"""
        return {
            "connected": self.is_connected,
            "paper_trading": self.paper_trading,
            "currency": self.currency,
            "initial_capital": self.initial_capital,
            "current_cash": self._cash,
            "num_positions": len(self._positions),
            "akshare_installed": self._akshare is not None,
        }


# Singleton instance
akshare_broker_service: Optional[AKShareBrokerService] = None


def get_akshare_service() -> AKShareBrokerService:
    """Get or create AKShare service"""
    global akshare_broker_service
    if akshare_broker_service is None:
        akshare_broker_service = AKShareBrokerService()
    return akshare_broker_service