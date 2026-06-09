---
name: self-learning-ai-trading-system
description: Implement reinforcement learning for AI trading agents using experience buffers and pattern recognition
source: auto-skill
extracted_at: '2026-06-02T09:59:24.386Z'
---

# Self-Learning AI Trading System

## Problem
AI trading agents make decisions but don't learn from past outcomes. Without feedback loops, the same mistakes repeat and winning patterns aren't systematically captured.

## Solution Architecture
Implement a three-component learning system:

1. **Experience Buffer** - Stores closed trade outcomes with market context
2. **Pattern Analyzer** - ML model (Random Forest) trained on historical trades
3. **Trade Monitor** - Auto-captures outcomes and triggers retraining

## Implementation Steps

### Step 1: Create Experience Buffer
```python
# backend/app/services/experience_buffer.py
from dataclasses import dataclass, asdict, field
from typing import List, Dict
from datetime import datetime
import json
from pathlib import Path

@dataclass
class Experience:
    """Single trading experience: state, action, outcome"""
    trade_id: str
    symbol: str
    action: str  # BUY, SELL, HOLD
    entry_price: float
    exit_price: float
    pnl_percent: float
    hold_duration_minutes: int
    market_conditions: Dict  # VIX, trend, volume
    technical_features: Dict  # RSI, MACD, Bollinger
    outcome: str  # WIN, LOSS, BREAKEVEN
    lessons: List[str] = field(default_factory=list)
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())

class ExperienceBuffer:
    def __init__(self, capacity: int = 1000):
        self.capacity = capacity
        self.experiences: List[Experience] = []
        self.db_path = Path("data/experiences.json")
        self.load()
    
    def add(self, experience: Experience):
        if len(self.experiences) >= self.capacity:
            self.experiences.pop(0)
        self.experiences.append(experience)
        self.save()
    
    def get_winning_patterns(self, min_trades: int = 10) -> List[Dict]:
        winners = [e for e in self.experiences 
                   if e.outcome == "WIN" and e.pnl_percent > 2.0]
        # Cluster by RSI zones, VIX levels, etc.
        ...
```

### Step 2: Create Pattern Analyzer
```python
# backend/app/services/pattern_analyzer.py
import numpy as np
from sklearn.ensemble import RandomForestClassifier
import joblib
from pathlib import Path

class PatternAnalyzer:
    def __init__(self):
        self.model_path = Path("data/models/pattern_model.joblib")
        self.model: Optional[RandomForestClassifier] = None
        self.load_model()
    
    def train_from_experiences(self, experiences: List[Experience]) -> bool:
        if len(experiences) < 30:
            return False
        
        X, y = [], []
        for exp in experiences:
            if exp.outcome == "BREAKEVEN":
                continue
            features = [
                exp.market_conditions.get("vix", 20),
                1 if exp.market_conditions.get("trend") == "bullish" else 0,
                exp.technical_features.get("rsi", 50),
                exp.technical_features.get("macd_signal", 0),
                exp.hold_duration_minutes / 60,
            ]
            X.append(features)
            y.append(1 if exp.outcome == "WIN" else 0)
        
        self.model = RandomForestClassifier(
            n_estimators=100,
            max_depth=6,
            class_weight="balanced"
        )
        self.model.fit(X, y)
        self.save_model()
        return True
    
    def predict_success_probability(
        self, 
        market_conditions: Dict, 
        technical_features: Dict
    ) -> Tuple[float, str]:
        if self.model is None:
            return 0.5, None
        
        features = [[
            market_conditions.get("vix", 20),
            1 if market_conditions.get("trend") == "bullish" else 0,
            technical_features.get("rsi", 50),
            technical_features.get("macd_signal", 0),
            4,  # expected hold hours
        ]]
        
        proba = self.model.predict_proba(features)[0][1]
        confidence = "HIGH" if abs(proba - 0.5) > 0.3 else "MEDIUM"
        return float(proba), confidence
```

