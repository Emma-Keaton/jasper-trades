"""
Quant Agent
Performs technical and statistical analysis.
From AutoHedge + Fincept QuantLib.
"""
from typing import Dict, Any, Optional, List
from app.agents.base import BaseAgent
from app.nvidia_nim import nvidia_client
from app.models import Signal
from app.services.agent_reach.market_intel_service import get_market_intel_service
import structlog

logger = structlog.get_logger(__name__)


class QuantAgent(BaseAgent):
    """
    Quant Agent - Technical and statistical analysis.

    This agent:
    - Analyzes price action and technicals
    - Computes statistical metrics
    - Identifies patterns and anomalies
    - Provides quantitative signals
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(
            name="Quant",
            model="meta/llama-3.1-8b-instruct",  # Balanced model for quant analysis
            config=config or {},
        )

        # Technical indicators config
        self.indicators = self.config.get('indicators', [
            'sma_20', 'sma_50', 'rsi', 'macd', 'bollinger', 'atr'
        ])

    async def analyze(self, market_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Perform quantitative analysis on market data.

        Args:
            market_data: Price history, volume, etc.

        Returns:
            Quantitative analysis with indicators and signals
        """
        try:
            # Calculate basic statistics
            prices = market_data.get('prices', [])
            volumes = market_data.get('volumes', [])

            if len(prices) < 2:
                return {"error": "Insufficient data"}

            # Simple calculations (can be extended with TA-Lib, pandas-ta, etc.)
            analysis = {
                'current_price': prices[-1],
                'price_change': prices[-1] - prices[0] if prices else 0,
                'price_change_pct': (prices[-1] / prices[0] - 1) * 100 if prices and prices[0] != 0 else 0,
                'avg_volume': sum(volumes) / len(volumes) if volumes else 0,
                'volatility': self._calculate_volatility(prices),
            }

            # Use NVIDIA NIM for pattern recognition with market intelligence
            symbol = market_data.get('symbol', '')
            news_context = ""
            if symbol:
                try:
                    market_intel_service = get_market_intel_service()
                    sentiment = await market_intel_service.get_sentiment(ticker=symbol)
                    if sentiment and sentiment.get('recent_articles', 0) > 0:
                        score = sentiment.get('overall_score', 50)
                        label = "bullish" if score > 60 else "bearish" if score < 40 else "neutral"
                        news_context = f"\n\nMarket Sentiment: {sentiment.get('recent_articles', 0)} articles, {label} ({score:.0f}/100)"
                except Exception as e:
                    logger.warning(f"Market sentiment lookup failed: {e}")

            prompt = f"""
Analyze this market data quantitatively:

Current Price: {analysis['current_price']}
Price Change: {analysis['price_change_pct']:.2f}%
Volatility: {analysis['volatility']:.4f}
Average Volume: {analysis['avg_volume']:.0f}{news_context}

Provide:
1. Trend direction (bullish/bearish/neutral)
2. Momentum status (strong/weak)
3. Key support/resistance levels
4. RSI interpretation (overbought/oversold/neutral)
5. Volume analysis

Output as JSON with: trend, momentum, support, resistance, rsi_status, volume_analysis, confidence
"""

            messages = [
                {"role": "system", "content": "You are a quantitative analyst AI."},
                {"role": "user", "content": prompt}
            ]

            response = await self.nvidia_client.chat_completion(
                messages,
                task_type='analysis',
            )

            import json
            try:
                quant_analysis = json.loads(response)
                analysis.update(quant_analysis)
            except:
                analysis['raw_analysis'] = response

            return analysis

        except Exception as e:
            logger.error(f"Quant analysis error: {e}")
            return {"error": str(e)}

    def _calculate_volatility(self, prices: List[float], window: int = 20) -> float:
        """Calculate rolling volatility."""
        if len(prices) < 2:
            return 0.0

        # Simple volatility calculation (can be enhanced)
        returns = [(prices[i] / prices[i-1] - 1) for i in range(1, len(prices))]

        if len(returns) < 2:
            return 0.0

        avg_return = sum(returns) / len(returns)
        variance = sum((r - avg_return) ** 2 for r in returns) / len(returns)

        return (variance ** 0.5) * 100  # As percentage

    async def generate_signal(
        self,
        symbol: str,
        analysis: Dict[str, Any],
    ) -> Optional[Signal]:
        """
        Generate a quantitative signal.

        Args:
            symbol: Trading symbol
            analysis: Quant analysis results

        Returns:
            Signal object or None
        """
        try:
            trend = analysis.get('trend', 'neutral')
            momentum = analysis.get('momentum', 'weak')

            # Simple logic: strong trend + strong momentum = signal
            if trend == 'neutral':
                return None

            action = 'buy' if trend == 'bullish' else 'sell'
            strength = 0.7 if momentum == 'strong' else 0.4

            signal = Signal(
                symbol=symbol,
                action=action,
                strength=strength,
                agent_name=self.name,
                reasoning=f"Quant signal: {trend} trend, {momentum} momentum",
                metadata={
                    'trend': trend,
                    'momentum': momentum,
                    'support': analysis.get('support'),
                    'resistance': analysis.get('resistance'),
                }
            )

            self.signals_generated += 1
            return signal

        except Exception as e:
            logger.error(f"Quant signal generation error: {e}")
            return None

    async def calculate_risk_metrics(
        self,
        returns: List[float],
    ) -> Dict[str, float]:
        """
        Calculate risk metrics from returns series.

        Returns:
            Dict with sharpe, sortino, max_drawdown, var_95
        """
        if len(returns) < 2:
            return {"error": "Insufficient data"}

        import statistics

        avg_return = statistics.mean(returns)
        std_return = statistics.stdev(returns) if len(returns) > 1 else 0

        # Annualized Sharpe (assuming daily returns)
        sharpe = (avg_return / std_return * 252 ** 0.5) if std_return != 0 else 0

        # Simple VaR calculation
        sorted_returns = sorted(returns)
        var_95_index = int(len(sorted_returns) * 0.05)
        var_95 = sorted_returns[var_95_index] if var_95_index < len(sorted_returns) else min(returns)

        return {
            'avg_return': avg_return,
            'volatility': std_return * 252 ** 0.5,
            'sharpe_ratio': sharpe,
            'var_95': var_95,
        }