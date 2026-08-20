"""
Market Data Service - Multi-Provider with Free Tier Support

Supports:
1. CoinGecko - FREE, no API key required (crypto prices)
2. Alpha Vantage - FREE tier (5 calls/min, 500/day) - stocks, forex, crypto
3. Finnhub - FREE tier (60 calls/min) - real-time stock prices
4. Twelve Data - FREE tier (800 calls/day) - stocks, forex, crypto
5. Polygon.io - FREE tier (5 calls/min) - stocks

All providers are configurable via Settings page.
CoinGecko works immediately without API key.
"""
from typing import Dict, Any, Optional, List
from datetime import datetime
import structlog
import httpx

logger = structlog.get_logger(__name__)


class MarketDataService:
    """Multi-provider market data service."""

    def __init__(self):
        self.config = {
            'coingecko_enabled': True,  # Always on, no key needed
            'alphavantage_key': None,
            'finnhub_key': None,
            'twelvedata_key': None,
            'polygon_key': None,
            'cmc_key': None,
        }
        
        # API endpoints
        self.COINGECKO_API = "https://api.coingecko.com/api/v3"
        self.ALPHA_VANTAGE_API = "https://www.alphavantage.co/query"
        self.FINNHUB_API = "https://finnhub.io/api/v1"
        self.TWELVE_DATA_API = "https://api.twelvedata.com"
        self.POLYGON_API = "https://api.polygon.io"

    def configure(self, config: Dict[str, Any]):
        """Configure API keys from settings."""
        self.config.update(config)
        logger.info("Market data service configured", 
                   alphavantage=bool(config.get('alphavantage_key')),
                   finnhub=bool(config.get('finnhub_key')),
                   twelvedata=bool(config.get('twelvedata_key')),
                   polygon=bool(config.get('polygon_key')))

    # ============ CoinGecko (FREE - No API Key) ============

    async def get_crypto_prices_coingecko(self, coin_ids: List[str]) -> Dict[str, Any]:
        """
        Get crypto prices from CoinGecko (FREE, no API key).
        
        Args:
            coin_ids: CoinGecko coin IDs (e.g., ['bitcoin', 'ethereum'])
        
        Returns:
            Price data for each coin
        """
        try:
            ids_str = ','.join(coin_ids)
            url = f"{self.COINGECKO_API}/coins/markets"
            params = {
                'vs_currency': 'usd',
                'ids': ids_str,
                'order': 'market_cap_desc',
                'per_page': 100,
                'page': 1,
                'sparkline': False,
                'price_change_percentage': '24h'
            }

            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()
                data = response.json()

            # Parse into clean format
            prices = {}
            for coin in data:
                prices[coin['symbol'].upper()] = {
                    'name': coin['name'],
                    'price_usd': coin['current_price'],
                    'market_cap': coin['market_cap'],
                    'volume_24h': coin['total_volume'],
                    'price_change_24h': coin['price_change_percentage_24h'],
                    'high_24h': coin['high_24h'],
                    'low_24h': coin['low_24h'],
                    'circulating_supply': coin['circulating_supply'],
                }

            logger.info(f"CoinGecko prices fetched: {len(prices)} coins")
            return {'success': True, 'data': prices, 'provider': 'coingecko'}

        except Exception as e:
            logger.error(f"CoinGecko error: {e}")
            return {'success': False, 'error': str(e), 'provider': 'coingecko'}

    async def get_crypto_price_single_coingecko(self, coin_id: str) -> Dict[str, Any]:
        """Get single coin price from CoinGecko."""
        try:
            url = f"{self.COINGECKO_API}/coins/{coin_id}"
            params = {'localization': False, 'tickers': False, 'market_data': True}

            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()
                data = response.json()

            market_data = data.get('market_data', {})
            return {
                'success': True,
                'data': {
                    'name': data.get('name', coin_id),
                    'symbol': data.get('symbol', coin_id).upper(),
                    'price_usd': market_data.get('current_price', {}).get('usd'),
                    'market_cap': market_data.get('market_cap', {}).get('usd'),
                    'volume_24h': market_data.get('total_volume', {}).get('usd'),
                    'price_change_24h': market_data.get('price_change_percentage_24h_in_currency', {}).get('usd'),
                    'high_24h': market_data.get('high_24h', {}).get('usd'),
                    'low_24h': market_data.get('low_24h', {}).get('usd'),
                    'ath': market_data.get('ath', {}).get('usd'),  # All-time high
                    'atl': market_data.get('atl', {}).get('usd'),  # All-time low
                },
                'provider': 'coingecko'
            }

        except Exception as e:
            logger.error(f"CoinGecko single coin error: {e}")
            return {'success': False, 'error': str(e), 'provider': 'coingecko'}

    async def get_trending_coins_coingecko(self) -> Dict[str, Any]:
        """Get trending crypto searches on CoinGecko."""
        try:
            url = f"{self.COINGECKO_API}/search/trending"

            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url)
                response.raise_for_status()
                data = response.json()

            trending = []
            for item in data.get('items', []):
                coin = item.get('item', {})
                trending.append({
                    'coin_id': coin.get('id'),
                    'symbol': coin.get('symbol'),
                    'name': coin.get('name'),
                    'thumb': coin.get('thumb'),
                    'price_btc': coin.get('price_btc'),
                })

            return {'success': True, 'data': {'trending': trending}, 'provider': 'coingecko'}

        except Exception as e:
            logger.error(f"CoinGecko trending error: {e}")
            return {'success': False, 'error': str(e), 'provider': 'coingecko'}

    async def get_top_gainers_losers_coingecko(self) -> Dict[str, Any]:
        """Get top gainers and losers (24h)."""
        try:
            url = f"{self.COINGECKO_API}/coins/markets"
            params = {
                'vs_currency': 'usd',
                'order': 'price_change_percentage_desc',  # Best gainers first
                'per_page': 250,
                'page': 1,
            }

            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()
                data = response.json()

            # Top 10 gainers (first in sorted list)
            gainers = data[:10]
            # Top 10 losers (last in sorted list, reversed)
            losers = list(reversed(data[-10:]))

            def format_coin(coin):
                return {
                    'symbol': coin['symbol'].upper(),
                    'name': coin['name'],
                    'price_usd': coin['current_price'],
                    'change_24h': coin['price_change_percentage_24h'],
                }

            return {
                'success': True,
                'data': {
                    'top_gainers': [format_coin(c) for c in gainers],
                    'top_losers': [format_coin(c) for c in losers],
                },
                'provider': 'coingecko'
            }

        except Exception as e:
            logger.error(f"CoinGecko gainers/losers error: {e}")
            return {'success': False, 'error': str(e), 'provider': 'coingecko'}

    # ============ CoinMarketCap (optional - CMC_API_KEY) ============

    async def get_crypto_prices_coinmarketcap(self, symbols: List[str]) -> Dict[str, Any]:
        """Bulk crypto quotes from CoinMarketCap. Requires CMC_API_KEY."""
        from app.services.coinmarketcap_service import get_coinmarketcap_service

        service = get_coinmarketcap_service()
        if not service.configured:
            return {'success': False, 'error': 'CMC_API_KEY not configured', 'provider': 'coinmarketcap'}
        result = await service.get_quotes(symbols)
        if not result.get('success'):
            # Single-symbol fallback
            prices = {}
            for sym in symbols:
                quote = await service.get_price(sym)
                if quote:
                    prices[quote.get('symbol', sym).upper()] = {
                        'name': sym,
                        'price_usd': quote['price'],
                        'market_cap': quote.get('market_cap'),
                        'volume_24h': quote.get('volume_24h'),
                        'price_change_24h': quote.get('price_change_24h'),
                    }
            if prices:
                return {'success': True, 'data': prices, 'provider': 'coinmarketcap'}
            return {'success': False, 'error': 'no data', 'provider': 'coinmarketcap'}
        return result

    # ============ Alpha Vantage (FREE tier) ============

    async def get_stock_price_alphavantage(self, symbol: str) -> Dict[str, Any]:
        """
        Get stock price from Alpha Vantage.
        FREE tier: 5 calls/min, 500 calls/day
        """
        if not self.config.get('alphavantage_key'):
            return {'success': False, 'error': 'Alpha Vantage API key not configured', 'provider': 'alphavantage'}

        try:
            url = self.ALPHA_VANTAGE_API
            params = {
                'function': 'GLOBAL_QUOTE',
                'symbol': symbol,
                'apikey': self.config['alphavantage_key']
            }

            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()
                data = response.json()

            quote = data.get('Global Quote', {})
            if not quote:
                return {'success': False, 'error': 'No data found', 'provider': 'alphavantage'}

            return {
                'success': True,
                'data': {
                    'symbol': quote.get('01. symbol'),
                    'price': float(quote.get('05. price', 0)),
                    'change': float(quote.get('09. change', 0)),
                    'change_percent': quote.get('10. change percent'),
                    'high': float(quote.get('03. high', 0)),
                    'low': float(quote.get('04. low', 0)),
                    'open': float(quote.get('02. open', 0)),
                    'previous_close': float(quote.get('07. previous close', 0)),
                    'volume': int(quote.get('06. volume', 0)),
                },
                'provider': 'alphavantage'
            }

        except Exception as e:
            logger.error(f"Alpha Vantage error: {e}")
            return {'success': False, 'error': str(e), 'provider': 'alphavantage'}

    async def get_forex_rate_alphavantage(self, from_currency: str, to_currency: str) -> Dict[str, Any]:
        """Get forex exchange rate from Alpha Vantage."""
        if not self.config.get('alphavantage_key'):
            return {'success': False, 'error': 'Alpha Vantage API key not configured', 'provider': 'alphavantage'}

        try:
            url = self.ALPHA_VANTAGE_API
            params = {
                'function': 'CURRENCY_EXCHANGE_RATE',
                'from_currency': from_currency,
                'to_currency': to_currency,
                'apikey': self.config['alphavantage_key']
            }

            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()
                data = response.json()

            rate = data.get('Realtime Currency Exchange Rate', {})
            if not rate:
                return {'success': False, 'error': 'No data found', 'provider': 'alphavantage'}

            return {
                'success': True,
                'data': {
                    'from_currency': rate.get('1. From_Currency Code'),
                    'to_currency': rate.get('2. To_Currency Code'),
                    'rate': float(rate.get('3. Exchange Rate', 0)),
                    'bid': float(rate.get('8. Bid Price', 0)),
                    'ask': float(rate.get('9. Ask Price', 0)),
                },
                'provider': 'alphavantage'
            }

        except Exception as e:
            logger.error(f"Alpha Vantage forex error: {e}")
            return {'success': False, 'error': str(e), 'provider': 'alphavantage'}

    # ============ ExchangeRate-API (FREE - No API Key) ============

    async def get_forex_rate_exchangerate(self, from_currency: str, to_currency: str) -> Dict[str, Any]:
        """
        Get forex exchange rate from ExchangeRate-API (FREE, no API key).
        Reliable fallback when Trove/Alpha Vantage are not available.
        
        Args:
            from_currency: Source currency code (e.g., "NGN")
            to_currency: Target currency code (e.g., "USD")
            
        Returns:
            Exchange rate data with bid/ask prices
        """
        try:
            # ExchangeRate-API open endpoint
            url = f"https://api.exchangerate-api.com/v4/latest/{from_currency}"
            
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url)
                response.raise_for_status()
                data = response.json()

            rates = data.get('rates', {})
            if to_currency not in rates:
                return {
                    'success': False, 
                    'error': f'Rate for {to_currency} not found', 
                    'provider': 'exchangerate'
                }

            rate = rates[to_currency]
            
            # Estimate bid/ask from rate (typical spread ~0.1%)
            bid = rate * 0.999
            ask = rate * 1.001

            return {
                'success': True,
                'data': {
                    'from_currency': from_currency,
                    'to_currency': to_currency,
                    'rate': float(rate),
                    'bid': float(bid),
                    'ask': float(ask),
                },
                'provider': 'exchangerate'
            }

        except Exception as e:
            logger.error(f"ExchangeRate-API error: {e}")
            return {'success': False, 'error': str(e), 'provider': 'exchangerate'}

    async def get_news_sentiment_alphavantage(self, symbol: str) -> Dict[str, Any]:
        """
        Get news sentiment for a stock from Alpha Vantage.
        FREE tier available.
        """
        if not self.config.get('alphavantage_key'):
            return {'success': False, 'error': 'Alpha Vantage API key not configured', 'provider': 'alphavantage'}

        try:
            url = self.ALPHA_VANTAGE_API
            params = {
                'function': 'NEWS_SENTIMENT',
                'tickers': symbol,
                'apikey': self.config['alphavantage_key'],
                'limit': 10,
                'sort': 'LATEST'
            }

            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()
                data = response.json()

            feed = data.get('feed', [])
            sentiment_data = []
            
            for article in feed[:10]:  # Top 10 articles
                ticker_sentiment = article.get('ticker_sentiment', [])
                symbol_sentiment = next((t for t in ticker_sentiment if t.get('ticker') == symbol), None)
                
                if symbol_sentiment:
                    sentiment_data.append({
                        'title': article.get('title'),
                        'url': article.get('url'),
                        'time_published': article.get('time_published'),
                        'summary': article.get('summary'),
                        'sentiment_score': float(symbol_sentiment.get('relevance_score', 0)),
                        'sentiment_label': symbol_sentiment.get('ticker_sentiment_label'),
                    })

            # Calculate overall sentiment
            if sentiment_data:
                avg_score = sum(s['sentiment_score'] for s in sentiment_data) / len(sentiment_data)
            else:
                avg_score = 0

            return {
                'success': True,
                'data': {
                    'symbol': symbol,
                    'articles': sentiment_data,
                    'overall_sentiment': avg_score,
                    'sentiment_label': 'Bullish' if avg_score > 0.15 else 'Bearish' if avg_score < -0.15 else 'Neutral',
                },
                'provider': 'alphavantage'
            }

        except Exception as e:
            logger.error(f"Alpha Vantage sentiment error: {e}")
            return {'success': False, 'error': str(e), 'provider': 'alphavantage'}

    # ============ Finnhub (FREE tier) ============

    async def get_stock_price_finnhub(self, symbol: str) -> Dict[str, Any]:
        """
        Get real-time stock quote from Finnhub.
        FREE tier: 60 calls/min
        """
        if not self.config.get('finnhub_key'):
            return {'success': False, 'error': 'Finnhub API key not configured', 'provider': 'finnhub'}

        try:
            url = f"{self.FINNHUB_API}/quote"
            params = {'symbol': symbol, 'token': self.config['finnhub_key']}

            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()
                data = response.json()

            if not data or 'c' not in data:  # 'c' = current price
                return {'success': False, 'error': 'No data found', 'provider': 'finnhub'}

            return {
                'success': True,
                'data': {
                    'symbol': symbol,
                    'price': data.get('c'),  # Current price
                    'change': data.get('d'),  # Change
                    'change_percent': data.get('dp'),  # Change %
                    'high': data.get('h'),  # High
                    'low': data.get('l'),  # Low
                    'open': data.get('o'),  # Open
                    'previous_close': data.get('pc'),  # Previous close
                    'timestamp': datetime.fromtimestamp(data.get('t', 0)),
                },
                'provider': 'finnhub'
            }

        except Exception as e:
            logger.error(f"Finnhub error: {e}")
            return {'success': False, 'error': str(e), 'provider': 'finnhub'}

    async def get_company_news_finnhub(self, symbol: str, from_date: str, to_date: str) -> Dict[str, Any]:
        """Get company news from Finnhub."""
        if not self.config.get('finnhub_key'):
            return {'success': False, 'error': 'Finnhub API key not configured', 'provider': 'finnhub'}

        try:
            url = f"{self.FINNHUB_API}/company-news"
            params = {
                'symbol': symbol,
                'from': from_date,
                'to': to_date,
                'token': self.config['finnhub_key']
            }

            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()
                data = response.json()

            news = []
            for item in data[:10]:  # Top 10 articles
                news.append({
                    'title': item.get('headline'),
                    'summary': item.get('summary'),
                    'url': item.get('url'),
                    'source': item.get('source'),
                    'datetime': datetime.fromtimestamp(item.get('datetime', 0)),
                })

            return {
                'success': True,
                'data': {'symbol': symbol, 'news': news},
                'provider': 'finnhub'
            }

        except Exception as e:
            logger.error(f"Finnhub news error: {e}")
            return {'success': False, 'error': str(e), 'provider': 'finnhub'}

    # ============ Smart Router ============

    async def get_price(self, symbol: str, asset_class: str = 'stock') -> Dict[str, Any]:
        """
        Smart price router - tries free providers first.
        
        Args:
            symbol: Trading symbol
            asset_class: 'stock', 'crypto', 'forex'
        
        Returns:
            Price data from best available provider
        """
        if asset_class == 'crypto':
            # CoinGecko is FREE and always available
            result = await self.get_crypto_prices_coingecko([symbol.lower()])
            if result.get('success') and result.get('data'):
                return result
            
            # No other free crypto providers
            return {'success': False, 'error': 'No crypto providers configured'}

        elif asset_class == 'stock':
            # Try Finnhub first (real-time, free tier)
            if self.config.get('finnhub_key'):
                result = await self.get_stock_price_finnhub(symbol)
                if result.get('success'):
                    return result

            # Fall back to Alpha Vantage
            if self.config.get('alphavantage_key'):
                result = await self.get_stock_price_alphavantage(symbol)
                if result.get('success'):
                    return result

            return {'success': False, 'error': 'No stock data providers configured'}

        elif asset_class == 'forex':
            # Alpha Vantage for forex
            if self.config.get('alphavantage_key'):
                # Convert forex pair (e.g., EURUSD -> EUR, USD)
                from_currency = symbol[:3]
                to_currency = symbol[3:]
                return await self.get_forex_rate_alphavantage(from_currency, to_currency)

            return {'success': False, 'error': 'No forex providers configured'}

        return {'success': False, 'error': f'Unknown asset class: {asset_class}'}

    async def get_currency_conversion(
        self,
        amount: float,
        from_currency: str,
        to_currency: str,
        use_trove: bool = False,
        trove_api_key: Optional[str] = None,
        trove_base_url: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Convert amount between currencies using Trove API or Alpha Vantage fallback.

        Args:
            amount: Amount to convert
            from_currency: Source currency (e.g., "NGN")
            to_currency: Target currency (e.g., "USD")
            use_trove: Whether to try Trove API first
            trove_api_key: Trove API key (if provided)
            trove_base_url: Trove base URL (if provided)

        Returns:
            Conversion result with original amount, converted amount, and exchange rate
        """
        # Handle same currency conversion
        if from_currency == to_currency:
            return {
                'success': True,
                'data': {
                    'amount': amount,
                    'from_currency': from_currency,
                    'to_currency': to_currency,
                    'converted_amount': amount,
                    'exchange_rate': 1.0,
                },
                'provider': 'identity',
            }

        # Try Trove API first if configured
        if use_trove and trove_api_key and trove_base_url:
            try:
                result = await self._get_forex_rate_trove(
                    from_currency, 
                    to_currency,
                    trove_api_key,
                    trove_base_url
                )
                if result.get('success'):
                    rate = result['data']['rate']
                    return {
                        'success': True,
                        'data': {
                            'amount': amount,
                            'from_currency': from_currency,
                            'to_currency': to_currency,
                            'converted_amount': amount * rate,
                            'exchange_rate': rate,
                            'bid': result['data'].get('bid'),
                            'ask': result['data'].get('ask'),
                        },
                        'provider': 'trove',
                    }
            except Exception as e:
                logger.warning(f"Trove forex conversion failed, falling back to Alpha Vantage: {e}")

        # Fallback to Alpha Vantage if configured
        if from_currency and to_currency:
            if self.config.get('alphavantage_key'):
                result = await self.get_forex_rate_alphavantage(from_currency, to_currency)
                if result.get('success'):
                    rate = result['data']['rate']
                    return {
                        'success': True,
                        'data': {
                            'amount': amount,
                            'from_currency': from_currency,
                            'to_currency': to_currency,
                            'converted_amount': amount * rate,
                            'exchange_rate': rate,
                            'bid': result['data'].get('bid'),
                            'ask': result['data'].get('ask'),
                        },
                        'provider': 'alphavantage',
                    }

            # Ultimate fallback: ExchangeRate-API (FREE, no key required)
            result = await self.get_forex_rate_exchangerate(from_currency, to_currency)
            if result.get('success'):
                rate = result['data']['rate']
                return {
                    'success': True,
                    'data': {
                        'amount': amount,
                        'from_currency': from_currency,
                        'to_currency': to_currency,
                        'converted_amount': amount * rate,
                        'exchange_rate': rate,
                        'bid': result['data'].get('bid'),
                        'ask': result['data'].get('ask'),
                    },
                    'provider': 'exchangerate',
                }

        return {
            'success': False,
            'error': 'No currency conversion providers configured',
        }

    async def _get_forex_rate_trove(
        self,
        from_currency: str,
        to_currency: str,
        api_key: str,
        base_url: str,
    ) -> Dict[str, Any]:
        """
        Get forex exchange rate from Trove API.

        Args:
            from_currency: Source currency
            to_currency: Target currency
            api_key: Trove API key
            base_url: Trove API base URL

        Returns:
            Exchange rate data
        """
        try:
            url = f"{base_url}/forex/rate"
            params = {'from': from_currency, 'to': to_currency}
            headers = {'Authorization': f'Bearer {api_key}'}

            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url, params=params, headers=headers)
                response.raise_for_status()
                data = response.json()

            if not data:
                return {'success': False, 'error': 'No data from Trove', 'provider': 'trove'}

            return {
                'success': True,
                'data': {
                    'from_currency': from_currency,
                    'to_currency': to_currency,
                    'rate': float(data.get('rate', 0)),
                    'bid': float(data.get('bid', 0)),
                    'ask': float(data.get('ask', 0)),
                    'timestamp': data.get('timestamp', datetime.utcnow().isoformat()),
                },
                'provider': 'trove',
            }

        except Exception as e:
            logger.error(f"Trove forex error: {e}")
            return {'success': False, 'error': str(e), 'provider': 'trove'}

    def get_available_providers(self) -> Dict[str, bool]:
        """Get list of configured providers."""
        from app.services.coinmarketcap_service import get_coinmarketcap_service

        return {
            'coingecko': True,  # Always available (free, no key)
            'alphavantage': bool(self.config.get('alphavantage_key')),
            'finnhub': bool(self.config.get('finnhub_key')),
            'twelvedata': bool(self.config.get('twelvedata_key')),
            'polygon': bool(self.config.get('polygon_key')),
            'coinmarketcap': get_coinmarketcap_service().configured,
        }


# Singleton instance
_market_data_service: Optional[MarketDataService] = None


def get_market_data_service() -> MarketDataService:
    """Get market data service singleton."""
    global _market_data_service
    if _market_data_service is None:
        _market_data_service = MarketDataService()
    return _market_data_service