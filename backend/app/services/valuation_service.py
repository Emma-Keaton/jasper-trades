"""
Valuation Service - Real-time price fetching and position valuation.
"""
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
import structlog

from app.brokers import get_broker, get_broker_for_asset
from app.brokers.ccxt_service import CCXTBrokerService
from app.brokers.registry import get_broker_for_asset as _get_broker_for_asset

logger = structlog.get_logger(__name__)


class ValuationService:
    """
    Valuation Service - Fetch prices and calculate position values.

    Features:
    - Multi-source price fetching (CCXT, cTrader, etc.)
    - Price caching with TTL
    - Batch price fetching
    - Fallback logic between providers
    """

    def __init__(self):
        # Price cache: {symbol: {"price": float, "timestamp": datetime}}
        self._price_cache: Dict[str, Dict[str, Any]] = {}
        self._cache_ttl_seconds = 60  # 1 minute cache

    async def get_price(
        self,
        symbol: str,
        use_cache: bool = True,
    ) -> Optional[float]:
        """
        Get current price for a symbol.

        Args:
            symbol: Trading symbol (e.g., "AAPL", "BTC")
            use_cache: Whether to use cached price

        Returns:
            Current price or None
        """
        symbol_upper = symbol.upper()

        # Check cache first
        if use_cache:
            cached = self._get_cached_price(symbol_upper)
            if cached is not None:
                return cached

        # Determine asset class and fetch price
        price = None

        # Try to identify asset class
        asset_class = self._identify_asset_class(symbol_upper)

        if asset_class == "crypto":
            price = await self._fetch_crypto_price(symbol_upper)
        elif asset_class in ["stocks", "etf"]:
            price = await self._fetch_stock_price(symbol_upper)
        else:
            # Try both sources
            price = await self._fetch_crypto_price(symbol_upper)
            if price is None:
                price = await self._fetch_stock_price(symbol_upper)

        # Cache the result
        if price is not None:
            self._cache_price(symbol_upper, price)

        return price

    async def get_prices(
        self,
        symbols: List[str],
        use_cache: bool = True,
    ) -> Dict[str, float]:
        """
        Get prices for multiple symbols.

        Args:
            symbols: List of symbols
            use_cache: Whether to use cached prices

        Returns:
            Dict of symbol -> price
        """
        prices = {}

        # Group by asset class for efficient fetching
        stocks = []
        crypto = []

        for symbol in symbols:
            symbol_upper = symbol.upper()

            # Check cache first
            if use_cache:
                cached = self._get_cached_price(symbol_upper)
                if cached is not None:
                    prices[symbol_upper] = cached
                    continue

            asset_class = self._identify_asset_class(symbol_upper)
            if asset_class in ["stocks", "etf"]:
                stocks.append(symbol_upper)
            elif asset_class == "crypto":
                crypto.append(symbol_upper)
            else:
                # Try crypto first, then stocks
                crypto.append(symbol_upper)

        # Fetch stock prices
        if stocks:
            stock_prices = await self._fetch_stock_prices(stocks)
            prices.update(stock_prices)

        # Fetch crypto prices
        if crypto:
            crypto_prices = await self._fetch_crypto_prices(crypto)
            prices.update(crypto_prices)

        return prices

    async def update_position_prices(
        self,
        positions: List[Any],
    ) -> Dict[str, float]:
        """
        Update prices for a list of positions.

        Args:
            positions: List of Position objects

        Returns:
            Dict of symbol -> new price
        """
        symbols = [p.symbol for p in positions if p.quantity > 0]
        return await self.get_prices(symbols)

    # ========== Cache Management ==========

    def _get_cached_price(self, symbol: str) -> Optional[float]:
        """Get price from cache if not expired."""
        if symbol not in self._price_cache:
            return None

        cache_entry = self._price_cache[symbol]
        age = datetime.utcnow() - cache_entry["timestamp"]

        if age > timedelta(seconds=self._cache_ttl_seconds):
            # Cache expired
            logger.debug(f"Cache expired for {symbol}")
            return None

        return cache_entry["price"]

    def _cache_price(self, symbol: str, price: float) -> None:
        """Cache a price."""
        self._price_cache[symbol] = {
            "price": price,
            "timestamp": datetime.utcnow(),
        }

    def clear_cache(self, symbol: Optional[str] = None) -> None:
        """
        Clear price cache.

        Args:
            symbol: Clear specific symbol or all
        """
        if symbol:
            self._price_cache.pop(symbol.upper(), None)
        else:
            self._price_cache.clear()

    # ========== Price Fetching - Stocks ==========

    async def _fetch_stock_price(self, symbol: str) -> Optional[float]:
        """
        Fetch stock price.

        Args:
            symbol: Stock symbol

        Returns:
            Current price or None
        """
        try:
            broker = _get_broker_for_asset("stocks")
            if not broker or not broker.is_connected:
                logger.debug("Stock broker not configured, skipping price fetch")
                return None

            # Get market data - use generic broker interface
            market_data = await broker.get_market_data(symbol)
            if market_data and "ask" in market_data:
                return float(market_data["ask"])
            elif market_data and "last" in market_data:
                return float(market_data["last"])

            # Alternative: Get position to get current price
            position = await broker.get_position(symbol)
            if position and position.current_price:
                return float(position.current_price)

        except Exception as e:
            logger.warning(f"Failed to fetch stock price for {symbol}: {e}")

        return None

    async def _fetch_stock_prices(self, symbols: List[str]) -> Dict[str, float]:
        """
        Fetch multiple stock prices.

        Args:
            symbols: List of stock symbols

        Returns:
            Dict of symbol -> price
        """
        prices = {}

        try:
            broker = _get_broker_for_asset("stocks")
            if not broker or not broker.is_connected:
                logger.warning("Stock broker not connected")
                return prices

            for symbol in symbols:
                price = await self._fetch_stock_price(symbol)
                if price:
                    prices[symbol] = price

        except Exception as e:
            logger.error(f"Error fetching stock prices: {e}")

        return prices

    # ========== Price Fetching - Crypto ==========

    async def _fetch_crypto_price(self, symbol: str) -> Optional[float]:
        """
        Fetch crypto price via the market-data router
        (CoinGecko -> CCXT -> CoinLore). No longer depends on a connected
        Binance broker.
        """
        try:
            from app.services.market_data_router import get_market_data_router

            result = await get_market_data_router().get_price(symbol)
            price = result.get("price")
            return float(price) if price else None
        except Exception as e:
            logger.warning(f"Failed to fetch crypto price for {symbol}: {e}")
            return None

    async def _fetch_crypto_prices(self, symbols: List[str]) -> Dict[str, float]:
        """Fetch multiple crypto prices via the market-data router."""
        prices = {}
        for symbol in symbols:
            price = await self._fetch_crypto_price(symbol)
            if price:
                prices[symbol] = price
        return prices

    # ========== Utilities ==========

    def _identify_asset_class(self, symbol: str) -> str:
        """
        Identify asset class from symbol.

        Returns:
            "stocks", "crypto", or "unknown"
        """
        # Common crypto symbols
        crypto_symbols = {
            "BTC", "ETH", "SOL", "BNB", "XRP", "ADA", "DOGE", "DOT",
            "MATIC", "LINK", "AVAX", "UNI", "ATOM", "LTC", "BCH",
            "JUP", "RAY", "ORCA", "BONK",
        }

        if symbol.upper() in crypto_symbols:
            return "crypto"

        # Stock symbols are typically 2-5 characters
        if 2 <= len(symbol) <= 5 and symbol.isalpha():
            return "stocks"

        # ETFs also fit this pattern
        if len(symbol) == 3 and symbol.isalpha():
            return "etf"

        return "unknown"

    async def get_portfolio_value(
        self,
        positions: List[Any],
        cash: float = 0,
    ) -> Dict[str, float]:
        """
        Calculate total portfolio value.

        Args:
            positions: List of Position objects
            cash: Cash balance

        Returns:
            Dict with portfolio metrics
        """
        # Get all prices
        symbols = [p.symbol for p in positions if p.quantity > 0]
        prices = await self.get_prices(symbols)

        # Calculate values
        total_market_value = 0
        total_cost_basis = 0

        for position in positions:
            if position.quantity <= 0:
                continue

            price = prices.get(position.symbol, position.current_price or position.avg_price)
            market_value = position.quantity * price
            cost_basis = position.quantity * position.avg_price

            total_market_value += market_value
            total_cost_basis += cost_basis

        total_value = cash + total_market_value
        total_pnl = total_market_value - total_cost_basis
        pnl_percent = (total_pnl / total_cost_basis * 100) if total_cost_basis > 0 else 0

        return {
            "total_value": total_value,
            "cash": cash,
            "market_value": total_market_value,
            "cost_basis": total_cost_basis,
            "unrealized_pnl": total_pnl,
            "unrealized_pnl_percent": pnl_percent,
        }

    async def calculate_performance(
        self,
        portfolio_id: int,
        positions: List[Any],
        initial_value: float,
        current_cash: float,
    ) -> Dict[str, Any]:
        """
        Calculate portfolio performance metrics.

        Returns:
            Dict with performance metrics
        """
        valuation = await self.get_portfolio_value(positions, current_cash)

        total_value = valuation["total_value"]
        total_return = total_value - initial_value
        total_return_percent = (total_return / initial_value * 100) if initial_value > 0 else 0

        return {
            "initial_value": initial_value,
            "current_value": total_value,
            "total_return": total_return,
            "total_return_percent": total_return_percent,
            "unrealized_pnl": valuation["unrealized_pnl"],
            "market_value": valuation["market_value"],
            "cash": current_cash,
        }
