"""
Structured Debate API - Multi-agent adversarial analysis
Inspired by TradingAgents framework
"""
from fastapi import APIRouter, HTTPException, Body
from typing import List, Optional, Dict, Any
from pydantic import BaseModel
import structlog

from app.services.structured_debate import (
    structured_debate_service,
    DebateRecord,
    AnalystReport,
    ResearcherArgument
)

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/v1/debate", tags=["Structured Debate"])


class DebateRequest(BaseModel):
    """Request to run structured debate"""
    ticker: str
    context: Dict[str, Any] = {}


class DebateSummary(BaseModel):
    """Debate summary response"""
    ticker: str
    date: str
    phase: str
    analyst_count: int
    bull_confidence: float
    bear_confidence: float
    neutral_confidence: float
    final_decision: Optional[Dict]


class AnalystReportResponse(BaseModel):
    """Analyst report response"""
    role: str
    ticker: str
    summary: str
    key_points: List[str]
    confidence: float
    bullish_signals: List[str]
    bearish_signals: List[str]
    neutral_signals: List[str]


class ResearcherArgumentResponse(BaseModel):
    """Researcher argument response"""
    stance: str
    thesis: str
    price_target: Optional[float]
    confidence: float
    catalysts: List[str]
    risks: List[str]


@router.post("/analyze")
async def run_structured_debate(request: DebateRequest) -> Dict[str, Any]:
    """
    Run structured analyst debate for a ticker.
    
    **Process:**
    1. **Specialist Analysts** research fundamentals, technicals, sentiment, news, macro
    2. ** Bull Researcher** builds bullish thesis from analyst reports
    3. **Bear Researcher** builds bearish thesis
    4. **Neutral Researcher** provides balanced perspective
    5. **Final decision** synthesizes all views
    
    **Why structured debate:**
    - Reduces AI hallucination through adversarial analysis
    - Forces consideration of both bullish and bearish cases
    - Tracks historical win rates for learning
    - Generates explainable trading recommendations
    
    Returns complete debate record with all reports and arguments.
    """
    try:
        debate = await structured_debate_service.run_analysis(
            ticker=request.ticker,
            context=request.context
        )
        
        # Format response
        return {
            "ticker": debate.ticker,
            "date": debate.date,
            "phase": debate.phase,
            "analyst_reports": [
                AnalystReportResponse(
                    role=r.role,
                    ticker=r.ticker,
                    summary=r.summary,
                    key_points=r.key_points,
                    confidence=r.confidence,
                    bullish_signals=r.bullish_signals,
                    bearish_signals=r.bearish_signals,
                    neutral_signals=r.neutral_signals
                )
                for r in debate.analysts
            ],
            "bull_case": ResearcherArgumentResponse(
                stance=debate.bull_case.stance,
                thesis=debate.bull_case.thesis,
                price_target=debate.bull_case.price_target,
                confidence=debate.bull_case.confidence,
                catalysts=debate.bull_case.catalysts,
                risks=debate.bull_case.risks
            ) if debate.bull_case else None,
            "bear_case": ResearcherArgumentResponse(
                stance=debate.bear_case.stance,
                thesis=debate.bear_case.thesis,
                price_target=debate.bear_case.price_target,
                confidence=debate.bear_case.confidence,
                catalysts=debate.bear_case.catalysts,
                risks=debate.bear_case.risks
            ) if debate.bear_case else None,
            "neutral_view": ResearcherArgumentResponse(
                stance=debate.neutral_view.stance,
                thesis=debate.neutral_view.thesis,
                price_target=debate.neutral_view.price_target,
                confidence=debate.neutral_view.confidence,
                catalysts=debate.neutral_view.catalysts,
                risks=debate.neutral_view.risks
            ) if debate.neutral_view else None,
            "win_rate_context": debate.win_rate_tracking,
            "summary": DebateSummary(
                ticker=debate.ticker,
                date=debate.date,
                phase=debate.phase,
                analyst_count=len(debate.analysts),
                bull_confidence=debate.bull_case.confidence if debate.bull_case else 0,
                bear_confidence=debate.bear_case.confidence if debate.bear_case else 0,
                neutral_confidence=debate.neutral_view.confidence if debate.neutral_view else 0,
                final_decision=debate.final_decision
            )
        }
    
    except Exception as e:
        logger.error(f"Structured debate failed for {request.ticker}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/outcome/record")
async def record_outcome(
    ticker: str = Body(...),
    decision: str = Body(...),
    entry_price: float = Body(...),
    exit_price: float = Body(...),
    return_pct: float = Body(...),
    alpha_vs_market: float = Body(0.0)
):
    """
    Record realized return for decision log learning.
    
    **Purpose:**
    - Track win/loss outcomes for each decision
    - Generate reflections on what worked/failed
    - Inject lessons into future debate prompts
    - Improve win rate over time
    
    **Example:**
    ```json
    {
      "ticker": "AAPL",
      "decision": "BUY",
      "entry_price": 175.50,
      "exit_price": 190.25,
      "return_pct": 0.084,
      "alpha_vs_market": 0.032
    }
    ```
    
    After recording, the service generates a reflection like:
    > "AAPL BUY resulted in excellent win (+8.40%), outperformed the market 
    > (alpha: +3.20%). Current win rate: 65.2% over 23 trades."
    """
    try:
        structured_debate_service.record_decision_outcome(
            ticker=ticker,
            decision=decision.upper(),
            entry_price=entry_price,
            exit_price=exit_price,
            return_pct=return_pct,
            alpha_vs_market=alpha_vs_market
        )
        
        return {
            "status": "success",
            "message": f"Recorded {ticker} {decision.upper()} outcome: {return_pct:.2%} return"
        }
    
    except Exception as e:
        logger.error(f"Failed to record outcome for {ticker}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/win-rate/{ticker}")
async def get_win_rate(ticker: str) -> Dict[str, Any]:
    """
    Get historical win rate for a ticker.
    
    Returns:
    - Total trades
    - Wins and losses
    - Win rate percentage
    - Average return
    - Last reflection
    """
    stats = structured_debate_service.win_rate_memory.get(ticker)
    
    if not stats:
        return {
            "ticker": ticker,
            "tracked": False,
            "message": "No historical data for this ticker"
        }
    
    return {
        "ticker": ticker,
        "tracked": True,
        "total_trades": stats["total_trades"],
        "wins": stats["wins"],
        "losses": stats["losses"],
        "win_rate": f"{stats['win_rate']:.1%}",
        "avg_return": f"{stats['avg_return']:.2%}",
        "last_reflection": stats.get("last_reflection")
    }


@router.get("/status")
async def get_debate_status():
    """Get structured debate service status"""
    return structured_debate_service.get_status()