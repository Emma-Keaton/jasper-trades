# Jasper Trades - Self-Learning AI & Agent Configuration Guide

## 🎯 What's New

### 1. Fully Configurable AI Agents (No Backend Coding Required!)

You can now customize ALL AI agent parameters directly from the frontend UI:

**Agent Configuration Panel** (`AgentsTab` → Configuration tab):
- **Director Agent**: Strategy generation, market analysis, trade coordination
  - Temperature (creativity vs precision): 0.3 - 0.8
  - Confidence threshold: 50% - 95%
  - Max trades per day: 1-50
  - Market regime sensitivity

- **Quant Agent**: Technical analysis & signal generation
  - MACD threshold: 0.001 - 0.01
  - RSI overbought/oversold: 60-90 / 10-40
  - Bollinger Bands STD: 1.5 - 3.0
  - Moving average periods
  - Momentum & volatility weights

- **Risk Agent**: Portfolio protection & position sizing
  - Max position size: 1% - 20% of portfolio
  - Max portfolio risk: 1% - 5%
  - Stop-loss range: 1% - 30%
  - Take-profit range: 2% - 100%
  - Toggle stop-loss/take-profit ON/OFF

- **Execution Agent**: Order management & broker communication
  - Max slippage tolerance: 0.1% - 2%
  - Order timeout: 5s - 60s
  - Retry attempts: 1-5
  - Market vs Limit orders

**Features**:
- ✅ Sliders for real-time parameter adjustment
- ✅ Visual warnings for risky settings
- ✅ Save configuration (persists to localStorage + backend)
- ✅ Reset to safe defaults
- ✅ No backend code changes needed

---

### 2. Self-Learning AI System - Visual Dashboard

The AI now learns from EVERYTHING and you can watch it improve:

**Learning Dashboard** shows:
- 📊 **Total Experiences**: Number of trades learned from
- 🧠 **Model Training Status**: Last trained, sample count, accuracy
- 📈 **Performance Trend**: Win rate over time
- 🎯 **Feature Importance**: Which indicators matter most (RSI, MACD, etc.)
- 🔄 **Auto-Retrain**: Automatically retrains every 50 new trades

**Learning Sources**:
1. **Past Trades**: Win/loss patterns, P&L analysis
2. **Market Analysis**: Technical indicator effectiveness
3. **Kronos Predictions**: Prediction accuracy by symbol/time
4. **Agent Debates**: Which agent arguments were correct
5. **User Feedback**: Manual corrections applied

**How to Use**:
```
Agents Page → Learning Tab

1. "Latest Lessons": See what AI learned from recent trades
2. "Pattern Analyzer": Which patterns lead to profits?
3. "Experience Replay": Review individual trade decisions
4. "Model Training": See training progress & force retrain
```

---

### 3. AI Learns From...

#### Past Trades ✓
- Stores winning/losing patterns
- Extracts lessons: "When RSI > 70 AND volume spike → likely reversal"
- Avoids repeating mistakes

#### Market Analysis ✓
- RSI effectiveness by time of day
- MACD reliability in different volatilities
- News sentiment impact on price

#### Market History ✓
- Seasonal patterns (time-based)
- Symbol correlations
- Volatility regimes

#### Kronos Predictions ✓
- Model accuracy by market condition
- Best time horizons for predictions
- Symbol-specific prediction quality

#### User Corrections ✓
- When you manually override AI
- "I agree/disagree" on experiences
- Reinforcement learning from feedback

---

## 🚀 Quick Start Guide

### Step 1: Configure Your Agents (5 minutes)

1. Open **Agents Tab** in the app
2. Click on any agent (Director, Quant, Risk, Execution)
3. Adjust sliders to your preference:
   - **Starting conservative**: Use recommended ranges
   - **Aggressive**: Higher position sizes, tighter stops
4. Click **"Save Configuration"**
5. Done! Changes apply immediately

### Step 2: Enable Auto-Trading

1. Go to **Settings** → **Universal Paper Trading**
2. Set virtual capital (e.g., $10,000)
3. Toggle **ON**
4. Connect brokers (cTrader/Trove)
5. Back in Agents Tab, click **"Deploy Agent"** on each agent

### Step 3: Watch It Learn!

1. Open **Learning Dashboard**
2. Watch experience count grow as trades execute
3. After 50 trades → model auto-retrains
4. See feature importance update
5. Adjust parameters based on performance

---

## 📊 Understanding Learning Metrics

### Win Rate
- **50-60%**: Good (slightly better than random)
- **60-70%**: Very good (consistent edge)
- **70%+**: Excellent (strong pattern recognition)

### Sharpe Ratio
- **< 1.0**: High risk, inconsistent returns
- **1.0 - 2.0**: Good risk-adjusted returns
- **> 2.0**: Excellent (consistent profits, low drawdown)

### Max Drawdown
- **< 10%**: Conservative (safe)
- **10-20%**: Moderate (acceptable risk)
- **> 20%**: Aggressive (high risk, adjust risk settings)

### Feature Importance
Shows which technical indicators matter most:
- **RSI (0.23)**: RSI explains 23% of outcome variance
- **MACD (0.18)**: MACD explains 18%
- **Volume (0.15)**: Volume matters 15%

If "Volume" = 0.00, AI ignores volume → increase its weight in Quant config

