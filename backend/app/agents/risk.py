"""
Risk Agent
Handles position sizing and risk assessment.
From AutoHedge.
"""
from typing import Dict, Any, Optional
from app.agents.base import BaseAgent
from app.nvidia_nim import nvidia_client
from app.models import Signal
from app.services.agent_reach.market_intel_service import get_market_intel_service
import structlog
import json

logger = structlog.get_logger(__name__)


class RiskAgent(BaseAgent):
    """
    Risk Agent - Position sizing and risk assessment.
    
    This agent:
    - Evaluates position risk
    - Determines appropriate position size
    - Sets stop-loss and take-profit levels
    - Approves/rejects trades based on risk
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(
            name="Risk",
            model="meta/llama-3.2-3b-instruct",  # Fast model for quick risk checks
            config=config or {},
        )
        
        # Risk parameters
        self.max_position_size = self.config.get('max_position_size', 0.1)  # 10% of portfolio
        self.max_portfolio_risk = self.config.get('max_portfolio_risk', 0.02)  # 2% max loss
        self.default_stop_loss = self.config.get('default_stop_loss', 0.05)  # 5% stop
        self.default_take_profit = self.config.get('default_take_profit', 0.10)  # 10% target
    
    async def analyze(self, market_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze market risk conditions.
        
        Args:
            market_data: Market volatility, correlation, etc.
        
        Returns:
            Risk assessment
        """
        try:
            prompt = f"""
Assess market risk conditions:

Market Data: {market_data}

Evaluate:
1. Overall market risk level (low/medium/high)
2. Volatility regime
3. Correlation risk
4. Liquidity conditions
5. Event risk (earnings, Fed, etc.)

Output as JSON with: risk_level, volatility_regime, correlation_risk, liquidity, event_risk, recommendations
"""
            
            messages = [
                {"role": "system", "content": "You are a risk management AI."},
                {"role": "user", "content": prompt}
            ]
            
            response = await self.nvidia_client.chat_completion(
                messages,
                task_type='analysis',
            )
            
            import json
            try:
                return json.loads(response)
            except:
                return {"raw_assessment": response}
                
        except Exception as e:
            logger.error(f"Risk analysis error: {e}")
            return {"error": str(e)}
    
    async def assess_position(
        self,
        symbol: str,
        signal: Signal,
        portfolio_value: float,
        current_positions: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Assess risk for a specific position.
        
        Returns:
            Risk assessment with approval and limits
        """
        try:
            # Get market intelligence for this symbol
            market_intel_service = get_market_intel_service()
            news_data = None
            sentiment_data = None
            news_context = ""
            
            try:
                # Fetch news and sentiment (non-blocking, doesn't fail if unavailable)
                news_data = await market_intel_service.get_news(ticker=symbol, limit=10)
                sentiment_data = await market_intel_service.get_sentiment(ticker=symbol)
                
                # Build news context for risk assessment
                if news_data and len(news_data) > 0 and sentiment_data:
                    sentiment_score = sentiment_data.get('overall_score', 50)
                    sentiment_label = "positive" if sentiment_score > 60 else "negative" if sentiment_score < 40 else "neutral"
                    news_context = f"\n\nMarket Intelligence:\n- Recent news articles: {len(news_data)}\n- Sentiment: {sentiment_score:.0f}/100 ({sentiment_label})\n- Sources: {len(sentiment_data.get('source_scores', {}))}"
            except Exception as intel_error:
                logger.warning(f"Market intelligence not available for {symbol}: {intel_error}")
            
            # Calculate current exposure
            current_exposure = sum(
                pos.get('market_value', 0) 
                for pos in current_positions.values()
            )
            
            exposure_ratio = current_exposure / portfolio_value if portfolio_value else 1
            
            # Use NVIDIA NIM for risk assessment with market intelligence context
            prompt = f"""
Assess the risk of this potential position:

Symbol: {symbol}
Signal Action: {signal.action}
Signal Strength: {signal.strength}
Signal Reasoning: {signal.reasoning}{news_context}

Portfolio Context:
- Total Value: ${portfolio_value:,.2f}
- Current Exposure: ${current_exposure:,.2f}
- Exposure Ratio: {exposure_ratio:.2%}

Risk Parameters:
- Max Position Size: {self.max_position_size:.1%}
- Max Portfolio Risk: {self.max_portfolio_risk:.1%}

Output JSON with:
- approval: true/false
- risk_level: "low"/"medium"/"high"
- max_position_size: float (dollar amount)
- stop_loss_pct: float
- take_profit_pct: float
- concerns: list of strings
"""
            
            messages = [
                {"role": "system", "content": "You are a risk management AI. Be conservative."},
                {"role": "user", "content": prompt}
            ]
            
            response = await self.nvidia_client.chat_completion(
                messages,
                task_type='execution',  # Fast response needed
            )
            
            import json
            try:
                assessment = json.loads(response)
                
                # Ensure required fields
                if 'approval' not in assessment:
                    assessment['approval'] = True
                if 'risk_level' not in assessment:
                    assessment['risk_level'] = 'medium'
                if 'max_position_size' not in assessment:
                    assessment['max_position_size'] = portfolio_value * self.max_position_size
                    
                return assessment
            except:
                return {
                    'approval': True,
                    'risk_level': 'medium',
                    'max_position_size': portfolio_value * self.max_position_size,
                    'concerns': ['Unable to parse risk assessment'],
                }
                
        except Exception as e:
            logger.error(f"Position risk assessment error: {e}")
            return {
                'approval': False,
                'risk_level': 'high',
                'concerns': [f'Error: {str(e)}'],
            }
    
    async def generate_signal(
        self,
        symbol: str,
        analysis: Dict[str, Any],
    ) -> Optional[Signal]:
        """
        Risk agent doesn't typically generate signals, but can issue warnings.
        """
        risk_level = analysis.get('risk_level', 'medium')
        
        if risk_level == 'high':
            # Issue a "reduce risk" signal
            signal = Signal(
                symbol=symbol,
                action='sell',
                strength=0.8,
                agent_name=self.name,
                reasoning=f"High risk detected: {analysis}",
                metadata={'risk_level': risk_level}
            )
            self.signals_generated += 1
            return signal
        
        return None
    
    def calculate_position_size(
        self,
        portfolio_value: float,
        stop_loss_pct: float,
        risk_per_trade: float = 0.01,
    ) -> float:
        """
        Calculate position size based on risk parameters.
        
        Args:
            portfolio_value: Total portfolio value
            stop_loss_pct: Stop loss as percentage
            risk_per_trade: Risk per trade (default 1%)
        
        Returns:
            Position size in dollars
        """
        # Position size = (Portfolio * Risk per trade) / Stop loss %
        if stop_loss_pct <= 0:
            stop_loss_pct = self.default_stop_loss
        
        position_size = (portfolio_value * risk_per_trade) / stop_loss_pct
        
        # Cap at max position size
        max_size = portfolio_value * self.max_position_size
        position_size = min(position_size, max_size)
        
        return position_size
