"""
Fincept Specialist Agents - Analyst Team
4 specialized analysts covering fundamentals, technicals, sentiment, and macro.
"""
from typing import Dict, Any, Optional, List
from app.agents.base import BaseAgent
from app.nvidia_nim import nvidia_client
from app.services.data_connectors import DataConnectorService
import structlog

logger = structlog.get_logger(__name__)


# ============== ANALYST TEAM ==============

class FundamentalsAnalyst(BaseAgent):
    """
    Fundamental Analyst - Financial Statement Deep Dive
    
    Analyzes:
    - Income statements, balance sheets, cash flow
    - DCF valuation
    - Financial ratios (P/E, P/B, ROE, ROA, margins)
    - Growth rates, guidance
    - Competitive positioning
    """
    
    def __init__(self):
        super().__init__(
            name="FundamentalsAnalyst",
            model="nvidia/nemotron-3-ultra-550b-a55b",
            config={
                "system_prompt": """You are a fundamental analyst at a top investment bank.

Analyze:
1. Financial statements (income, balance sheet, cash flow)
2. Valuation metrics (P/E, P/B, EV/EBITDA, DCF)
3. Profitability (gross margin, operating margin, ROE, ROA)
4. Growth (revenue CAGR, earnings CAGR)
5. Balance sheet health (debt/equity, current ratio, interest coverage)
6. Competitive advantages (moat assessment)

Output should include:
- Intrinsic value estimate (DCF methodology)
- Comparable company analysis
- Buy/hold/sell with price target
- Key risks and catalysts"""
            }
        )
    
    async def analyze(self, symbol: str, financials: Dict[str, Any]) -> Dict[str, Any]:
        """Perform fundamental analysis."""
        data_service = DataConnectorService()
        
        # Pull additional data if needed
        # financials already provided
        
        prompt = f"""Perform fundamental analysis on {symbol}:
Financial Data:
- Revenue (TTM): ${financials.get('revenue', 'N/A')}B
- Net Income (TTM): ${financials.get('net_income', 'N/A')}B
- Gross Margin: {financials.get('gross_margin', 'N/A')}%
- Operating Margin: {financials.get('operating_margin', 'N/A')}%
- ROE: {financials.get('roe', 'N/A')}%
- Debt/Equity: {financials.get('debt_equity', 'N/A')}
- P/E: {financials.get('pe_ratio', 'N/A')}
- P/B: {financials.get('pb_ratio', 'N/A')}

Provide:
1. DCF intrinsic value estimate
2. Comparable analysis summary
3. Financial health assessment
4. Buy/hold/sell recommendation with price target"""
        
        response = await nvidia_client.chat_completion(
            [{"role": "system", "content": self.system_prompt},
             {"role": "user", "content": prompt}],
            task_type="portfolio"
        )
        
        return {
            "analyst": "Fundamentals",
            "intrinsic_value": self._extract_intrinsic_value(response),
            "price_target": self._extract_price_target(response),
            "rating": self._extract_rating(response),
            "thesis": response
        }