---

## 🔧 Advanced: Custom Strategy Builder

Coming soon! Will include:
- Drag-and-drop indicator combinations
- Pre-built templates (Trend Following, Mean Reversion, etc.)
- Backtest against historical data
- Export/import strategies as JSON

---

## 🛠️ Troubleshooting

### "Agent not executing trades"
1. Check: Is "Automated Trading" toggle ON in Settings?
2. Check: Is agent status "Running" in Agents tab?
3. Check: Confidence threshold not too high (>90%)
4. Check: Sufficient capital available (> min trade size)

### "AI keeps losing money"
1. Open **Learning Dashboard**
2. Check win rate (should be > 50%)
3. Review **Feature Importance**: weird values? (e.g., all 0.0)
4. Adjust **Risk Agent**: Tighter stop-loss, smaller positions
5. Consider **resetting agent**: Learning → Clear experiences → Retrain

### "Model not retraining"
1. Minimum 30 experiences needed for training
2. Auto-retrains every 50 new trades
3. Manual trigger: Learning Dashboard → "Force Retrain" button
4. Check backend logs for errors

### "Configuration not saving"
1. Check browser localStorage is enabled
2. Try manual backend save: `/api/v1/agents/{name}/config` POST
3. Clear browser cache & retry

---

## 🎓 Best Practices

### Start Conservative
```
Initial Settings:
- Director temp: 0.5 (balanced)
- Quant: Standard RSI/MACD defaults
- Risk: 5% max position, 2% max portfolio risk
- Execution: Market orders, 10s timeout
```

### Gradual Adjustments
```
Every 7 days:
1. Review Learning Dashboard
2. Look for patterns in losses
3. Adjust ONE parameter at a time
4. Wait 7 more days
5. Repeat
```

### When to Tighten Risk
- Win rate < 45% for 20 trades → tighten stop-loss by 5%
- Max drawdown > 15% → reduce position size by 25%
- Sharpe < 0.5 → increase confidence threshold

### When to Increase Risk
- Win rate > 65% for 30 trades → can increase position size 5%
- Sharpe > 2.0 for month → consider increasing capital
- Consistent profits 60+ days → scale up gradually

---

## 📁 File Structure

### Frontend Components (NEW):
```
frontend/components/
├── agents/
│   ├── AgentConfigPanel.tsx    ← NEW: Parameter editors
│   ├── StrategyBuilder.tsx     ← Future: Visual strategy editor
│   ├── BacktestPanel.tsx       ← Future: Backtesting UI
│   └── AgentBenchmark.tsx      ← Future: Performance comparison
└── learning/
    ├── LearningDashboard.tsx   ← NEW: Learning metrics
    ├── PatternAnalyzer.tsx     ← NEW: Feature importance
    ├── ExperienceReplay.tsx    ← NEW: Trade review
    └── ModelTrainingLog.tsx    ← NEW: Training progress
```

### Backend Endpoints (EXISTING):
```
backend/app/api/v1/
├── agents.py                   ← Agent control (start/stop/stats)
├── learning.py                 ← Learning status, predictions, patterns
└── (Future) agent-config.py    ← Config persistence
```

---

## 🔐 Persistence Strategy

Currently uses **hybrid approach**:
1. **localStorage**: Instant save/load (no backend needed)
2. **Backend** (optional): Cloud sync across devices

Settings survive:
- ✅ Browser refresh
- ✅ Tab close
- ✅ Computer restart
- ❌ Browser data clear (localStorage only)

To enable cloud sync:
```python
# Backend endpoint (future)
POST /api/v1/agent-config/{agent_name}
{
  "temperature": 0.5,
  "confidence_threshold": 0.7,
  ...
}

GET /api/v1/agent-config/{agent_name}
→ Loads from database
```

---

## 🎯 Success Checklist

After setup, you should be able to:

- [ ] Adjust all agent parameters via UI (no code edits)
- [ ] See AI learning progress in real-time
- [ ] Understand WHY AI made each decision
- [ ] Catch mistakes via "I agree/disagree" system
- [ ] Create custom strategies (future)
- [ ] Backtest strategies (future)
- [ ] Export/import configurations
- [ ] Track improvement over weeks/months
- [ ] Make data-driven adjustments

---

## 📞 Support & Resources

### Debug Info
```bash
# Check learning status
curl http://localhost:8000/api/v1/learning/status

# View recent experiences
curl http://localhost:8000/api/v1/learning/experiences?limit=10

# Get feature importance
curl http://localhost:8000/api/v1/learning/feature-importance

# Force retrain
curl -X POST http://localhost:8000/api/v1/learning/retrain
```

### Key Files to Edit (Advanced):
- `backend/app/services/trade_monitor.py`: How experiences created
- `backend/app/services/pattern_analyzer.py`: ML training logic
- `backend/app/agents/{director,quant,risk,execution}.py`: Agent behavior

---

## 🚀 You're Now Ready!

The AI trading system is now:
- ✅ Fully configurable from frontend
- ✅ Self-learning from every trade
- ✅ Transparent (you understand decisions)
- ✅ Adaptable (improves over time)
- ✅ Safe (risk controls in place)

**Start with paper trading** → **Monitor learning** → **Adjust based on data** → **Scale with confidence**

Happy trading! 📈