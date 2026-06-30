"""
Twitter Channel Integration for Market Intelligence

Uses OpenCLI for real-time Twitter/X data via browser authentication.
No API keys needed - uses your logged-in Chrome session.

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
    """Twitter channel for fetching financial news and sentiment via OpenCLI."""

    # Financial/ticker patterns
    TICKER_PATTERN = re.compile(r'\$([A-Z]{1,5})|\\b[A-Z]{2,5}\\b')
    
    # Financial search terms
    FINANCIAL_SEARCH_TERMS = [
        'stock market',
        'earnings report',
        'SPY',
        'QQQ',
        'market crash',
        'bull market',
        'Fed rate',
        'inflation data',
        'tech stocks',
        'crypto market',
        'Bitcoin',
        'Ethereum'
    ]

    def __init__(self):
        self.enabled = False
        self.cli_available = self._check_cli_availability()

        if self.cli_available:
            logger.info("Twitter/OpenCLI available for market intelligence")
            self.enabled = True
        else:
            logger.info("Twitter/OpenCLI not available")

    def _check_cli_availability(self) -> bool:
        """Check if OpenCLI is available."""
        try:
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
        limit: int = 30
    ) -> List[Dict[str, Any]]:
        """
        Fetch financial news/tweets using OpenCLI.

        Args:
            ticker: Stock ticker symbol (e.g., "AAPL")
            keywords: Search keywords
            limit: Maximum tweets to fetch

        Returns:
            List of tweet dictionaries
        """
        if not self.enabled:
            logger.warning("Twitter channel not enabled")
            return []

        try:
            # Build search query
            query = self._build_search_query(ticker, keywords)

            # Execute OpenCLI Twitter search
            tweets = await self._search_twitter_opencli(query, limit)

            # Extract tickers mentioned
            for tweet in tweets:
                tweet['tickers_mentioned'] = self._extract_tickers(tweet['content'])

            return tweets

        except Exception as e:
            logger.error(f"Twitter fetch error: {e}")
            import traceback
            traceback.print_exc()
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
            # Default financial terms
            parts.extend(self.FINANCIAL_SEARCH_TERMS[:3])

        return " OR ".join(parts[:5])  # Limit query length

    async def _search_twitter_opencli(self, query: str, limit: int) -> List[Dict[str, Any]]:
        """Search Twitter using OpenCLI browser bridge."""
        try:
            # Use OpenCLI for Twitter search
            result = subprocess.run(
                [
                    'opencli', 'twitter', 'search',
                    '--query', query,
                    '--limit', str(limit),
                    '--format', 'json'
                ],
                capture_output=True,
                text=True,
                timeout=30
            )

            if result.returncode == 0 and result.stdout.strip():
                return self._parse_opencli_output(result.stdout)

            if result.stderr:
                logger.error(f"Twitter search stderr: {result.stderr}")
            return []

        except subprocess.TimeoutExpired:
            logger.error("Twitter search timed out")
            return []
        except Exception as e:
            logger.error(f"Twitter search error: {e}")
            import traceback
            traceback.print_exc()
            return []

    def _parse_opencli_output(self, output: str) -> List[Dict[str, Any]]:
        """Parse OpenCLI Twitter output."""
        tweets = []

        try:
            data = json.loads(output)
            if isinstance(data, list):
                for tweet in data:
                    tweets.append({
                        'id': tweet.get('id', f"tw_{hash(tweet.get('text', ''))}"),
                        'source': 'twitter',
                        'title': tweet.get('text', '')[:100],
                        'content': tweet.get('text', ''),
                        'url': tweet.get('url', tweet.get('permalink', '')),
                        'author': tweet.get('user', {}).get('username', 
                                   tweet.get('author', 'unknown')),
                        'timestamp': datetime.utcnow(),  # Will be parsed if available
                        'likes': tweet.get('likes', tweet.get('likes_count', 0)),
                        'retweets': tweet.get('retweets', tweet.get('retweet_count', 0)),
                        'sentiment_score': 50,
                        'impact_score': 0
                    })
        except json.JSONDecodeError:
            logger.warning("Failed to parse Twitter JSON output")

        return tweets

    def _extract_tickers(self, text: str) -> List[str]:
        """Extract ticker symbols from text."""
        # Match $TICKER or WORD_TICKER patterns
        matches = re.findall(r'\$([A-Z]{1,5})|_([A-Z]{1,5})\\b', text.upper())
        
        # Flatten and filter
        tickers = []
        for match in matches:
            ticker = match[0] or match[1]
            if ticker and len(ticker) >= 2:
                tickers.append(ticker)

        # Remove duplicates
        return list(set(tickers))

    async def get_trending_tickers(self, limit: int = 10) -> List[str]:
        """Get trending ticker symbols from Twitter."""
        if not self.enabled:
            return []

        try:
            # Search for common financial discussions
            tweets = await self._search_twitter_opencli("stock OR $SPY OR $QQQ", limit=100)

            # Count ticker mentions
            ticker_counts = {}
            for tweet in tweets:
                tickers = self._extract_tickers(tweet.get('content', ''))
                for ticker in tickers:
                    # Skip common non-ticker symbols
                    if ticker in ['SPY', 'QQQ', 'DIA']:
                        continue
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