class TechnicalAnalyst(BaseAgent):
    """
    Technical Analyst - Charts, Patterns, Indicators
    
    Analyzes:
    - Price patterns (head & shoulders, double tops/bottoms)
    - Moving averages (SMA, EMA, crossovers)
    - Momentum indicators (RSI, MACD, Stochastic)
    - Volume analysis
    - Support/resistance levels
    - Fibonacci retracements
    """
    
    def __init__(self):
        super().__init__(
            name="TechnicalAnalyst",
            model="microsoft/phi-3.5-moe-instruct",  # Fast pattern recognition
            config={
                "system_prompt": """You are a technical analyst with 20 years of chart reading experience.

Analyze:
1. Price patterns (H&S, double top/bottom, triangles, flags)
2. Moving averages (50-day, 200-day SMA; golden/death cross)
3. Momentum (RSI overbought/oversold, MACD crossovers)
4. Volume (accumulation/distribution, OBV)
5. Support/resistance levels
6. Fibonacci retracements/extensions
7. Trend analysis (uptrend, downtrend, consolidation)

Provide actionable setup:
- Entry price
- Stop loss
- Price targets
- Time horizon"""
            }
        )
    
    async def analyze(self, symbol: str, ohlcv: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Perform technical analysis."""
        # Calculate indicators (simplified - would use TA-Lib or pandas-ta in production)
        
        prompt = f"""Analyze {symbol} technically:

Recent price action (last 20 bars):
{self._format_ohlcv(ohlcv)}

Pattern recognition:
- Any head & shoulders, double top/bottom?
- Triangle, wedge, or flag patterns?
- Key support/resistance levels?

Indicators:
- RSI: Is it overbought (>70) or oversold (<30)?
- MACD: Bullish or bearish crossover?
- Moving averages: Golden cross (50>200) or death cross?
- Volume: Accumulation or distribution?

Provide:
1. Current trend (uptrend/downtrend/consolidation)
2. Pattern identified
3. Entry/stop/target levels
4. Risk/reward ratio
5. Time horizon"""
        
        response = await nvidia_client.chat_completion(
            [{"role": "system", "content": self.system_prompt},
             {"role": "user", "content": prompt}],
            task_type="execution"
        )
        
        return {
            "analyst": "Technical",
            "trend": self._extract_trend(response),
            "pattern": self._extract_pattern(response),
            "entry": self._extract_level(response, "entry"),
            "stop_loss": self._extract_level(response, "stop"),
            "target": self._extract_level(response, "target"),
            "setup": response
        }


class SentimentAnalyst(BaseAgent):
    """
    Sentiment Analyst - News, Social Media, Positioning
    
    Analyzes:
    - News sentiment (positive/negative/neutral)
    - Social media buzz (Reddit, Twitter, StockTwits)
    - Analyst upgrades/downgrades
    - Insider buying/selling
    - Institutional positioning (13F filings)
    - Options flow (put/call ratios)
    """
    
    def __init__(self):
        super().__init__(
            name="SentimentAnalyst",
            model="moonshotai/kimi-k2.6",  # Good at NLP/sentiment
            config={
                "system_prompt": """You are a sentiment analyst tracking market psychology.

Analyze:
1. News sentiment (positive/negative/neutral tone)
2. Social media buzz (Reddit r/wallstreetbets, Twitter, StockTwits)
3. Analyst actions (upgrades, downgrades, price target changes)
4. Insider transactions (buying/selling by executives)
5. Institutional positioning (13F filings, 13D activism)
6. Options flow (put/call ratios, unusual activity)
7. Short interest changes

Sentiment extremes often signal contrarian opportunities:
- Extreme bullishness = potential top
- Extreme bearishness = potential bottom

Provide sentiment score (-1 to +1) and actionable insights."""
            }
        )
    
    async def analyze(self, symbol: str, news: List[str], social_data: Optional[Dict] = None) -> Dict[str, Any]:
        """Analyze sentiment from news and social data."""
        prompt = f"""Analyze sentiment for {symbol}:

Recent news headlines:
{self._format_news(news)}

{'Social media data:\n' + str(social_data) if social_data else 'No social data available'}

Assess:
1. Overall news sentiment (positive/negative/neutral)?
2. Social media sentiment - bullish or bearish crowd?
3. Any notable analyst upgrades/downgrades?
4. Insider buying or selling?
5. Institutional activity?
6. Options flow - puts or calls favored?

Provide:
- Sentiment score (-1.0 to +1.0)
- Crowd psychology (greed/fear/extreme?)
- Contrarian signal? (yes/no, why)
- Actionable insight"""
        
        response = await nvidia_client.chat_completion(
            [{"role": "system", "content": self.system_prompt},
             {"role": "user", "content": prompt}],
            task_type="analysis"
        )
        
        return {
            "analyst": "Sentiment",
            "sentiment_score": self._extract_sentiment_score(response),
            "crowd_psychology": self._extract_psychology(response),
            "contrarian_signal": self._extract_contrarian_view(response),
            "summary": response
        }


class MacroAnalyst(BaseAgent):
    """
    Macro Analyst - Fed, Rates, Geopolitics, Global Flows
    
    Analyzes:
    - Federal Reserve policy (rates, QE/QT)
    - Economic data (GDP, inflation, employment)
    - Yield curve (normal/inverted)
    - Dollar strength (DXY)
    - Commodity prices (oil, gold)
    - Geopolitical events
    - Global capital flows
    """
    
    def __init__(self):
        super().__init__(
            name="MacroAnalyst",
            model="nvidia/nemotron-3-ultra-550b-a55b",
            config={
                "system_prompt": """You are a macro strategist at a global investment bank.

Analyze:
1. Fed policy ( Fed funds rate, dot plot, QE/QT)
2. Economic data (GDP growth, CPI/PCE inflation, unemployment)
3. Yield curve (2s10s spread - normal/inverted?)
4. Dollar (DXY) - strength or weakness?
5. Commodities (oil, gold, copper) - what do they signal?
6. Geopolitics (trade wars, conflicts, elections)
7. Global capital flows (EM vs DM, risk-on/risk-off)

Macro framework:
- Risk-on: Stocks up, bonds down, dollar down, commodities up
- Risk-off: Stocks down, bonds up, dollar up, commodities down

Provide market regime assessment and tactical asset allocation views."""
            }
        )
    
    async def analyze(self, macro_data: Dict[str, Any]) -> Dict[str, Any]:
        """Perform macro analysis."""
        data_service = DataConnectorService()
        
        # Get current macro data if not provided
        if not macro_data:
            # Fetch from FRED, etc.
            pass
        
        prompt = f"""Macro environment analysis:

Economic data:
- GDP growth: {macro_data.get('gdp_growth', 'N/A')}%
- CPI inflation: {macro_data.get('cpi', 'N/A')}%
- Unemployment: {macro_data.get('unemployment', 'N/A')}%
- Fed funds rate: {macro_data.get('fed_rate', 'N/A')}%

Market data:
- 10Y Treasury yield: {macro_data.get('treasury_10y', 'N/A')}%
- 2s10s spread: {macro_data.get('yield_curve', 'N/A')} (normal/inverted?)
- DXY (dollar): {macro_data.get('dxy', 'N/A')}
- VIX: {macro_data.get('vix', 'N/A')}
- Oil (WTI): ${macro_data.get('oil_price', 'N/A')}
- Gold: ${macro_data.get('gold_price', 'N/A')}

Provide:
1. Market regime (risk-on or risk-off?)
2. Fed policy stance (hawkish/dovish/neutral?)
3. Economic cycle position (early/mid/late/recession?)
4. Tactical asset allocation (overweight/underweight asset classes)
5. Key risks to monitor"""
        
        response = await nvidia_client.chat_completion(
            [{"role": "system", "content": self.system_prompt},
             {"role": "user", "content": prompt}],
            task_type="portfolio"
        )
        
        return {
            "analyst": "Macro",
            "market_regime": self._extract_regime(response),
            "fed_stance": self._extract_fed_view(response),
            "cycle_position": self._extract_cycle_position(response),
            "asset_allocation": self._extract_allocation(response),
            "outlook": response
        }


# Registry of all analyst types
ANALYST_TYPES = {
    "fundamentals": FundamentalsAnalyst,
    "technical": TechnicalAnalyst,
    "sentiment": SentimentAnalyst,
    "macro": MacroAnalyst,
}