"""
Reddit Channel Integration for Market Intelligence

Uses Agent Reach's OpenCLI or rdt-cli for Reddit data.
Requires browser authentication for r/wallstreetbets, r/stocks, etc.

Usage:
    from app.services.agent_reach.channels.reddit_channel import RedditChannel
    
    channel = RedditChannel()
    news = await channel.fetch_subreddit_posts(subreddit="wallstreetbets", limit=20)
"""

import asyncio
import re
from datetime import datetime
from typing import Any, Dict, List, Optional
import subprocess
import json

from loguru import logger


class RedditChannel:
    """Reddit channel for fetching financial discussions."""
    
    # Financial subreddits to monitor
    FINANCIAL_SUBREDDITS = [
        'wallstreetbets',
        'stocks',
        'investing',
        'securityanalysis',
        'stocksinvesting',
        'stockmarket'
    ]
    
    # Ticker pattern
    TICKER_PATTERN = re.compile(r'\b\$?([A-Z]{1,5})\b')
    
    def __init__(self):
        self.enabled = False
        self.cli_available = self._check_cli_availability()
        
        if self.cli_available:
            logger.info("Reddit CLI available for market intelligence")
            self.enabled = True
        else:
            logger.info("Reddit CLI not available. Install with: pipx install 'git+https://github.com/public-clis/rdt-cli.git@5e4fb3720d5c174e976cd425ccc3b879d52cac66'")
    
    def _check_cli_availability(self) -> bool:
        """Check if rdt-cli or opencli is available."""
        try:
            # Check for rdt-cli
            result = subprocess.run(
                ['rdt', '--help'],
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
    
    async def fetch_subreddit_posts(
        self,
        subreddit: str = "wallstreetbets",
        ticker: Optional[str] = None,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Fetch posts from a specific subreddit.
        
        Args:
            subreddit:Subreddit name (e.g., "wallstreetbets")
            ticker: Filter by ticker symbol
            limit: Maximum number of posts to fetch
            
        Returns:
            List of post dictionaries
        """
        if not self.enabled:
            logger.warning("Reddit channel not enabled")
            return []
        
        try:
            # Build search query
            query = self._build_search_query(ticker)
            
            # Execute rdt-cli search
            posts = await self._search_reddit(subreddit, query, limit)
            
            # Extract tickers mentioned
            for post in posts:
                post['tickers_mentioned'] = self._extract_tickers(post['content'])
            
            return posts
            
        except Exception as e:
            logger.error(f"Reddit fetch error: {e}")
            return []
    
    def _build_search_query(self, ticker: Optional[str] = None) -> str:
        """Build Reddit search query."""
        if ticker:
            return f"${ticker} OR {ticker}"
        return "stock OR buy OR sell OR earnings OR market"
    
    async def _search_reddit(
        self,
        subreddit: str,
        query: str,
        limit: int
    ) -> List[Dict[str, Any]]:
        """Search Reddit using rdt-cli or opencli."""
        try:
            # Try rdt-cli first
            result = subprocess.run(
                ['rdt', 'search', subreddit, query, '--limit', str(limit)],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0:
                return self._parse_reddit_output(result.stdout)
            
            # Fallback to opencli
            result = subprocess.run(
                ['opencli', 'reddit', 'search', subreddit, query, '--limit', str(limit)],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0:
                return self._parse_reddit_output(result.stdout)
            
            logger.error(f"Reddit search failed: {result.stderr}")
            return []
            
        except subprocess.TimeoutExpired:
            logger.error("Reddit search timed out")
            return []
        except Exception as e:
            logger.error(f"Reddit search error: {e}")
            return []
    
    def _parse_reddit_output(self, output: str) -> List[Dict[str, Any]]:
        """Parse rdt-cli output into structured data."""
        posts = []
        
        try:
            # Try to parse as JSON first
            data = json.loads(output)
            if isinstance(data, list):
                for post in data:
                    posts.append({
                        'id': post.get('id', ''),
                        'source': 'reddit',
                        'title': post.get('title', ''),
                        'content': post.get('selftext', '') or post.get('title', ''),
                        'url': post.get('url', ''),
                        'author': post.get('author', ''),
                        'timestamp': datetime.fromisoformat(
                            datetime.utcfromtimestamp(post.get('created', 0) if post.get('created') else 0).isoformat()
                        ),
                        'upvotes': post.get('score', 0),
                        'comments': post.get('num_comments', 0),
                        'sentiment_score': 50,
                        'impact_score': 0
                    })
        except json.JSONDecodeError:
            # Try line-by-line parsing
            for line in output.strip().split('\n'):
                if line.strip():
                    posts.append({
                        'id': f"reddit_{hash(line)}",
                        'source': 'reddit',
                        'title': line[:100],
                        'content': line,
                        'url': '',
                        'author': 'unknown',
                        'timestamp': datetime.utcnow(),
                        'upvotes': 0,
                        'comments': 0,
                        'sentiment_score': 50,
                        'impact_score': 0
                    })
        
        return posts
    
    def _extract_tickers(self, text: str) -> List[str]:
        """Extract ticker symbols from text."""
        matches = self.TICKER_PATTERN.findall(text.upper())
        
        # Filter out common non-ticker words
        exclude = {
            'THE', 'AND', 'FOR', 'WITH', 'THAT', 'THIS', 'HAVE', 'HAS',
            'ARE', 'WERE', 'WILL', 'WOULD', 'COULD', 'SHOULD', 'CAN',
            'SPY', 'QQQ', 'DIA', 'IWM', 'TLT', 'GLD', 'SLV'  # Common ETFs to exclude from random mentions
        }
        
        return list(set([t for t in matches if t not in exclude and len(t) >= 2 and len(t) <= 5]))
    
    async def get_trending_tickers(self, limit: int = 10) -> List[str]:
        """Get trending ticker symbols from Reddit."""
        if not self.enabled:
            return []
        
        try:
            # Fetch from main financial subreddits
            all_posts = []
            for subreddit in self.FINANCIAL_SUBREDDITS[:3]:
                posts = await self._search_reddit(subreddit, "stock OR $", limit=50)
                all_posts.extend(posts)
            
            # Count ticker mentions
            ticker_counts = {}
            for post in all_posts:
                tickers = self._extract_tickers(post.get('content', ''))
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
_reddit_channel = None

def get_reddit_channel() -> RedditChannel:
    """Get Reddit channel singleton."""
    global _reddit_channel
    if _reddit_channel is None:
        _reddit_channel = RedditChannel()
    return _reddit_channel