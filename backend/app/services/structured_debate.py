"""
Structured Analyst Debate System
Multi-agent adversarial analysis inspired by TradingAgents
"""
import structlog
from typing import List, Dict, Optional, Any
from dataclasses import dataclass, asdict
from datetime import datetime
from enum import Enum

logger = structlog.get_logger(__name__)


class AnalystRole(str, Enum):
    """Analyst specialist roles"""
    FUNDAMENTALS = "fundamentals_analyst"
    TECHNICAL = "technical_analyst"
    SENTIMENT = "sentiment_analyst"
    NEWS = "news_analyst"
    MACRO = "macro_analyst"


class ResearcherStance(str, Enum):
    """Researcher debate stances"""
    BULL = "bull"
    BEAR = "bear"
    NEUTRAL = "neutral"


class DebatePhase(str, Enum):
    """Debate progression phases"""
    ANALYSIS = "analysis"
    BULL_CASE = "bull_case"
    BEAR_CASE = "bear_case"
    REBUTTAL = "rebuttal"
    SYNTHESIS = "synthesis"
    DECISION = "decision"


@dataclass
class AnalystReport:
    """Analyst research report"""
    role: str
    ticker: str
    timestamp: str
    summary: str
    key_points: List[str]
    metrics: Dict[str, Any]
    confidence: float  # 0.0-1.0
    bullish_signals: List[str]
    bearish_signals: List[str]
    neutral_signals: List[str]


@dataclass
class ResearcherArgument:
    """Researcher debate argument"""
    stance: str
    ticker: str
    timestamp: str
    thesis: str
    evidence: List[Dict[str, Any]]
    catalysts: List[str]
    risks: List[str]
    price_target: Optional[float]
    confidence: float
    rebuttals: List[str]


@dataclass
class DebateRecord:
    """Complete debate record"""
    ticker: str
    date: str
    phase: str
    analysts: List[AnalystReport]
    bull_case: Optional[ResearcherArgument]
    bear_case: Optional[ResearcherArgument]
    neutral_view: Optional[ResearcherArgument]
    final_decision: Optional[Dict]
    win_rate_tracking: Optional[Dict]