### Step 3: Create Trade Monitor
```python
# backend/app/services/trade_monitor.py
class TradeMonitor:
    def __init__(self):
        self.exp_buffer = ExperienceBuffer()
        self.pattern_analyzer = PatternAnalyzer()
        self._last_training_size = 0
    
    async def on_trade_closed(self, trade: Trade):
        pnl_percent = (trade.exit_price - trade.entry_price) / trade.entry_price * 100
        outcome = "WIN" if pnl_percent > 1.0 else ("LOSS" if pnl_percent < -1.0 else "BREAKEVEN")
        
        experience = Experience(
            trade_id=trade.id,
            symbol=trade.symbol,
            action=trade.type,
            pnl_percent=pnl_percent,
            market_conditions=trade.metadata.get("market_conditions", {}),
            technical_features=trade.metadata.get("technical_features", {}),
            outcome=outcome,
        )
        
        self.exp_buffer.add(experience)
        
        if len(self.exp_buffer.experiences) - self._last_training_size >= 50:
            self.pattern_analyzer.train_from_experiences(
                self.exp_buffer.experiences
            )
            self._last_training_size = len(self.exp_buffer.experiences)
```

### Step 4: Integrate with Agents
Update agent decision loop to query pattern analyzer:
```python
# backend/app/agents/director.py
async def analyze_opportunity(self, symbol: str) -> TradingSignal:
    market_data = await self.fetch_market_data(symbol)
    
    # Query ML model for success probability
    success_prob, confidence = self.pattern_analyzer.predict_success_probability(
        market_data.market_conditions,
        market_data.technical_features
    )
    
    # Adjust confidence based on learned patterns
    base_confidence = await self.llm_analyze(market_data)
    adjusted_confidence = (base_confidence + success_prob) / 2
    
    if adjusted_confidence > 0.7 and success_prob > 0.55:
        return TradingSignal(confidence=adjusted_confidence)
```

### Step 5: Create API Endpoints
```python
# backend/app/api/v1/learning.py
from fastapi import APIRouter
from app.services.trade_monitor import trade_monitor

router = APIRouter(prefix="/learning")

@router.get("/status")
async def get_learning_status():
    return {
        "total_experiences": len(trade_monitor.exp_buffer.experiences),
        "win_rate": trade_monitor.exp_buffer.win_stats["wins"] / 
                    max(trade_monitor.exp_buffer.win_stats["total"], 1),
        "pattern_model_trained": trade_monitor.pattern_analyzer.model is not None,
    }

@router.post("/predict")
async def predict_trade_success(request: PredictionRequest):
    return trade_monitor.predict_trade_success(
        request.symbol,
        request.market_conditions,
        request.technical_features
    )

@router.get("/patterns/winning")
async def get_winning_patterns():
    return trade_monitor.exp_buffer.get_winning_patterns()
```

### Step 6: Register in Main App
```python
# backend/app/main.py
from app.api.v1 import learning

app.include_router(learning.router, prefix="/api/v1", tags=["self-learning"])
```

## Key Design Decisions

1. **Experience capacity of 1000**: Enough for pattern recognition without memory bloat
2. **Retrain every 50 trades**: Balance between fresh learning and compute cost
3. **Random Forest over Neural Net**: Interpretable feature importance, faster training on small datasets
4. **BREAKEVEN trades excluded**: Focus learning on clear win/loss signals
5. **Per-trade market snapshot**: Captures VIX, trend, volume for context-aware patterns

## Files to Create
```
backend/app/services/experience_buffer.py
backend/app/services/pattern_analyzer.py
backend/app/services/trade_monitor.py
backend/app/api/v1/learning.py
```

## Dependencies
```txt
scikit-learn>=1.5.0
joblib>=1.4.0
```

## Testing Workflow
1. Run backend with learning system
2. Execute 30+ paper trades (simulate wins/losses)
3. Check `GET /api/v1/learning/status` - should show win_rate and trained model
4. Call `POST /api/v1/learning/predict` with current market data
5. Verify agents adjust confidence based on ML predictions

## Common Pitfalls

1. **Not enough training data**: Model needs 30+ trades minimum. Show "collecting data" state until then.

2. **Feature mismatch**: Ensure features used for training match features at prediction time. Use consistent normalization.

3. **Blocking on retraining**: Always retrain in background task to not block trade execution.

4. **Overfitting**: Limit tree depth (max_depth=6) and use class_weight="balanced" for imbalanced win/loss ratios.

5. **Memory leaks**: Clear old experiences beyond capacity. Use file-based persistence for survival across restarts.