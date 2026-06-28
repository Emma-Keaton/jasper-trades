"""
Twitter Channel Integration for Market Intelligence

Uses Agent Reach's twitter-cli or OpenCLI for real-time Twitter/X data.
Requires browser authentication (Chrome with logged-in Twitter account).

Usage:
    from app.services.agent_reach.channels.twitter_channel import TwitterChannel
    
    channel = TwitterChannel()
    news = await channel.fetch_financial_news(ticker="AAPL")
"""

import asyncio
import re
from datetime import datetime
from typing import Any, Dict, List, Optional
import subprocess
import json

from loguru import logger


class TwitterChannel:
    """Twitter channel for fetching financial news and sentiment."""
    
    # Financial/tickers keywords to look for
    TICKER_PATTERN = re.compile(r'\b[A-Z]{1,5}\b')
    FINANCIAL_KEYWORDS = [
        'earnings', 'stock', 'shares', 'price', 'market', 'investment',
        'trading', 'bullish', 'bearish', 'buy', 'sell', 'hold',
        'SPY', 'QQQ', 'DIA', 'IWM'  # Major ETFs
    ]
    
    def __init__(self):
        self.enabled = False
        self.cli_available = self._check_cli_availability()
        
        if self.cli_available:
            logger.info("Twitter CLI available for market intelligence")
            self.enabled = True
        else:
            logger.info("Twitter CLI not available. Install with: pipx install twitter-cli")
    
    def _check_cli_availability(self) -> bool:
        """Check if twitter-cli or opencli is available."""
        try:
            # Check for twitter-cli
            result = subprocess.run(
                ['twitter', '--help'],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                return True
            
            # Check for opencli
            result = subprocess.run(
                ['opencli', '--help'],
                capture_output=True,
                text=True,
                timeout=5
            )
            return result.returncode == 0
            
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False
    
    async def fetch_financial_news(
        self,
        ticker: Optional[str] = None,
        keywords: Optional[List[str]] = None,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Fetch financial news/tweets for a ticker or keywords.
        
        Args:
            ticker: Stock ticker symbol (e.g., "AAPL")
            keywords: List of keywords to search for
            limit: Maximum number of tweets to fetch
            
        Returns:
            List of tweet dictionaries with sentiment context
        """
        if not self.enabled:
            logger.warning("Twitter channel not enabled")
            return []
        
        try:
            # Build search query
            query = self._build_search_query(ticker, keywords)
            
            # Execute twitter-cli search
            tweets = await self._search_twitter(query, limit)
            
            # Filter for financial content
            financial_tweets = self._filter_financial_content(tweets)
            
            # Extract tickers mentioned
            for tweet in financial_tweets:
                tweet['tickers_mentioned'] = self._extract_tickers(tweet['content'])
            
            return financial_tweets
            
        except Exception as e:
            logger.error(f"Twitter fetch error: {e}")
            return []
    
    def _build_search_query(
        self,
        ticker: Optional[str] = None,
        keywords: Optional[List[str]] = None
    ) -> str:
        """Build Twitter search query."""
        parts = []
        
        if ticker:
            parts.append(f"${ticker}")
            parts.append(ticker)
        
        if keywords:
            parts.extend(keywords)
        else:
            parts.extend(self.FINANCIAL_KEYWORDS[:5])  # Top 5 financial keywords
        
        return " OR ".join(parts)
    
    async def _search_twitter(self, query: str, limit: int) -> List[Dict[str, Any]]:
        """Search Twitter using twitter-cli."""
        try:
            # Try twitter-cli first
            result = subprocess.run(
                ['twitter', 'search', query, '--limit', str(limit)],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0:
                return self._parse_twitter_output(result.stdout)
            
            # Fallback to opencli
            result = subprocess.run(
                ['opencli', 'twitter', 'search', query, '--limit', str(limit)],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0:
                return self._parse_twitter_output(result.stdout)
            
            logger.error(f"Twitter search failed: {result.stderr}")
            return []
            
        except subprocess.TimeoutExpired:
            logger.error("Twitter search timed out")
            return []
        except Exception as e:
            logger.error(f"Twitter search error: {e}")
            return []
    
    def _parse_twitter_output(self, output: str) -> List[Dict[str, Any]]:
        """Parse twitter-cli output into structured data."""
        tweets = []
        
        try:
            # Try to parse as JSON first
            data = json.loads(output)
            if isinstance(data, list):
                for tweet in data:
                    tweets.append({
                        'id': tweet.get('id', ''),
                        'source': 'twitter',
                        'title': tweet.get('text', '')[:100],
                        'content': tweet.get('text', ''),
                        'url': tweet.get('url', ''),
                        'author': tweet.get('user', {}).get('username', ''),
                        'timestamp': datetime.fromisoformat(
                            tweet.get('created_at', '').replace('Z', '+00:00')
                        ) if tweet.get('created_at') else datetime.utcnow(),
                        'likes': tweet.get('likes', 0),
                        'retweets': tweet.get('retweets', 0),
                        'sentiment_score': 50,  # Will be calculated by AI
                        'impact_score': 0  # Will be calculated by AI
                    })
        except json.JSONDecodeError:
            # Try line-by-line parsing
            for line in output.strip().split('\n'):
                if line.strip():
                    tweets.append({
                        'id': f"twitter_{hash(line)}",
                        'source': 'twitter',
                        'title': line[:100],
                        'content': line,
                        'url': '',
                        'author': 'unknown',
                        'timestamp': datetime.utcnow(),
                        'likes': 0,
                        'retweets': 0,
                        'sentiment_score': 50,
                        'impact_score': 0
                    })
        
        return tweets
    
    def _filter_financial_content(
        self,
        tweets: List[Dict[str, Any]],
        min_relevance: float = 0.3
    ) -> List[Dict[str, Any]]:
        """Filter tweets for financial/relevant content."""
        filtered = []
        
        for tweet in tweets:
            content_lower = tweet.get('content', '').lower()
            
            # Check for financial keywords
            relevance_score = sum(
                1 for keyword in self.FINANCIAL_KEYWORDS
                if keyword.lower() in content_lower
            ) / len(self.FINANCIAL_KEYWORDS)
            
            # Check for ticker mentions
            tickers = self._extract_tickers(tweet.get('content', ''))
            if tickers:
                relevance_score = max(relevance_score, 0.8)
            
            if relevance_score >= min_relevance:
                tweet['relevance_score'] = relevance_score
                filtered.append(tweet)
        
        # Sort by relevance and engagement
        filtered.sort(
            key=lambda x: (
                x.get('relevance_score', 0) * 0.6 +
                min(x.get('likes', 0) / 100, 1) * 0.2 +
                min(x.get('retweets', 0) / 50, 1) * 0.2
            ),
            reverse=True
        )
        
        return filtered
    
    def _extract_tickers(self, text: str) -> List[str]:
        """Extract ticker symbols from text."""
        matches = self.TICKER_PATTERN.findall(text.upper())
        
        # Filter out common non-ticker words
        exclude = {
            'THE', 'AND', 'FOR', 'WITH', 'THAT', 'THIS', 'HAVE', 'HAS',
            'ARE', 'WERE', 'WILL', 'WOULD', 'COULD', 'SHOULD', 'CAN',
            ' Stocks', ' Stock', ' Market', ' Price'
        }
        
        return [t for t in matches if t not in exclude and len(t) >= 2]
    
    async def get_trending_tickers(self, limit: int = 10) -> List[str]:
        """Get trending ticker symbols from Twitter."""
        if not self.enabled:
            return []
        
        try:
            # Search for common financial discussions
            tweets = await self._search_twitter("stock OR $SPY OR $QQQ", limit=100)
            
            # Count ticker mentions
            ticker_counts = {}
            for tweet in tweets:
                tickers = self._extract_tickers(tweet.get('content', ''))
                for ticker in tickers:
                    ticker_counts[ticker] = ticker_counts.get(ticker, 0) + 1
            
            # Return most mentioned
            sorted_tickers = sorted(
                ticker_counts.items(),
                key=lambda x: x[1],
                reverse=True
            )
            
            return [t[0] for t in sorted_tickers[:limit]]
            
        except Exception as e:
            logger.error(f"Error getting trending tickers: {e}")
            return []


# Singleton
_twitter_channel = None

def get_twitter_channel() -> TwitterChannel:
    """Get Twitter channel singleton."""
    global _twitter_channel
    if _twitter_channel is None:
        _twitter_channel = TwitterChannel()
    return _twitter_channel