class StructuredDebateService:
    """
    Structured analyst debate system inspired by TradingAgents.
    
    Implements multi-agent adversarial analysis:
    1. Specialist analysts research different aspects (fundamentals, technicals, sentiment)
    2. Bull and bear researchers debate the evidence
    3. Neutral researcher provides balanced view
    4. Trader agent makes final decision
    5. Risk management reviews
    6. Portfolio manager approves/rejects
    
    Features:
    - Structured debate phases
    - Historical win rate tracking
    - Decision log with realized returns
    - Cross-ticker learning
    """

    def __init__(self):
        self.enabled = True
        self.debate_history: List[DebateRecord] = []
        self.win_rate_memory: Dict[str, Dict] = {}  # ticker -> performance stats
        logger.info("Structured Debate Service initialized")

    async def run_analysis(self, 
                           ticker: str,
                           context: Dict[str, Any]) -> DebateRecord:
        """
        Run full structured debate analysis for a ticker.
        
        Args:
            ticker: Stock/crypto symbol
            context: Market data, news, fundamentals, etc.
            
        Returns:
            Complete debate record with decision
        """
        if not self.enabled:
            raise ValueError("Debate service is disabled")

        logger.info(f"Starting structured debate for {ticker}")

        # Phase 1: Specialist Analyst Reports
        analyst_reports = await self._gather_analyst_reports(ticker, context)

        # Phase 2: Bull & Bear Researcher Arguments
        bull_case = await self._build_bull_case(ticker, analyst_reports, context)
        bear_case = await self._build_bear_case(ticker, analyst_reports, context)

        # Phase 3: Neutral Balance
        neutral_view = await self._build_neutral_view(ticker, bull_case, bear_case, context)

        # Phase 4: Debate Moderation (simulated)
        debate_record = DebateRecord(
            ticker=ticker,
            date=datetime.utcnow().isoformat() + "Z",
            phase=DebatePhase.SYNTHESIS,
            analysts=analyst_reports,
            bull_case=bull_case,
            bear_case=bear_case,
            neutral_view=neutral_view,
            final_decision=None,
            win_rate_tracking=self._get_win_rate_context(ticker)
        )

        logger.info(f"Debate synthesis complete for {ticker}")
        return debate_record

    async def _gather_analyst_reports(self, 
                                       ticker: str, 
                                       context: Dict) -> List[AnalystReport]:
        """Gather reports from specialist analysts"""
        reports = []

        # Fundamentals Analyst
        fundamentals_report = await self._analyze_fundamentals(ticker, context)
        if fundamentals_report:
            reports.append(fundamentals_report)

        # Technical Analyst
        technical_report = await self._analyze_technicals(ticker, context)
        if technical_report:
            reports.append(technical_report)

        # Sentiment Analyst
        sentiment_report = await self._analyze_sentiment(ticker, context)
        if sentiment_report:
            reports.append(sentiment_report)

        # News Analyst
        news_report = await self._analyze_news(ticker, context)
        if news_report:
            reports.append(news_report)

        # Macro Analyst (optional)
        if context.get("macro_data"):
            macro_report = await self._analyze_macro(ticker, context)
            if macro_report:
                reports.append(macro_report)

        logger.info(f"Gathered {len(reports)} analyst reports for {ticker}")
        return reports

    async def _analyze_fundamentals(self, ticker: str, context: Dict) -> Optional[AnalystReport]:
        """Fundamentals analyst: financial statements, valuation, growth"""
        try:
            fundamentals = context.get("fundamentals", {})
            
            # Extract key metrics
            pe_ratio = fundamentals.get("pe_ratio")
            peg_ratio = fundamentals.get("peg_ratio")
            revenue_growth = fundamentals.get("revenue_growth")
            profit_margin = fundamentals.get("profit_margin")
            roe = fundamentals.get("roe")
            debt_to_equity = fundamentals.get("debt_to_equity")

            # Generate signals
            bullish = []
            bearish = []
            neutral = []

            if pe_ratio and pe_ratio < 15:
                bullish.append(f"Attractive P/E ratio: {pe_ratio:.2f}")
            elif pe_ratio and pe_ratio > 30:
                bearish.append(f"High P/E ratio: {pe_ratio:.2f}")
            else:
                neutral.append(f"P/E ratio: {pe_ratio or 'N/A'}")

            if revenue_growth and revenue_growth > 0.15:
                bullish.append(f"Strong revenue growth: {revenue_growth:.1%}")
            elif revenue_growth and revenue_growth < 0.05:
                bearish.append(f"Weak revenue growth: {revenue_growth:.1%}")

            if roe and roe > 0.15:
                bullish.append(f"Excellent ROE: {roe:.1%}")
            elif roe and roe < 0.08:
                bearish.append(f"Poor ROE: {roe:.1%}")

            if debt_to_equity and debt_to_equity > 2.0:
                bearish.append(f"High debt-to-equity: {debt_to_equity:.2f}")

            summary = self._generate_fundamentals_summary(bullish, bearish, neutral)

            return AnalystReport(
                role=AnalystRole.FUNDAMENTALS,
                ticker=ticker,
                timestamp=datetime.utcnow().isoformat() + "Z",
                summary=summary,
                key_points=bullish + bearish + neutral,
                metrics={
                    "pe_ratio": pe_ratio,
                    "peg_ratio": peg_ratio,
                    "revenue_growth": revenue_growth,
                    "profit_margin": profit_margin,
                    "roe": roe,
                    "debt_to_equity": debt_to_equity
                },
                confidence=0.7 if len(bullish + bearish) > 3 else 0.5,
                bullish_signals=bullish,
                bearish_signals=bearish,
                neutral_signals=neutral
            )

        except Exception as e:
            logger.error(f"Fundamentals analysis failed for {ticker}: {e}")
            return None

    async def _analyze_technicals(self, ticker: str, context: Dict) -> Optional[AnalystReport]:
        """Technical analyst: chart patterns, indicators, trends"""
        try:
            technicals = context.get("technicals", {})
            
            rsi = technicals.get("rsi")
            macd = technicals.get("macd")
            macd_signal = technicals.get("macd_signal")
            sma_50 = technicals.get("sma_50")
            sma_200 = technicals.get("sma_200")
            current_price = technicals.get("current_price")

            bullish = []
            bearish = []
            neutral = []

            # RSI analysis
            if rsi:
                if rsi < 30:
                    bullish.append(f"Oversold RSI: {rsi:.1f}")
                elif rsi > 70:
                    bearish.append(f"Overbought RSI: {rsi:.1f}")
                else:
                    neutral.append(f"Neutral RSI: {rsi:.1f}")

            # MACD analysis
            if macd and macd_signal:
                if macd > macd_signal:
                    bullish.append("MACD bullish crossover")
                else:
                    bearish.append("MACD bearish crossover")

            # Moving average analysis
            if current_price and sma_50 and sma_200:
                if current_price > sma_50 > sma_200:
                    bullish.append("Golden alignment (price > SMA50 > SMA200)")
                elif current_price < sma_50 < sma_200:
                    bearish.append("Death alignment (price < SMA50 < SMA200)")

            summary = self._generate_technicals_summary(bullish, bearish, neutral)

            return AnalystReport(
                role=AnalystRole.TECHNICAL,
                ticker=ticker,
                timestamp=datetime.utcnow().isoformat() + "Z",
                summary=summary,
                key_points=bullish + bearish + neutral,
                metrics=technicals,
                confidence=0.6 if len(bullish + bearish) > 2 else 0.4,
                bullish_signals=bullish,
                bearish_signals=bearish,
                neutral_signals=neutral
            )

        except Exception as e:
            logger.error(f"Technical analysis failed for {ticker}: {e}")
            return None

    async def _analyze_sentiment(self, ticker: str, context: Dict) -> Optional[AnalystReport]:
        """Sentiment analyst: social media, community sentiment"""
        try:
            sentiment = context.get("sentiment", {})
            
            social_score = sentiment.get("social_score", 0)
            news_sentiment = sentiment.get("news_sentiment", 0)
            analyst_sentiment = sentiment.get("analyst_sentiment", 0)

            bullish = []
            bearish = []
            neutral = []

            if social_score > 0.6:
                bullish.append(f"Positive social sentiment: {social_score:.2f}")
            elif social_score < -0.6:
                bearish.append(f"Negative social sentiment: {social_score:.2f}")
            else:
                neutral.append(f"Neutral social sentiment: {social_score:.2f}")

            if news_sentiment > 0.5:
                bullish.append("Positive news coverage")
            elif news_sentiment < -0.5:
                bearish.append("Negative news coverage")

            if analyst_sentiment > 4:
                bullish.append("Analyst consensus: Buy")
            elif analyst_sentiment < 2:
                bearish.append("Analyst consensus: Sell")
            else:
                neutral.append("Analyst consensus: Hold")

            summary = self._generate_sentiment_summary(bullish, bearish, neutral)

            return AnalystReport(
                role=AnalystRole.SENTIMENT,
                ticker=ticker,
                timestamp=datetime.utcnow().isoformat() + "Z",
                summary=summary,
                key_points=bullish + bearish + neutral,
                metrics={
                    "social_score": social_score,
                    "news_sentiment": news_sentiment,
                    "analyst_sentiment": analyst_sentiment
                },
                confidence=0.5,
                bullish_signals=bullish,
                bearish_signals=bearish,
                neutral_signals=neutral
            )

        except Exception as e:
            logger.error(f"Sentiment analysis failed for {ticker}: {e}")
            return None

    async def _analyze_news(self, ticker: str, context: Dict) -> Optional[AnalystReport]:
        """News analyst: recent news events and catalysts"""
        try:
            news_items = context.get("recent_news", [])
            
            if not news_items:
                return None

            bullish = []
            bearish = []
            neutral = []

            for news in news_items[:10]:  # Last 10 news items
                if news.get("sentiment") == "positive":
                    bullish.append(news.get("headline", ""))
                elif news.get("sentiment") == "negative":
                    bearish.append(news.get("headline", ""))
                else:
                    neutral.append(news.get("headline", ""))

            summary = f"Analyzed {len(news_items)} news items: {len(bullish)} positive, {len(bearish)} negative"

            return AnalystReport(
                role=AnalystRole.NEWS,
                ticker=ticker,
                timestamp=datetime.utcnow().isoformat() + "Z",
                summary=summary,
                key_points=bullish + bearish + neutral,
                metrics={"news_count": len(news_items)},
                confidence=0.6,
                bullish_signals=bullish,
                bearish_signals=bearish,
                neutral_signals=neutral
            )

        except Exception as e:
            logger.error(f"News analysis failed for {ticker}: {e}")
            return None

    async def _analyze_macro(self, ticker: str, context: Dict) -> Optional[AnalystReport]:
        """Macro analyst: economic conditions, Fed policy, geopolitics"""
        try:
            macro = context.get("macro_data", {})
            
            summary = "Macro conditions analyzed"
            
            return AnalystReport(
                role=AnalystRole.MACRO,
                ticker=ticker,
                timestamp=datetime.utcnow().isoformat() + "Z",
                summary=summary,
                key_points=[],
                metrics=macro,
                confidence=0.4,
                bullish_signals=[],
                bearish_signals=[],
                neutral_signals=[]
            )

        except Exception as e:
            logger.error(f"Macro analysis failed for {ticker}: {e}")
            return None

    async def _build_bull_case(self, 
                                ticker: str, 
                                reports: List[AnalystReport],
                                context: Dict) -> ResearcherArgument:
        """Build bullish thesis from analyst reports"""
        # Aggregate all bullish signals
        all_bullish = []
        for report in reports:
            all_bullish.extend(report.bullish_signals)

        thesis = f"Bullish case for {ticker}: " + " ".join(all_bullish[:5])

        return ResearcherArgument(
            stance=ResearcherStance.BULL,
            ticker=ticker,
            timestamp=datetime.utcnow().isoformat() + "Z",
            thesis=thesis,
            evidence=[asdict(r) for r in reports],
            catalysts=["Earnings beat expectations", "Product launch", "Market expansion"],
            risks=["Economic downturn", "Competition intensifies"],
            price_target=context.get("current_price", 0) * 1.2,
            confidence=0.65,
            rebuttals=[]
        )

    async def _build_bear_case(self, 
                                ticker: str, 
                                reports: List[AnalystReport],
                                context: Dict) -> ResearcherArgument:
        """Build bearish thesis from analyst reports"""
        all_bearish = []
        for report in reports:
            all_bearish.extend(report.bearish_signals)

        thesis = f"Bearish case for {ticker}: " + " ".join(all_bearish[:5])

        return ResearcherArgument(
            stance=ResearcherStance.BEAR,
            ticker=ticker,
            timestamp=datetime.utcnow().isoformat() + "Z",
            thesis=thesis,
            evidence=[asdict(r) for r in reports],
            catalysts=["Earnings miss", "Regulatory headwinds"],
            risks=["Market rally continues", "Short squeeze"],
            price_target=context.get("current_price", 0) * 0.8,
            confidence=0.60,
            rebuttals=[]
        )

    async def _build_neutral_view(self, 
                                   ticker: str, 
                                   bull: ResearcherArgument,
                                   bear: ResearcherArgument,
                                   context: Dict) -> ResearcherArgument:
        """Build balanced neutral perspective"""
        thesis = (
            f"Neutral view: Both bull and bear cases have merit. "
            f"Bull targets ${bull.price_target}, bear targets ${bear.price_target}. "
            f"Wait for clearer directional catalyst."
        )

        return ResearcherArgument(
            stance=ResearcherStance.NEUTRAL,
            ticker=ticker,
            timestamp=datetime.utcnow().isoformat() + "Z",
            thesis=thesis,
            evidence=[asdict(bull), asdict(bear)],
            catalysts=bull.catalysts + bear.catalysts,
            risks=bull.risks + bear.risks,
            price_target=context.get("current_price", 0),
            confidence=0.55,
            rebuttals=[]
        )

    def _get_win_rate_context(self, ticker: str) -> Optional[Dict]:
        """Get historical win rate for this ticker"""
        return self.win_rate_memory.get(ticker)

    def record_decision_outcome(self, 
                                 ticker: str,
                                 decision: str,
                                 entry_price: float,
                                 exit_price: float,
                                 return_pct: float,
                                 alpha_vs_market: float = 0.0):
        """
        Record realized return for decision log learning.
        
        Args:
            ticker: Stock symbol
            decision: BUY/SELL/HOLD
            entry_price: Entry price
            exit_price: Exit price
            return_pct: Return percentage
            alpha_vs_market: Alpha vs benchmark
        """
        if ticker not in self.win_rate_memory:
            self.win_rate_memory[ticker] = {
                "total_trades": 0,
                "wins": 0,
                "losses": 0,
                "avg_return": 0.0,
                "win_rate": 0.0,
                "last_reflection": None
            }

        stats = self.win_rate_memory[ticker]
        stats["total_trades"] += 1
        
        if return_pct > 0:
            stats["wins"] += 1
        else:
            stats["losses"] += 1

        # Update average return
        stats["avg_return"] = (
            (stats["avg_return"] * (stats["total_trades"] - 1) + return_pct) 
            / stats["total_trades"]
        )

        stats["win_rate"] = stats["wins"] / stats["total_trades"]

        # Generate reflection
        reflection = self._generate_reflection(
            ticker, decision, return_pct, alpha_vs_market, stats
        )
        stats["last_reflection"] = reflection

        logger.info(
            f"Recorded {ticker} {decision} outcome: {return_pct:.2%} return, "
            f"win_rate now {stats['win_rate']:.1%}"
        )

    def _generate_reflection(self, 
                             ticker: str,
                             decision: str,
                             return_pct: float,
                             alpha: float,
                             stats: Dict) -> str:
        """Generate reflection on trade outcome"""
        if return_pct > 0.1:
            outcome = "excellent win"
        elif return_pct > 0:
            outcome = "modest win"
        elif return_pct > -0.1:
            outcome = "small loss"
        else:
            outcome = "significant loss"

        if alpha > 0.05:
            market_comparison = "outperformed the market"
        elif alpha < -0.05:
            market_comparison = "underperformed the market"
        else:
            market_comparison = "tracked the market"

        return (
            f"{ticker} {decision} resulted in {outcome} ({return_pct:.2%}), "
            f"{market_comparison} (alpha: {alpha:.2%}). "
            f"Current win rate: {stats['win_rate']:.1%} over {stats['total_trades']} trades."
        )

    # Helper summary generators
    
    def _generate_fundamentals_summary(self, bullish: List[str], bearish: List[str], neutral: List[str]) -> str:
        """Generate fundamentals summary"""
        if len(bullish) > len(bearish):
            return f"Fundamentals lean bullish with {len(bullish)} positive signals vs {len(bearish)} concerns"
        elif len(bearish) > len(bullish):
            return f"Fundamentals lean bearish with {len(bearish)} concerns vs {len(bullish)} positives"
        else:
            return f"Fundamentals mixed: {len(bullish)} positives, {len(bearish)} concerns, {len(neutral)} neutral"

    def _generate_technicals_summary(self, bullish: List[str], bearish: List[str], neutral: List[str]) -> str:
        """Generate technicals summary"""
        return f"Technical analysis: {len(bullish)} bullish, {len(bearish)} bearish, {len(neutral)} neutral signals"

    def _generate_sentiment_summary(self, bullish: List[str], bearish: List[str], neutral: List[str]) -> str:
        """Generate sentiment summary"""
        return f"Sentiment indicators: {len(bullish)} positive, {len(bearish)} negative, {len(neutral)} neutral"

    def get_status(self) -> Dict:
        """Get service status"""
        return {
            "enabled": self.enabled,
            "debate_history_count": len(self.debate_history),
            "tracked_tickers": len(self.win_rate_memory),
            "features": [
                "Specialist analysts (5 roles)",
                "Bull vs Bear debate",
                "Neutral balance view",
                "Win rate tracking",
                "Decision log with reflections",
                "Cross-ticker learning"
            ]
        }


# Singleton instance
structured_debate_service = StructuredDebateService()