"""
Polymarket Integration Service
Prediction market data and simulated trading using official polymarket-client SDK
Inspired by AI-Trader Polymarket skill
"""
import structlog
from typing import Optional, Dict, List, Any
from dataclasses import dataclass, asdict
from datetime import datetime

logger = structlog.get_logger(__name__)

try:
    from polymarket import AsyncPublicClient
    from polymarket.models.gamma.search import SearchResults
    SDK_AVAILABLE = True
except ImportError:
    SDK_AVAILABLE = False
    AsyncPublicClient = None
    SearchResults = None


@dataclass
class PolymarketMarket:
    """Polymarket market data"""
    market_id: str
    question: str
    slug: str
    condition_id: str
    outcomes: List[str]
    clob_token_ids: List[str]
    volume: float
    liquidity: float
    open_interest: float
    closing_date: Optional[str]
    status: str  # open, closed, resolved
    resolved_prices: Optional[Dict[str, float]]


@dataclass
class PolymarketOrderbook:
    """Orderbook for a specific outcome token"""
    token_id: str
    bids: List[Dict[str, float]]  # [{price, size}]
    asks: List[Dict[str, float]]
    best_bid: float
    best_ask: float
    mid_price: float
    spread: float
    last_update: str


class PolymarketService:
    """
    Polymarket prediction market integration using official SDK.
    
    Reads market metadata and orderbook prices directly from Polymarket public APIs.
    No API key required for public data access.
    
    Features:
    - Market discovery and search
    - Outcome token resolution
    - Real-time orderbook pricing
    - Simulated trading (paper)
    - Price history tracking
    - Arbitrage detection
    """

    def __init__(self):
        self.enabled = SDK_AVAILABLE
        self.cache: Dict[str, PolymarketMarket] = {}
        self.orderbook_cache: Dict[str, PolymarketOrderbook] = {}
        self.cache_ttl_seconds = 300  # 5 minutes
        self._client: Optional[AsyncPublicClient] = None
        
        if not SDK_AVAILABLE:
            logger.warning("Polymarket SDK not available - install with: pip install polymarket-client")
        else:
            logger.info("Polymarket Service initialized (using official SDK)")

    async def _get_client(self) -> Optional[AsyncPublicClient]:
        """Get or create async client"""
        if not SDK_AVAILABLE:
            return None
        
        if self._client is None:
            self._client = AsyncPublicClient()
        
        return self._client

    async def search_markets(self, query: str, limit: int = 20) -> List[PolymarketMarket]:
        """
        Search for Polymarket markets by keyword.
        
        Args:
            query: Search query (e.g., "BTC", "election", "Fed")
            limit: Maximum results to return
            
        Returns:
            List of matching markets
        """
        if not self.enabled:
            return []

        try:
            client = await self._get_client()
            if not client:
                return []

            # First try direct list_markets approach for active markets
            # Search works best for finding events, but we want actual markets
            markets = []
            
            # Try to find markets by querying different endpoints
            # Approach 1: List markets ordered by volume (trending)
            if query.lower() in ['btc', 'bitcoin', 'crypto', 'eth', 'ethereum']:
                # For crypto queries, get trending crypto markets
                markets_response = client.list_markets(
                    page_size=limit,
                    closed=False,
                    order="-volume"
                )
                
                markets_data = await markets_response.first_page()
                
                for m in markets_data.items:
                    market = self._parse_market_from_sdk(m)
                    if market and query.lower() in market.question.lower():
                        markets.append(market)
                        self.cache[market.market_id] = market
                        if len(markets) >= limit:
                            break
                
                if markets:
                    logger.info(f"Found {len(markets)} Polymarket markets for '{query}'")
                    return markets
            
            # Approach 2: Use search for generic queries
            search_results = client.search(
                q=query,
                page_size=min(limit * 2, 100)  # Get more results since many may be closed
            )
            
            search_data = await search_results.first_page()
            
            market_ids_seen = set()
            
            for item in search_data.items:
                # SearchResults contain events
                if hasattr(item, 'events'):
                    for event in item.events:
                        # Try to get market details using condition ID if available
                        if hasattr(event, 'id') and event.id:
                            try:
                                market_data = await client.get_market(event.id)
                                if market_data:
                                    market = self._parse_market_from_sdk(market_data)
                                    if market and market.market_id not in market_ids_seen:
                                        markets.append(market)
                                        market_ids_seen.add(market.market_id)
                                        self.cache[market.market_id] = market
                                        if len(markets) >= limit:
                                            return markets
                            except Exception:
                                # Market may not exist or be inaccessible
                                continue

            logger.info(f"Found {len(markets)} Polymarket markets for '{query}'")
            return markets

        except Exception as e:
            logger.error(f"Polymarket search error: {e}")
            return []

    async def get_market_by_slug(self, slug: str) -> Optional[PolymarketMarket]:
        """
        Get market metadata by slug.
        
        Args:
            slug: Market slug (e.g., "will-btc-be-above-120k-on-june-30")
            
        Returns:
            Market data or None if not found
        """
        # Check cache first
        cached = self.cache.get(slug)
        if cached:
            logger.debug(f"Cache hit for market {slug}")
            return cached

        try:
            client = await self._get_client()
            if not client:
                return None

            # Search for the market using slug in list_markets
            markets_response = client.list_markets(
                slug=slug,
                page_size=1
            )
            
            markets_data = await markets_response.first_page()
            
            if not markets_data.items:
                logger.warning(f"Market not found: {slug}")
                return None

            market = self._parse_market_from_sdk(markets_data.items[0])
            if market:
                self.cache[market.market_id] = market
                logger.info(f"Resolved market: {slug}")

            return market

        except Exception as e:
            logger.error(f"Failed to fetch market {slug}: {e}")
            return None

    async def get_market_by_condition_id(self, condition_id: str) -> Optional[PolymarketMarket]:
        """
        Get market by condition ID (on-chain identifier).
        
        Args:
            condition_id: Ethereum condition ID (hex string)
            
        Returns:
            Market data or None if not found
        """
        try:
            client = await self._get_client()
            if not client:
                return None

            # Use SDK's get_market method
            market_data = await client.get_market(condition_id)
            
            return self._parse_market_from_sdk(market_data)

        except Exception as e:
            logger.error(f"Failed to fetch market by condition ID {condition_id}: {e}")
            return None

    async def get_orderbook(self, token_id: str) -> Optional[PolymarketOrderbook]:
        """
        Get orderbook for a specific outcome token.
        
        Args:
            token_id: CLOB token ID
            
        Returns:
            Orderbook data or None if not found
        """
        try:
            client = await self._get_client()
            if not client:
                return None

            # Use SDK's get_order_book method
            orderbook_data = await client.get_order_book(token_id)
            
            # Parse orderbook
            bids = [
                {"price": float(b["price"]), "size": float(b["size"])}
                for b in getattr(orderbook_data, 'bids', [])[:10]
            ]
            asks = [
                {"price": float(a["price"]), "size": float(a["size"])}
                for a in getattr(orderbook_data, 'asks', [])[:10]
            ]

            best_bid = max(b["price"] for b in bids) if bids else 0.0
            best_ask = min(a["price"] for a in asks) if asks else 0.0
            mid_price = (best_bid + best_ask) / 2 if best_bid and best_ask else 0.0
            spread = best_ask - best_bid if best_bid and best_ask else 0.0

            orderbook = PolymarketOrderbook(
                token_id=token_id,
                bids=bids,
                asks=asks,
                best_bid=best_bid,
                best_ask=best_ask,
                mid_price=mid_price,
                spread=spread,
                last_update=datetime.utcnow().isoformat() + "Z"
            )

            self.orderbook_cache[token_id] = orderbook
            logger.debug(f"Orderbook fetched for token {token_id}: mid={mid_price:.4f}")
            return orderbook

        except Exception as e:
            logger.error(f"Failed to fetch orderbook for token {token_id}: {e}")
            return None

    async def get_outcome_price(self, token_id: str) -> Optional[float]:
        """
        Get current mid price for an outcome token.
        
        Args:
            token_id: CLOB token ID
            
        Returns:
            Mid price (0.0-1.0) or None if unavailable
        """
        orderbook = await self.get_orderbook(token_id)
        if orderbook:
            return orderbook.mid_price
        return None

    async def analyze_market(self, slug: str) -> Optional[Dict[str, Any]]:
        """
        Analyze a Polymarket for trading opportunity.
        
        Args:
            slug: Market slug
            
        Returns:
            Analysis with recommendation
        """
        market = await self.get_market_by_slug(slug)
        if not market:
            return None

        # Fetch prices for all outcomes
        prices = {}
        for token_id in market.clob_token_ids:
            price = await self.get_outcome_price(token_id)
            if price:
                prices[token_id] = price

        # Find value opportunities
        # Implied probability should sum to ~1.0 across all outcomes
        total_implied = sum(prices.values())
        
        analysis = {
            "market_id": market.market_id,
            "question": market.question,
            "outcomes": market.outcomes,
            "prices": prices,
            "total_implied_probability": total_implied,
            "arbitrage_detected": abs(total_implied - 1.0) > 0.05,
            "recommendation": None,
            "confidence": 0.0
        }

        # Simple arbitrage detection
        if total_implied < 0.90:
            # All outcomes underpriced - potential arbitrage
            analysis["recommendation"] = "Consider buying all outcomes (arbitrage opportunity)"
            analysis["confidence"] = min(1.0 - total_implied, 0.5)
        elif total_implied > 1.10:
            # All outcomes overpriced - market inefficiency
            analysis["recommendation"] = "Market overpriced - wait for correction"
            analysis["confidence"] = min(total_implied - 1.0, 0.5)
        else:
            # Normal market - find best value
            if prices:
                best_outcome_idx = min(range(len(prices)), key=lambda i: list(prices.values())[i])
                analysis["recommendation"] = f"Best value: {market.outcomes[best_outcome_idx]} @ {list(prices.values())[best_outcome_idx]:.2%}"
                analysis["confidence"] = 0.3  # Base confidence

        logger.info(f"Analyzed Polymarket {slug}: {analysis['recommendation']}")
        return analysis

    def _parse_market_from_sdk(self, market_data: Any) -> Optional[PolymarketMarket]:
        """Parse market data from SDK response"""
        try:
            return PolymarketMarket(
                market_id=getattr(market_data, 'id', '') or getattr(market_data, 'market_id', ''),
                question=getattr(market_data, 'title', '') or getattr(market_data, 'question', ''),
                slug=getattr(market_data, 'slug', ''),
                condition_id=getattr(market_data, 'conditionId', '') or getattr(market_data, 'condition_id', ''),
                outcomes=getattr(market_data, 'outcomes', []) or [],
                clob_token_ids=getattr(market_data, 'clobTokenIds', []) or getattr(market_data, 'clob_token_ids', []) or [],
                volume=float(getattr(market_data, 'volume', 0) or 0),
                liquidity=float(getattr(market_data, 'liquidity', 0) or 0),
                open_interest=float(getattr(market_data, 'openInterest', 0) or 0),
                closing_date=getattr(market_data, 'closingDate', None) or getattr(market_data, 'closing_date', None),
                status=getattr(market_data, 'status', 'open'),
                resolved_prices=getattr(market_data, 'resolvedPrices', None) or getattr(market_data, 'resolved_prices', None)
            )
        except Exception as e:
            logger.error(f"Failed to parse market data: {e}")
            return None

    async def get_trending_markets(self, limit: int = 10) -> List[PolymarketMarket]:
        """
        Get trending/volatile markets.
        
        Args:
            limit: Number of markets to return
            
        Returns:
            List of trending markets
        """
        try:
            client = await self._get_client()
            if not client:
                return []

            # Get recent active markets (ordered by volume)
            markets_response = client.list_markets(
                page_size=limit,
                closed=False,
                order="-volume"  # Order by volume descending
            )
            
            markets_data = await markets_response.first_page()
            
            markets = []
            for m in markets_data.items:
                market = self._parse_market_from_sdk(m)
                if market:
                    markets.append(market)
                    self.cache[market.market_id] = market

            logger.info(f"Fetched {len(markets)} trending markets")
            return markets

        except Exception as e:
            logger.error(f"Failed to fetch trending markets: {e}")
            return []

    async def get_markets_by_category(self, category: str, limit: int = 20) -> List[PolymarketMarket]:
        """
        Get markets by category (tag).
        
        Args:
            category: Category name (crypto, politics, sports, economics, etc.)
            limit: Maximum results
            
        Returns:
            List of markets in category
        """
        try:
            client = await self._get_client()
            if not client:
                return []

            # First, find the tag ID for this category
            tags_response = client.list_tags(q=category, page_size=1)
            tags_data = await tags_response.first_page()
            
            if not tags_data.items:
                logger.warning(f"No tag found for category: {category}")
                return []
            
            tag_id = tags_data.items[0].id
            
            # Now get markets with this tag
            markets_response = client.list_markets(
                tag_id=tag_id,
                page_size=min(limit, 100)
            )
            
            markets_data = await markets_response.first_page()
            
            markets = []
            for m in markets_data.items:
                market = self._parse_market_from_sdk(m)
                if market:
                    markets.append(market)
                    self.cache[market.market_id] = market

            logger.info(f"Fetched {len(markets)} {category} markets")
            return markets

        except Exception as e:
            logger.error(f"Failed to fetch {category} markets: {e}")
            return []

    def get_cache_status(self) -> Dict:
        """Get cache status"""
        return {
            "cached_markets": len(self.cache),
            "cached_orderbooks": len(self.orderbook_cache),
            "cache_ttl_seconds": self.cache_ttl_seconds,
            "enabled": self.enabled,
            "sdk_available": SDK_AVAILABLE
        }

    async def refresh_cache(self):
        """Refresh cached market data"""
        logger.info(f"Refreshing {len(self.cache)} cached markets")
        for market_id in list(self.cache.keys()):
            market = self.cache[market_id]
            refreshed = await self.get_market_by_slug(market.slug)
            if refreshed:
                self.cache[market_id] = refreshed
        logger.info("Cache refresh complete")


# Singleton instance
polymarket_service = PolymarketService()