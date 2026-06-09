"""
Self-Learning AI API
Endpoints for experience buffer, pattern analysis, and ML predictions
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Optional
import structlog

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/learning", tags=["self-learning"])

# Import learning services
from app.services.trade_monitor import trade_monitor


class PredictionRequest(BaseModel):
    symbol: str
    action: str  # BUY, SELL
    market_conditions: Dict
    technical_features: Dict


class PredictionResponse(BaseModel):
    symbol: str
    success_probability: float
    confidence: Optional[str]
    recommendation: str
    win_rate: float
    recent_form: str


@router.get("/status")
async def get_learning_status():
    """Get self-learning system status"""
    return trade_monitor.get_learning_status()


@router.post("/predict")
async def predict_trade_success(request: PredictionRequest):
    """Get ML prediction for proposed trade"""
    result = trade_monitor.predict_trade_success(
        request.symbol,
        request.market_conditions,
        request.technical_features
    )
    
    status = trade_monitor.get_learning_status()
    
    return PredictionResponse(
        symbol=request.symbol,
        success_probability=result["success_probability"],
        confidence=result["confidence"],
        recommendation=result["recommendation"],
        win_rate=status["win_rate"],
        recent_form=status["recent_form"]["form"],
    )


@router.get("/patterns/winning")
async def get_winning_patterns():
    """Get extracted patterns from winning trades"""
    patterns = trade_monitor.exp_buffer.get_winning_patterns(min_trades=5)
    return {
        "count": len(patterns.get("all_patterns", [])) if isinstance(patterns, dict) else len(patterns),
        "patterns": patterns,
    }


@router.get("/patterns/losing")
async def get_losing_patterns():
    """Get extracted patterns from losing trades to avoid"""
    patterns = trade_monitor.exp_buffer.get_losing_patterns(min_trades=3)
    return {
        "count": len(patterns),
        "patterns": patterns,
    }


@router.get("/experiences")
async def get_experiences(limit: int = 50, offset: int = 0):
    """Get recent trading experiences"""
    experiences = trade_monitor.exp_buffer.experiences[offset:offset+limit]
    return {
        "total": len(trade_monitor.exp_buffer.experiences),
        "limit": limit,
        "offset": offset,
        "experiences": [
            {
                "trade_id": e.trade_id,
                "symbol": e.symbol,
                "action": e.action,
                "pnl_percent": e.pnl_percent,
                "outcome": e.outcome,
                "timestamp": e.timestamp,
                "lessons": e.lessons,
            }
            for e in experiences
        ]
    }


@router.get("/feature-importance")
async def get_feature_importance():
    """Get ML model feature importance"""
    return trade_monitor.pattern_analyzer.get_feature_importance()


@router.post("/retrain")
async def retrain_model():
    """Force retrain pattern model on all experiences"""
    success = trade_monitor.pattern_analyzer.train_from_experiences(
        trade_monitor.exp_buffer.experiences,
        force=True
    )
    
    if success:
        return {"status": "success", "message": "Model retrained"}
    else:
        raise HTTPException(status_code=400, detail="Training failed - not enough data")


@router.delete("/experiences")
async def clear_experiences():
    """Clear all experiences (use with caution)"""
    trade_monitor.exp_buffer.clear()
    return {"status": "success", "message": "All experiences cleared"}