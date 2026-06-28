"""
Sentiment Analysis Service using NVIDIA NIM Models

Analyzes news and social media content for:
- Sentiment score (positive/negative/neutral)
- Impact assessment (market-moving potential)
- Ticker/entity extraction
- Trading signal generation

Model Routing:
- Llama-3.2-3B: Fast sentiment scoring (~50ms)
- Llama-3.3-70B: Deep impact analysis (~300ms)
"""

import json
from datetime import datetime
from typing import Any, Dict, List, Optional

from loguru import logger

from app.nvidia_nim import nvidia_client


class SentimentAnalysisService:
    """AI-powered sentiment analysis using NVIDIA NIM models."""
    
    def __init__(self):
        self.fast_model = "meta/llama-3.2-3b-instruct"
        self.smart_model = "meta/llama-3.3-70b-instruct"
    
    async def analyze_sentiment(
        self,
        text: str,
        tickers: Optional[List[str]] = None,
        use_fast_model: bool = True
    ) -> Dict[str, Any]:
        """
        Analyze sentiment of news/article text.
        
        Args:
            text: Text content to analyze
            tickers: Known ticker symbols mentioned (optional)
            use_fast_model: Use 3B model for speed (False = use 70B for accuracy)
            
        Returns:
            {
                'sentiment_score': 0-100 (50 = neutral),
                'sentiment_label': 'positive'/'negative'/'neutral',
                'confidence': 0-1,
                'tickers_mentioned': list of extracted tickers,
                'key_topics': list of topics,
                'actionable': bool (whether this contains trading signals)
            }
        """
        try:
            model = self.fast_model if use_fast_model else self.smart_model
            
            tickers_context = f"\nKnown tickers to watch for: {', '.join(tickers)}" if tickers else ""
            
            prompt = f"""Analyze the following financial news for sentiment and trading relevance:

{text}{tickers_context}

Extract and analyze:
1. Overall sentiment (positive/negative/neutral)
2. Sentiment score 0-100 (50=neutral, >65=positive, <35=negative)
3. Confidence level (0-1)
4. All ticker symbols mentioned
5. Key topics/themes
6. Is this actionable for trading? (yes/no)

Output as STRICT JSON only, no markdown, no explanations:
{{
    "sentiment_score": number,
    "sentiment_label": "positive"|"negative"|"neutral",
    "confidence": number,
    "tickers_mentioned": ["TICKER1", "TICKER2"],
    "key_topics": ["topic1", "topic2"],
    "actionable": true|false
}}
"""
            
            messages = [
                {"role": "system", "content": "You are a financial sentiment analysis AI. Output ONLY valid JSON."},
                {"role": "user", "content": prompt}
            ]
            
            response = await nvidia_client.chat_completion(
                messages,
                task_type='analysis',
                model_override=model,
                temperature=0.1  # Low temperature for consistent JSON output
            )
            
            # Parse JSON response
            try:
                result = json.loads(response.strip())
                
                # Validate and normalize
                result['sentiment_score'] = max(0, min(100, float(result.get('sentiment_score', 50))))
                result['confidence'] = max(0, min(1, float(result.get('confidence', 0.5))))
                result['actionable'] = bool(result.get('actionable', False))
                result['tickers_mentioned'] = result.get('tickers_mentioned', [])
                result['key_topics'] = result.get('key_topics', [])
                
                # Set label based on score if not provided
                if 'sentiment_label' not in result:
                    score = result['sentiment_score']
                    if score > 65:
                        result['sentiment_label'] = 'positive'
                    elif score < 35:
                        result['sentiment_label'] = 'negative'
                    else:
                        result['sentiment_label'] = 'neutral'
                
                result['analyzed_at'] = datetime.utcnow().isoformat()
                return result
                
            except json.JSONDecodeError:
                logger.warning(f"Failed to parse JSON response: {response[:200]}")
                return {
                    'sentiment_score': 50,
                    'sentiment_label': 'neutral',
                    'confidence': 0,
                    'tickers_mentioned': tickers or [],
                    'key_topics': [],
                    'actionable': False,
                    'raw_response': response[:500],
                    'analyzed_at': datetime.utcnow().isoformat()
                }
                
        except Exception as e:
            logger.error(f"Sentiment analysis error: {e}")
            return {
                'sentiment_score': 50,
                'sentiment_label': 'neutral',
                'confidence': 0,
                'tickers_mentioned': tickers or [],
                'key_topics': [],
                'actionable': False,
                'error': str(e),
                'analyzed_at': datetime.utcnow().isoformat()
            }
    
    async def assess_impact(
        self,
        text: str,
        tickers: List[str],
        sentiment_score: float
    ) -> Dict[str, Any]:
        """
        Assess market impact of news (deeper analysis with 70B model).
        
        Args:
            text: News content
            tickers: Affected tickers
            sentiment_score: Pre-calculated sentiment score
            
        Returns:
            {
                'impact_score': 0-100 (market-moving potential),
                'impact_level': 'low'/'medium'/'high'/'critical',
                'time_horizon': 'intraday'/'short-term'/'long-term',
                'sector_impact': list of affected sectors,
                'catalyst_type': 'earnings'/'regulatory'/'macro'/'company-specific',
                'confidence': 0-1
            }
        """
        try:
            prompt = f"""Assess the market impact of this financial news:

News: {text[:1000]}

Affected Tickers: {', '.join(tickers)}
Current Sentiment Score: {sentiment_score:.0f}/100

Analyze:
1. Impact score (0-100): How market-moving is this?
2. Impact level (low/medium/high/critical)
3. Time horizon (intraday/short-term/long-term)
4. Category (earnings/regulatory/macro/company-specific)
5. Confidence (0-1)

Output as STRICT JSON:
{{
    "impact_score": number,
    "impact_level": "low"|"medium"|"high"|"critical",
    "time_horizon": "intraday"|"short-term"|"long-term",
    "catalyst_type": "earnings"|"regulatory"|"macro"|"company-specific",
    "confidence": number
}}
"""
            
            messages = [
                {"role": "system", "content": "You are a market impact analyst. Output ONLY valid JSON."},
                {"role": "user", "content": prompt}
            ]
            
            response = await nvidia_client.chat_completion(
                messages,
                task_type='analysis',
                model_override=self.smart_model,
                temperature=0.1
            )
            
            try:
                result = json.loads(response.strip())
                
                result['impact_score'] = max(0, min(100, float(result.get('impact_score', 0))))
                result['confidence'] = max(0, min(1, float(result.get('confidence', 0.5))))
                
                # Set impact level if not provided
                if 'impact_level' not in result:
                    score = result['impact_score']
                    if score > 75:
                        result['impact_level'] = 'critical'
                    elif score > 55:
                        result['impact_level'] = 'high'
                    elif score > 35:
                        result['impact_level'] = 'medium'
                    else:
                        result['impact_level'] = 'low'
                
                result['assessed_at'] = datetime.utcnow().isoformat()
                return result
                
            except json.JSONDecodeError:
                logger.warning(f"Failed to parse impact assessment: {response[:200]}")
                return {
                    'impact_score': 50,
                    'impact_level': 'medium',
                    'time_horizon': 'short-term',
                    'catalyst_type': 'company-specific',
                    'confidence': 0,
                    'assessed_at': datetime.utcnow().isoformat()
                }
                
        except Exception as e:
            logger.error(f"Impact assessment error: {e}")
            return {
                'impact_score': 50,
                'impact_level': 'medium',
                'time_horizon': 'short-term',
                'catalyst_type': 'company-specific',
                'confidence': 0,
                'error': str(e),
                'assessed_at': datetime.utcnow().isoformat()
            }
    
    async def analyze_news_batch(
        self,
        articles: List[Dict[str, Any]],
        enable_impact_scoring: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Analyze multiple news articles in batch.
        
        Args:
            articles: List of article dicts with 'content' and 'tickers_mentioned'
            enable_impact_scoring: Run deeper impact analysis (slower)
            
        Returns:
            Articles with added sentiment and impact scores
        """
        results = []
        
        for i, article in enumerate(articles):
            # Analyze sentiment
            sentiment = await self.analyze_sentiment(
                text=article.get('content', '') + ' ' + article.get('title', ''),
                tickers=article.get('tickers_mentioned', []),
                use_fast_model=True  # Use fast model for batch
            )
            
            # Update article
            updated_article = article.copy()
            updated_article['sentiment_score'] = sentiment['sentiment_score']
            updated_article['sentiment_label'] = sentiment['sentiment_label']
            updated_article['sentiment_confidence'] = sentiment['confidence']
            updated_article['actionable'] = sentiment['actionable']
            
            # Merge extracted tickers
            new_tickers = [t for t in sentiment.get('tickers_mentioned', []) 
                          if t not in updated_article.get('tickers_mentioned', [])]
            updated_article['tickers_mentioned'] = list(set(
                updated_article.get('tickers_mentioned', []) + new_tickers
            ))
            
            # Optional impact scoring
            if enable_impact_scoring and sentiment['actionable']:
                impact = await self.assess_impact(
                    text=article.get('content', ''),
                    tickers=updated_article['tickers_mentioned'],
                    sentiment_score=sentiment['sentiment_score']
                )
                updated_article['impact_score'] = impact['impact_score']
                updated_article['impact_level'] = impact['impact_level']
                updated_article['impact_confidence'] = impact['confidence']
            else:
                updated_article['impact_score'] = 0
                updated_article['impact_level'] = 'low'
            
            results.append(updated_article)
            
            # Progress logging
            if (i + 1) % 10 == 0:
                logger.info(f"Analyzed {i + 1}/{len(articles)} articles")
        
        return results


# Singleton
_sentiment_service = None

def get_sentiment_service() -> SentimentAnalysisService:
    """Get singleton SentimentAnalysisService instance."""
    global _sentiment_service
    if _sentiment_service is None:
        _sentiment_service = SentimentAnalysisService()
    return _sentiment_service