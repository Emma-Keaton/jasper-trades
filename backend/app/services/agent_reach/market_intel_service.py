"""
Market Intelligence Service — Agent Reach Integration

Provides real-time news aggregation and sentiment analysis from:
- Twitter/X, Reddit, Xueqiu, V2EX, RSS feeds

Usage:
    from app.services.agent_reach.market_intel_service import MarketIntelService
    service = MarketIntelService()
    news = await service.get_news(ticker="AAPL", limit=20)
"""

import asyncio
import time
import os
import urllib.request
import urllib.error
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from loguru import logger
from app.config import settings
from app.services.agent_reach.channels.twitter_channel import get_twitter_channel
import xml.etree.ElementTree as ET


class MarketIntelService:
    """Market intelligence service with sentiment analysis."""

    def __init__(self):
        self.enabled = getattr(settings, 'AGENT_REACH_ENABLED', False)
        self.channels = self._parse_channels()
        self.poll_interval = getattr(settings, 'NEWS_POLL_INTERVAL', 15)
        self.cache = {}
        self.cache_ttl = getattr(settings, 'SENTIMENT_CACHE_TTL', 60)
        self.last_update = None
        self.sentiment_enabled = getattr(settings, 'SENTIMENT_ANALYSIS_ENABLED', True)

        # Configure Agent Reach config path
        self.config_path = getattr(settings, 'AGENT_REACH_CONFIG_PATH', None)
        if self.config_path:
            # Resolve relative paths to backend directory
            if not os.path.isabs(self.config_path):
                backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
                self.config_path = os.path.join(backend_dir, self.config_path)
            # Set environment variable for agent-reach library
            os.environ['AGENT_REACH_CONFIG_PATH'] = self.config_path
            logger.info(f"Agent Reach config path set to: {self.config_path}")

        # Lazy-load sentiment service
        self._sentiment_service = None
        if self.sentiment_enabled:
            try:
                from app.services.agent_reach.sentiment_analysis import get_sentiment_service
                self._sentiment_service = get_sentiment_service()
            except Exception as e:
                logger.warning(f"Sentiment service unavailable: {e}")

        if self.enabled:
            logger.info(f"Market Intelligence enabled: {self.channels}, poll_interval={self.poll_interval}s")
            asyncio.create_task(self._polling_loop())
        else:
            logger.info("Market Intelligence disabled")
    
    @property
    def sentiment_service(self):
        if self._sentiment_service is None and self.sentiment_enabled:
            try:
                from app.services.agent_reach.sentiment_analysis import get_sentiment_service
                self._sentiment_service = get_sentiment_service()
            except:
                pass
        return self._sentiment_service
    
    def _parse_channels(self) -> List[str]:
        channels_str = getattr(settings, 'AGENT_REACH_CHANNELS', 'v2ex')
        return [c.strip().lower() for c in channels_str.split(',') if c.strip()]
    
    async def _polling_loop(self):
        while True:
            try:
                await self._fetch_all_news()
                await asyncio.sleep(self.poll_interval)
            except Exception as e:
                logger.error(f"Polling error: {e}")
                await asyncio.sleep(60)
    
    async def _fetch_all_news(self):
        if not self.enabled:
            return
        
        start_time = time.time()
        all_news = []
        
        for channel in self.channels:
            try:
                channel_news = await self._fetch_from_channel(channel)
                all_news.extend(channel_news)
            except Exception as e:
                logger.error(f"Error from {channel}: {e}")
        
        if all_news:
            # Analyze sentiment if enabled
            if self.sentiment_service:
                try:
                    all_news = await self.sentiment_service.analyze_news_batch(all_news)
                except Exception as e:
                    logger.warning(f"Sentiment analysis failed: {e}")
            
            self.cache['news'] = all_news
            self.last_update = datetime.utcnow()
            logger.info(f"Fetched {len(all_news)} news in {time.time()-start_time:.2f}s")
    
    async def _fetch_from_channel(self, channel: str) -> List[Dict[str, Any]]:
        if channel == 'v2ex':
            return await self._fetch_v2ex_news()
        elif channel == 'twitter':
            return await self._fetch_twitter_news()
        elif channel == 'reddit':
            return await self._fetch_reddit_news()
        elif channel == 'rss':
            return await self._fetch_rss_news()
        else:
            return []

    async def _fetch_rss_news(self) -> List[Dict[str, Any]]:
        """Fetch news from RSS feeds configured in RSS_FEED_URLS."""
        try:
            # Get RSS URLs from settings (comma-separated)
            rss_urls_str = getattr(settings, 'RSS_FEED_URLS', '')
            if not rss_urls_str:
                logger.warning("No RSS feed URLs configured in RSS_FEED_URLS")
                return []

            rss_urls = [url.strip() for url in rss_urls_str.split(',') if url.strip()]
            if not rss_urls:
                return []

            all_items = []
            max_per_feed = 15
            max_total = 100

            for url in rss_urls:
                try:
                    logger.info(f"Fetching RSS feed: {url}")
                    req = urllib.request.Request(
                        url,
                        headers={"User-Agent": "JasperTrades/1.0 (RSS Feed Reader)"}
                    )

                    with urllib.request.urlopen(req, timeout=15) as resp:
                        xml_data = resp.read()

                    # Parse XML
                    root = ET.fromstring(xml_data)

                    # Find feed items (handle different RSS/Atom formats)
                    items = []

                    # RSS 2.0 format
                    channel = root.find('channel')
                    if channel is not None:
                        items = channel.findall('item')

                    # Atom format
                    if not items:
                        ns = {'atom': 'http://www.w3.org/2005/Atom'}
                        items = root.findall('atom:entry', ns)
                        if not items:
                            # Try without namespace
                            items = root.findall('{http://www.w3.org/2005/Atom}entry')

                    feed_items = []
                    for item in items[:max_per_feed]:
                        title = self._get_xml_text(item, ['title', '{http://www.w3.org/2005/Atom}title'])
                        link = self._get_xml_text(item, ['link', 'guid', '{http://www.w3.org/2005/Atom}link'])

                        # Handle Atom link with href attribute
                        if not link:
                            link_elem = item.find('link')
                            if link_elem is not None and link_elem.get('href'):
                                link = link_elem.get('href')
                            else:
                                link_elem = item.find('{http://www.w3.org/2005/Atom}link')
                                if link_elem is not None and link_elem.get('href'):
                                    link = link_elem.get('href')

                        description = self._get_xml_text(item, [
                            'description',
                            'content',
                            'summary',
                            '{http://www.w3.org/2005/Atom}content',
                            '{http://www.w3.org/2005/Atom}summary'
                        ])

                        pub_date_str = self._get_xml_text(item, [
                            'pubDate',
                            'pubdate',
                            'date',
                            'published',
                            '{http://www.w3.org/2005/Atom}published',
                            '{http://www.w3.org/2005/Atom}updated'
                        ])

                        author = self._get_xml_text(item, [
                            'author',
                            'dc:creator',
                            'creator',
                            '{http://www.w3.org/2005/Atom}author'
                        ])

                        # Parse date
                        timestamp = self._parse_rss_date(pub_date_str)

                        # Generate unique ID
                        item_id = f"rss_{hash(link or title) % 100000000}"

                        feed_items.append({
                            'id': item_id,
                            'source': 'rss',
                            'title': title or '',
                            'content': (description or '')[:500],
                            'url': link or '',
                            'author': author or '',
                            'timestamp': timestamp or datetime.utcnow(),
                            'tickers_mentioned': [],
                            'sentiment_score': 50,
                            'impact_score': 0
                        })

                    all_items.extend(feed_items)
                    logger.info(f"Fetched {len(feed_items)} items from {url}")

                except urllib.error.URLError as e:
                    logger.warning(f"Failed to fetch RSS feed {url}: {e}")
                    continue
                except ET.ParseError as e:
                    logger.warning(f"Failed to parse RSS XML from {url}: {e}")
                    continue
                except Exception as e:
                    logger.warning(f"Error processing RSS feed {url}: {e}")
                    continue

                # Limit total items
                if len(all_items) >= max_total:
                    break

            logger.info(f"Total RSS news collected: {len(all_items)}")
            return all_items[:max_total]

        except Exception as e:
            logger.error(f"RSS fetch error: {e}")
            return []

    def _get_xml_text(self, element: ET.Element, tag_names: List[str]) -> Optional[str]:
        """Extract text from XML element with fallback to multiple tag names."""
        for tag_name in tag_names:
            child = element.find(tag_name)
            if child is not None and child.text:
                return child.text.strip()
        return None

    def _parse_rss_date(self, date_str: Optional[str]) -> Optional[datetime]:
        """Parse RFC 822 or ISO 8601 date formats."""
        if not date_str:
            return None

        try:
            # RFC 822 format: "Wed, 02 Oct 2024 14:30:00 GMT"
            from email.utils import parsedate_to_datetime
            dt = parsedate_to_datetime(date_str)
            return dt.replace(tzinfo=None)
        except (ValueError, TypeError):
            pass

        try:
            # ISO 8601 format: "2024-10-02T14:30:00Z" or "2024-10-02T14:30:00+00:00"
            if date_str.endswith('Z'):
                date_str = date_str[:-1] + '+00:00'
            from datetime import timezone
            dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
            return dt.replace(tzinfo=None)
        except (ValueError, TypeError):
            pass

        try:
            # Simple format: "2024-10-02 14:30:00"
            return datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S')
        except (ValueError, TypeError):
            pass

        logger.warning(f"Failed to parse date: {date_str}")
        return None
    
    async def _fetch_v2ex_news(self) -> List[Dict[str, Any]]:
        try:
            import urllib.request
            import json
            
            url = "https://www.v2ex.com/api/topics/hot.json"
            req = urllib.request.Request(url, headers={"User-Agent": "JasperTrades/1.0"})
            
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode('utf-8'))
            
            return [{
                'id': f"v2ex_{t.get('id', '')}",
                'source': 'v2ex',
                'title': t.get('title', ''),
                'content': t.get('content', '')[:500],
                'url': t.get('url', ''),
                'author': t.get('member', {}).get('username', ''),
                'timestamp': datetime.utcfromtimestamp(t.get('created', 0)),
                'tickers_mentioned': [],
                'sentiment_score': 50,
                'impact_score': 0
            } for t in data[:10]]
        except Exception as e:
            logger.error(f"V2EX error: {e}")
            return []
    
    async def _fetch_twitter_news(self) -> List[Dict[str, Any]]:
        if 'twitter' not in self.channels:
            return []
        try:
            channel = get_twitter_channel()
            if not channel.enabled:
                return []
            return await channel.fetch_financial_news(limit=30)
        except Exception as e:
            logger.error(f"Twitter error: {e}")
            return []
    
    async def _fetch_reddit_news(self) -> List[Dict[str, Any]]:
        if 'reddit' not in self.channels:
            return []
        try:
            from app.services.agent_reach.channels.reddit_channel import get_reddit_channel
            channel = get_reddit_channel()
            if not channel.enabled:
                return []
            
            # Trading-relevant subreddits for execution signals
            subreddits = [
                'wallstreetbets',      # High-signal YOLO trades, sentiment
                'stocks',               # Fundamental discussions
                'investing',            # Broader market analysis
                'securityanalysis',     # Deep value investing
                'investor',             # Long-term positions
                'Daytrading',           # Short-term signals
                'CryptoCurrency',       # Crypto sentiment
                'CryptoMarkets',        # Crypto trading signals
                'wallstreetbets质的',    # WSB discussion mirror
                'superstonk',           # Meme stock sentiment
                'stocks',               # General stock talk
                'BeenWhy',              # Options flow (if available)
            ]
            
            posts = []
            for sub in subreddits[:8]:  # Limit to 8 subs to avoid rate limits
                try:
                    sub_posts = await channel.fetch_subreddit_posts(subreddit=sub, limit=10)
                    posts.extend(sub_posts)
                    logger.info(f"Fetched {len(sub_posts)} posts from r/{sub}")
                except Exception as sub_error:
                    logger.warning(f"Failed to fetch r/{sub}: {sub_error}")
                    continue
            
            # Deduplicate by post ID
            seen_ids = set()
            unique_posts = []
            for post in posts:
                if post.get('id') not in seen_ids:
                    seen_ids.add(post.get('id'))
                    unique_posts.append(post)
            
            logger.info(f"Reddit: {len(unique_posts)} unique posts from {len(subreddits)} subreddits")
            return unique_posts[:50]  # Return top 50 posts
        except Exception as e:
            logger.error(f"Reddit error: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    async def get_news(self, ticker: Optional[str] = None, limit: int = 20,
                      sources: Optional[List[str]] = None,
                      since: Optional[datetime] = None) -> List[Dict[str, Any]]:
        """Get news with optional filtering."""
        news = list(self.cache.get('news', []))
        
        # Filter
        if ticker:
            news = [n for n in news if ticker.upper() in n.get('tickers_mentioned', [])]
        if sources:
            news = [n for n in news if n.get('source') in sources]
        if since:
            news = [n for n in news if n.get('timestamp') and n['timestamp'] > since]
        
        # Sort and limit
        news.sort(key=lambda x: x.get('timestamp') or datetime.min, reverse=True)
        return news[:limit]
    
    async def get_sentiment(self, ticker: str) -> Dict[str, Any]:
        """Get sentiment for a ticker."""
        news = await self.get_news(ticker=ticker, limit=50)
        
        if not news:
            return {
                'symbol': ticker,
                'overall_score': 50,
                'source_scores': {},
                'recent_articles': 0,
                'last_updated': datetime.utcnow()
            }
        
        # Calculate by source
        source_scores = {}
        for source in self.channels:
            src_news = [n for n in news if n.get('source') == source]
            if src_news:
                avg = sum(n.get('sentiment_score', 50) for n in src_news) / len(src_news)
                source_scores[source] = round(avg, 1)
        
        overall = sum(n.get('sentiment_score', 50) for n in news) / len(news)
        
        return {
            'symbol': ticker,
            'overall_score': round(overall, 1),
            'source_scores': source_scores,
            'recent_articles': len(news),
            'last_updated': datetime.utcnow()
        }
    
    async def get_trending_stocks(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get trending stocks by mention count."""
        news = await self.get_news(limit=200)
        
        ticker_counts = {}
        for article in news:
            for ticker in article.get('tickers_mentioned', []):
                ticker_counts[ticker] = ticker_counts.get(ticker, 0) + 1
        
        trending = [
            {'symbol': t, 'mention_count': c, 'sentiment': 'unknown'}
            for t, c in sorted(ticker_counts.items(), key=lambda x: x[1], reverse=True)
        ]
        return trending[:limit]
    
    async def search_news(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Search news by keywords."""
        news = await self.get_news(limit=500)
        query_lower = query.lower()
        matches = [n for n in news if query_lower in n.get('title', '').lower() or 
                  query_lower in n.get('content', '').lower()]
        return matches[:limit]
    
    async def health_check(self) -> Dict[str, Any]:
        """Check service health."""
        return {
            'enabled': self.enabled,
            'channels': {c: {'enabled': c in self.channels, 'status': 'ok' if c in self.channels else 'off'} 
                        for c in ['twitter', 'reddit', 'xueqiu', 'v2ex', 'rss']},
            'last_update': self.last_update,
            'cached_news_count': len(self.cache.get('news', [])),
            'sentiment_enabled': self.sentiment_enabled and self._sentiment_service is not None
        }


# Singleton
_market_intel_service = None

def get_market_intel_service() -> MarketIntelService:
    global _market_intel_service
    if _market_intel_service is None:
        _market_intel_service = MarketIntelService()
    return _market_intel_service