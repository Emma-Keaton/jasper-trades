---
name: phase1-websocket-risk-circuit-chat
description: Implement Phase 1 core features: WebSocket real-time data, risk dashboard, circuit breaker, and AI chat assistant for trading platforms
source: auto-skill
extracted_at: '2026-06-02T15:59:07.956Z'
---

# Phase 1 Implementation: Core Reliability & Risk Controls

This skill captures the approach for implementing 4 P0 features for a trading platform: WebSocket real-time data, risk dashboard, circuit breaker, and AI chat assistant.

## Key Architecture Decisions

### 1. WebSocket Real-Time Data

**Pattern:** Publisher-Subscriber with Room-Based Channels

```
Frontend: usePriceStream hook → WebSocketClient → Component state updates
```

**Key Implementation Points:**
- Use rooms for different data types (prices, signals, trades, portfolio, risk)
- Implement exponential backoff reconnection (1s, 2s, 4s, 8s, 16s max)
- Reduce polling frequency from 10s to 30s once WebSocket is connected
- Display connection status indicator in header

**File Structure:**
```
backend/app/api/websocket/streams.py         # ConnectionManager + publishers
frontend/lib/websocket.ts                     # Reusable WS client
frontend/hooks/usePriceStream.ts              # React hook
```

**Common Pitfalls:**
- Don't forget to import `websockets` library in requirements.txt
- WebSocket URLs use `ws://` or `wss://` not `http://`
- Handle JSON parse errors gracefully in onmessage handler
- Clean up disconnected clients to prevent memory leaks

### 2. Risk Dashboard

**Pattern:** API-First with Simplified MVP Calculations

Start with simplified calculations for MVP, then enhance with real historical data:

```python
# MVP: Assumed values
var_95 = portfolio_value * 0.025  # 2.5% of portfolio
sharpe = (0.20 - 0.05) / 0.15     # Assumed returns/volatility

# Production: Historical simulation
var_95 = np.percentile(historical_returns, 5)
sharpe = (mean_return - risk_free_rate) / std_return * sqrt(252)
```

**Endpoints to Create:**
- `GET /api/v1/risk/metrics` - VaR, drawdown, Sharpe, Sortino
- `GET /api/v1/risk/exposure` - Asset allocation, concentrations
- `GET /api/v1/risk/correlations` - Correlation matrix, beta

**UI Components:**
- Color-code metrics (green/yellow/red based on thresholds)
- VaR: Green <3%, Yellow 3-5%, Red >5%
- Drawdown: Green <5%, Yellow 5-10%, Red >10%
- Sharpe: Green >1.5, Yellow 1.0-1.5, Red <1.0

### 3. Circuit Breaker System

**Pattern:** State Machine with Guard Middleware

```python
States: IDLE → WARNING → HALTED

Triggers:
- Flash crash: >5% drop in 5 minutes
- Drawdown: >10% from peak
- Volatility: ATR > 2x average

Actions:
- Check state before every trade execution
- Send WhatsApp alert on state change
- Broadcast to WebSocket clients
```

**Implementation Steps:**

1. Create singleton service with state tracking
2. Add price monitoring with 5-minute sliding window
3. Integrate check into trading endpoint:
```python
circuit = get_circuit_breaker()
if not circuit.can_trade():
    raise HTTPException(423, f"Trading halted: {circuit.trigger_reason}")
```
4. Add API endpoints: `/halt`, `/resume`, `/status`
5. Create UI widget with emergency halt button and 2-step resume confirmation

**Important:** Always log halt events and send WhatsApp notifications for audit trail.

### 4. AI Chat Assistant

**Pattern:** Intent Detection + Context-Aware LLM Responses

```
User Message → Intent Detection → Context Fetch → LLM → Response → WhatsApp
                 ↓
        (status, positions,
         explain_trade, risk,
         help, conversation)
```

**Intent Detection (Regex + Keywords):**
```python
def _detect_intent(text):
    text_lower = text.lower()
    if 'status' in text_lower or 'portfolio' in text_lower:
        return 'status'
    if 'why' in text_lower or 'explain' in text_lower:
        return 'explain_trade'
    # ... etc
```

**LLM Prompt Template:**
```python
prompt = f"""
You are Jasper, an AI trading assistant.

Context:
- Portfolio value: ${value:,.2f}
- Current positions: {positions_json}
- Recent trades: {trades_json}

User message: "{user_message}"

Respond conversationally but concisely (2-4 sentences).
"""
```

**Model Selection:** Use Llama-3.2-3B for chat (fast, cheap ~50ms latency)

**Database Models:**
```python
class ChatMessage(Base):
    phone_number, message, direction, message_type, intent
```

## Integration Checklist

### Backend
- [ ] Register all new routers in `main.py`
- [ ] Add models to `models.py` (ChatMessage, RiskSnapshot)
- [ ] Start market data service in lifespan
- [ ] Stop market data service on shutdown
- [ ] Add `websockets>=12.0` to requirements.txt

### Frontend
- [ ] Create WebSocket client library
- [ ] Create React hooks for real-time data
- [ ] Add components: RiskDashboard, CircuitBreaker, ChatWidget
- [ ] Integrate ChatWidget into main page layout
- [ ] Update connection status indicators

### Testing
- [ ] Backend health endpoint responds
- [ ] WebSocket connects and receives price updates
- [ ] Risk metrics return valid JSON
- [ ] Circuit breaker halts trading when triggered
- [ ] Chat widget sends/receives messages

## Deployment Commands

```bash
# Install dependencies
pip install -r backend/requirements.txt
cd frontend && npm install

# Start with Docker
docker-compose up -d --build

# Test all features
test-phase1.bat  # Windows
bash test-phase1.sh  # Linux/Mac

# Verify endpoints
curl http://localhost:8000/api/v1/health
curl http://localhost:8000/api/v1/system/market-data
curl http://localhost:8000/api/v1/risk/metrics
curl http://localhost:8000/api/v1/circuit-breaker/status
```

## MVP vs Production

| Feature | MVP Approach | Production Enhancement |
|---------|-------------|----------------------|
| VaR | 2.5% assumed | Historical simulation with 252 days |
| Sharpe | Assumed 20% return | Calculate from actual trade PnL |
| Correlations | Identity matrix | Fetch 90-day returns, compute matrix |
| Circuit breaker | In-memory state | Redis-backed for persistence |
| Chat AI | No long-term memory | Vector DB + RAG for conversation history |

The MVP approach is sufficient for testing and validation. Plan enhancements for Phase 2+.