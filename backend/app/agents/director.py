"""
Director Agent
Generates trading strategy and theses from market analysis.
From AutoHedge.
"""
from typing import Dict, Any, Optional, List
from app.agents.base import BaseAgent
from app.nvidia_nim import nvidia_client
from app.models import Signal
from app.services.agent_reach.market_intel_service import get_market_intel_service
import structlog

logger = structlog.get_logger(__name__)


class DirectorAgent(BaseAgent):
    """
    Director Agent - Generates trading strategy and theses.
    
    This agent:
    - Analyzes market conditions
    - Generates trading theses
    - Decides which opportunities to pursue
    - Coordinates with other agents
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(
            name="Director",
            model="meta/llama-3.3-70b-instruct",  # Smart model for strategy
            config=config or {},
        )
    
    async def analyze(self, market_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze market conditions and generate strategic insights.
        
        Args:
            market_data: Market data including prices, volumes, news, etc.
        
        Returns:
            Strategic analysis with theses and recommendations
        """
        # Extract symbols from market data for news lookup
        symbols = market_data.get('symbols', [])
        if isinstance(symbols, str):
            symbols = [symbols]
        
        # Get market intelligence for mentioned symbols
        news_context = ""
        if symbols:
            try:
                market_intel_service = get_market_intel_service()
                for symbol in symbols[:3]:  # Look up top 3 symbols
                    try:
                        sentiment = await market_intel_service.get_sentiment(ticker=symbol)
                        if sentiment and sentiment.get('recent_articles', 0) > 0:
                            score = sentiment.get('overall_score', 50)
                            label = "bullish" if score > 60 else "bearish" if score < 40 else "neutral"
                            news_context += f"\n- {symbol}: {sentiment.get('recent_articles', 0)} recent articles, sentiment {label} ({score:.0f}/100)"
                    except:
                        pass
            except Exception as e:
                logger.warning(f"Market intelligence lookup failed: {e}")
        
        prompt = f"""
You are the Director Agent of an AI trading system. Your role is to analyze market conditions 
and generate strategic trading theses.

Market Data:
{market_data}

Market Intelligence:{news_context if news_context else " No real-time news available."}

Generate a comprehensive analysis including:
1. Market regime (bullish/bearish/sideways)
2. Key trends and patterns
3. Potential opportunities
4. Risk factors to watch
5. Recommended focus areas

Output as JSON with: market_regime, trends, opportunities, risks, focus_symbols, confidence
"""
        
        try:
            messages = [
                {"role": "system", "content": "You are a strategic trading analyst AI."},
                {"role": "user", "content": prompt}
            ]
            
            response = await self.nvidia_client.chat_completion(
                messages, 
                task_type='analysis',
                temperature=0.5,  # Lower temperature for more focused analysis
            )
            
            # Parse JSON response
            import json
            try:
                return json.loads(response)
            except:
                return {"raw_analysis": response}
                
        except Exception as e:
            logger.error(f"Director analysis error: {e}")
            return {"error": str(e)}
    
    async def generate_signal(
        self,
        symbol: str,
        analysis: Dict[str, Any],
    ) -> Optional[Signal]:
        """
        Generate a strategic signal based on analysis.
        
        Args:
            symbol: Trading symbol
            analysis: Strategic analysis results
        
        Returns:
            Signal object or None
        """
        try:
            # Use NVIDIA NIM to generate signal
            prompt = f"""
Based on this strategic analysis, should we trade {symbol}?

Analysis: {analysis}

Output JSON with:
- action: "buy", "sell", or "hold"
- strength: 0-1 confidence
- reasoning: brief explanation
- target_allocation: 0-1 (portion of portfolio)
"""
            
            messages = [
                {"role": "system", "content": "Generate trading signals from strategic analysis."},
                {"role": "user", "content": prompt}
            ]
            
            response = await self.nvidia_client.chat_completion(
                messages,
                task_type='analysis',
            )
            
            import json
            signal_data = json.loads(response)
            
            # Create signal
            action = signal_data.get('action', 'hold')
            if action == 'hold':
                return None
            
            signal = Signal(
                symbol=symbol,
                action=action,
                strength=signal_data.get('strength', 0.5),
                agent_name=self.name,
                reasoning=signal_data.get('reasoning', ''),
                metadata={
                    'target_allocation': signal_data.get('target_allocation', 0.1),
                    'analysis': analysis,
                }
            )
            
            self.signals_generated += 1
            return signal
            
        except Exception as e:
            logger.error(f"Director signal generation error: {e}")
            return None
    
    async def generate_thesis(
        self,
        market_context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Generate a trading thesis from market context.
        
        Returns:
            Thesis with entry/exit rationale
        """
        prompt = f"""
Generate a trading thesis based on:
{market_context}

Output JSON with:
- thesis_type: "long", "short", "hedge"
- rationale: string
- entry_conditions: list
- exit_conditions: list
- time_horizon: "intraday", "swing", "position"
- confidence: 0-1
"""
        
        try:
            messages = [
                {"role": "system", "content": "Generate trading theses."},
                {"role": "user", "content": prompt}
            ]
            
            response = await self.nvidia_client.chat_completion(
                messages,
                task_type='analysis',
            )
            
            import json
            return json.loads(response)
        except Exception as e:
            logger.error(f"Thesis generation error: {e}")
            return {}
