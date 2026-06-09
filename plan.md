# Jasper Trades: Superpowered AI Trader - Implementation Plan

## Executive Summary

Jasper Trades merges four powerful open-source AI trading platforms into one unified, white-labeled solution optimized for minimal cost and maximum performance.

**Source Platforms:**
1. **Fincept Terminal** - Institutional-grade desktop analytics, 100+ data connectors, 37 AI agents
2. **AI-Trader (HKUDS)** - Multi-agent collaboration, copy trading, signal sync
3. **Vibe-Trading (HKUDS)** - Natural language research, 452 alpha zoo, 7 backtest engines, persistent memory
4. **AutoHedge** - 4-stage risk-first autonomous trading pipeline

---

## Architecture Overview

### Target Architecture: Hybrid Local-First with Cloud Sync

```
┌─────────────────────────────────────────────────────────────────┐
│ USER'S MACHINE (Local Execution - Zero Latency)                 │
│ ┌───────────────────────────────────────────────────────────┐   │
│ │ Jasper Trades Backend (FastAPI - Python 3.11+)            │   │
│ │ - Agent execution (Director, Quant, Risk, Execution)      │   │
│ │ - Paper trading engine ($100K simulation)                 │   │
│ │ - SQLite database (local, fast)                           │   │
│ │ - Broker adapters (Alpaca, Binance, IBKR, Solana)         │   │
│ └───────────────────────────────────────────────────────────┘   │
│                                                                 │
│ ┌───────────────────────────────────────────────────────────┐   │
│ │ Jasper Trades Frontend (React 19 + Vite - PWA)            │   │
│ │ - Trading dashboard                                       │   │
│ │ - Agent management                                        │   │
│ │ - Copy trading UI                                         │   │
│ │ - Backtest interface                                      │   │
│ └───────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                              │
                              │ (Optional: Sync to cloud for sharing)
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ FREE CLOUD LAYER (PythonAnywhere + Vercel - No CC Required)     │
│ - Signal sharing (for copy trading)                             │
│ - Portfolio backup (GitHub Gists / Google Drive)                │
│ - Multi-device sync                                             │
└─────────────────────────────────────────────────────────────────┘
```

---

## Technology Stack

| Component | Technology | Source | Rationale |
|-----------|-----------|--------|-----------|
| **Backend Framework** | FastAPI (Python 3.11+) | AI-Trader + Vibe | Fast, auto-docs, WebSocket support |
| **Frontend Framework** | React 19 + Vite | Vibe-Trading | Modern, PWA-capable, fast |
| **State Management** | Zustand | Vibe-Trading | Lightweight, simple |
| **Database** | SQLite + DuckDB | Vibe-Trading | File-based, zero server costs |
| **Agent Framework** | LangChain + Custom | Vibe + AutoHedge | Flexible, no paid dependencies |
| **LLM Provider** | NVIDIA NIM API | All 4 platforms | Pay-per-use, multiple models |
| **Charts** | ECharts + Recharts | Vibe + AI-Trader | Free, powerful |
| **Broker APIs** | Alpaca, CCXT, IBKR | Fincept + AI-Trader | Free paper trading + live trading |

---

## NVIDIA NIM Model Strategy

### Model Routing for Optimal Performance/Cost

| Model | Use Case | Latency | Traffic % | Cost/1M tokens |
|-------|----------|---------|-----------|----------------|
| **Llama-3.2-3B-Instruct** | Risk checks, order execution | 50-100ms | 50% | ~$0.15-0.30 |
| **Llama-3.3-70B-Instruct** | News analysis, signal generation | 200-400ms | 35% | ~$0.65-1.00 |
| **Llama-3.1-8B-Instruct** | Copy trading decisions | 100-150ms | 10% | ~$0.20-0.40 |
| **Nemotron-3-Super-120B-A12B** | Portfolio analysis | 500-800ms | 5% | ~$2.00-3.00 |

**Target End-to-End Latency:** 400-600ms (beats 95% of human traders)

**Cost Optimization:**
- Use smaller models (3B, 8B) for 90% of calls
- Reserve 70B+ models for complex decisions only
- Expected cost: $25-150/month for medium usage

---

## Paper Trading Strategy

### Primary: Alpaca Securities
- **Unlimited free paper trading** (stocks, options, crypto)
- Same API for paper + live (just switch endpoint)
- No account minimums
- Perfect for testing AI agents

### Crypto: Binance Testnet + Coinbase Sandbox
- Full order book simulation
- Test crypto strategies risk-free

### Implementation
```python
class PaperTradingService:
    - Simulated $100K portfolio (from AI-Trader)
    - Real-time order execution simulation
    - Slippage modeling
    - Commission modeling
    - Performance tracking & leaderboards
```

---

## Merged Features by Source

### From Fincept Terminal
| Feature | Implementation | Status |
|---------|----------------|--------|
| 100+ data connectors | `services/data_service.py` with free sources | Phase 3 |
| QuantLib suite (18 modules) | Port Python analytics to `services/quant_service.py` | Phase 3 |
| 37 specialized agents | Implement as `agents/specialists/` (Buffett, Graham, etc.) | Phase 3 |
| Node editor (visual workflows) | React Flow library in frontend | Phase 4 |
| Multi-asset analytics | Integrate into `backtest_service.py` | Phase 3 |
| 16 broker integrations | `brokers/` adapters (Zerodha, IBKR, Alpaca, etc.) | Phase 2 |

### From AI-Trader (HKUDS)
| Feature | Implementation | Status |
|---------|----------------|--------|
| Signal sync system | `services/signal_service.py` | Phase 2 |
| Copy trading | `services/copytrade_service.py` | Phase 2 |
| Multi-agent collaboration | `agents/swarm.py` | Phase 2 |
| Paper trading ($100K sim) | SQLite-based simulation | Phase 1 |
| Reward system | SQLite points tracking | Phase 2 |
| Cross-platform signal sync | GitHub Gists API (free) | Phase 2 |

### From Vibe-Trading (HKUDS)
| Feature | Implementation | Status |
|---------|----------------|--------|
| ReAct agent loop | `agents/base.py` | Phase 1 |
| 452 alpha zoo | `api/alpha.py` + factors DB | Phase 3 |
| 7 backtest engines | `services/backtest_service.py` | Phase 3 |
| Persistent memory | SQLite FTS5 + file storage | Phase 1 |
| Shadow Account | Analyze user's trade history | Phase 3 |
| MCP server (22 tools) | Optional: `mcp_server.py` | Phase 4 |
| Self-evolving skills | Skill CRUD in `agents/skills.py` | Phase 4 |

### From AutoHedge
| Feature | Implementation | Status |
|---------|----------------|--------|
| 4-stage agent pipeline | `director → quant → risk → execution` | Phase 1 |
| Risk-first design | `agents/risk.py` pre-checks | Phase 1 |
| Structured JSON trades | Standardized output schema | Phase 1 |
| Solana/DeFi integration | `brokers/solana.py` (Jupiter API) | Phase 2 |
| Enterprise logging | Python logging + SQLite | Phase 1 |

---

## Phased Implementation Plan

### Phase 1: MVP Core (Week 1-2)
**Goal:** Running backend + basic web UI with 1 working agent + 1 broker

#### Backend Setup
- [ ] Initialize FastAPI project structure
- [ ] Create base agent class (from Vibe-Trading + AutoHedge)
- [ ] Implement Director Agent (from AutoHedge)
- [ ] Add Alpaca broker adapter (free paper trading)
- [ ] Set up SQLite database
- [ ] Configure NVIDIA NIM API integration

#### Frontend Setup
- [ ] Initialize React 19 + Vite project
- [ ] Create basic dashboard layout
- [ ] Add API connection utility
- [ ] Build agent status component

#### Integration
- [ ] Connect frontend to backend
- [ ] Test Director Agent → Alpaca paper trading
- [ ] Add basic logging

**Deliverable:** Web dashboard where Director Agent can analyze markets and execute paper trades via Alpaca

---

### Phase 2: Agent Expansion (Week 3-4)
**Goal:** Add Quant Agent, Risk Agent, Execution Agent + more brokers

#### Agent Pipeline
- [ ] Implement Quant Agent (AutoHedge + Fincept QuantLib)
- [ ] Implement Risk Agent (AutoHedge risk-first logic)
- [ ] Implement Execution Agent (AutoHedge + AI-Trader)
- [ ] Connect 4-stage pipeline: Director → Quant → Risk → Execution

#### Broker Expansion
- [ ] Add Binance adapter (via CCXT - free)
- [ ] Add Interactive Brokers adapter
- [ ] Add Solana/Jupiter adapter (for DeFi)

#### Frontend
- [ ] Agent management page (view/start/stop agents)
- [ ] Trade history view
- [ ] Basic portfolio chart
- [ ] Copy trading UI (signal feed)

#### Cloud Deployment
- [ ] Deploy backend to PythonAnywhere (free tier)
- [ ] Deploy frontend to Vercel (free tier)
- [ ] Configure CORS and environment variables

**Deliverable:** Full 4-stage autonomous trading pipeline with multiple broker options + copy trading UI

---

### Phase 3: Advanced Features (Week 5-6)
**Goal:** Copy trading, signals, swarm intelligence, alpha zoo

#### AI-Trader Integration
- [ ] Signal service (`services/signal_service.py`)
- [ ] Copy trading service (follow top performers)
- [ ] Signal feed UI (real-time updates)
- [ ] Reward/points system

#### Vibe-Trading Integration
- [ ] Alpha Zoo browser (452 pre-built alphas)
- [ ] Backtest service (7 engines: A-shares, Crypto, Futures, Options)
- [ ] Persistent memory system (cross-session)
- [ ] Shadow Account (analyze user's actual trading behavior)

#### Fincept Integration
- [ ] Data connectors (yfinance, CCXT, AKShare - free sources)
- [ ] QuantLib analytics modules (port Python components)
- [ ] Specialist agents (Buffett, Graham, Lynch personas)

**Deliverable:** Full-featured platform with copy trading, backtesting, and multi-agent swarms

---

### Phase 4: Polish & Mobile (Week 7-8)
**Goal:** PWA support, mobile optimization, performance tuning

#### PWA Setup
- [ ] Add service worker (Vite PWA plugin)
- [ ] Add manifest.json
- [ ] Offline support for dashboard
- [ ] Mobile-responsive UI

#### Performance Optimization
- [ ] Optimize database queries
- [ ] Add caching layer (Redis or in-memory)
- [ ] WebSocket optimization
- [ ] Model routing optimization (NVIDIA NIM)

#### Documentation
- [ ] User guide
- [ ] API documentation (auto-generated from FastAPI)
- [ ] Deployment guide
- [ ] Contributing guidelines

**Deliverable:** Production-ready, mobile-accessible Jasper Trades platform

---

## Cost Breakdown

| Item | Cost | Notes |
|------|------|-------|
| **Infrastructure** | $0 | Local-first, no cloud required |
| **Domain** | $0 | Use localhost or free subdomain |
| **LLM (NVIDIA NIM)** | $0-50/month | Free tier + pay-per-use (estimated for light usage) |
| **Data** | $0 | yfinance, CCXT, AKShare (free tiers) |
| **Brokers** | $0 | Paper trading free; live trading uses standard fees |
| **Database** | $0 | SQLite + DuckDB (file-based) |
| **Hosting (Optional)** | $0 | PythonAnywhere + Vercel free tiers |
| **Total** | **$0-50/month** | Scales with usage |

---

## Project Structure

```
jasper-trades/
├── backend/                      # FastAPI backend
│   ├── app/
│   │   ├── main.py               # FastAPI entry point
│   │   ├── api/                  # REST + WebSocket endpoints
│   │   │   ├── v1/
│   │   │   │   ├── trading.py    # Trade execution
│   │   │   │   ├── signals.py    # Signal management
│   │   │   │   ├── agents.py     # Agent control
│   │   │   │   ├── portfolio.py  # Portfolio mgmt
│   │   │   │   ├── backtest.py   # Backtest endpoints
│   │   │   │   └── alpha.py      # Alpha zoo endpoints
│   │   │   └── websocket/
│   │   │       ├── streams.py    # Real-time data
│   │   │       └── sync.py       # Cross-device sync
│   │   ├── agents/               # Unified agent framework
│   │   │   ├── base.py           # Base agent class
│   │   │   ├── director.py       # AutoHedge Director Agent
│   │   │   ├── quant.py          # AutoHedge Quant + Fincept QuantLib
│   │   │   ├── risk.py           # AutoHedge Risk + Vibe Risk Committee
│   │   │   ├── execution.py      # AutoHedge Execution + AI-Trader broker sync
│   │   │   ├── swarm.py          # Vibe-Trading swarm engine
│   │   │   └── specialists/      # 37 agents from Fincept
│   │   ├── services/
│   │   │   ├── signal_service.py     # AI-Trader signal sync
│   │   │   ├── copytrade_service.py  # AI-Trader copy trading
│   │   │   ├── backtest_service.py   # Vibe-Trading (7 engines)
│   │   │   ├── risk_service.py       # AutoHedge risk-first logic
│   │   │   ├── data_service.py       # 100+ connectors from Fincept
│   │   │   └── paper_trading_service.py  # Paper trading engine
│   │   ├── brokers/              # Broker adapters
│   │   │   ├── alpaca.py         # Stocks/Options (free paper trading)
│   │   │   ├── binance.py        # Crypto (via CCXT)
│   │   │   ├── coinbase.py       # Crypto (via CCXT)
│   │   │   ├── ibkr.py           # Interactive Brokers
│   │   │   └── solana.py         # AutoHedge Jupiter/DeFi
│   │   ├── models/
│   │   │   ├── db.py             # SQLAlchemy models
│   │   │   └── schemas.py        # Pydantic schemas
│   │   └── utils/
│   │       ├── nvidia_nim.py     # NVIDIA NIM API integration
│   │       └── logger.py         # Enterprise logging
│   ├── requirements.txt
│   └── tests/
│
├── frontend/                     # React 19 + Vite (PWA)
│   ├── src/
│   │   ├── pages/
│   │   │   ├── Dashboard.tsx     # Main trading dashboard
│   │   │   ├── Agents.tsx        # Agent management
│   │   │   ├── Signals.tsx       # Signal feed (AI-Trader)
│   │   │   ├── CopyTrade.tsx     # Copy trading UI
│   │   │   ├── Backtest.tsx      # Backtest interface (Vibe)
│   │   │   ├── AlphaZoo.tsx      # 452 alphas browser (Vibe)
│   │   │   ├── Portfolio.tsx     # Portfolio view
│   │   │   └── Settings.tsx      # API keys, brokers, LLM config
│   │   ├── components/           # Reusable UI components
│   │   ├── stores/               # Zustand state (from Vibe)
│   │   └── utils/                # Helpers
│   ├── package.json
│   └── vite.config.ts
│
├── data/                         # Local data storage (no cloud costs)
│   ├── sqlite/                   # SQLite database files
│   ├── memories/                 # Vibe-Trading persistent memory
│   └── logs/                     # Trading logs
│
├── research/                     # Research & documentation
│   └── free-hosting-research.md
│
├── .env.example
├── docker-compose.yml            # Optional: one-command deploy
├── README.md
└── plan.md                       # This file
```

---

## Hosting Strategy (No Credit Card Required)

### Phase 1: Local-Only Development
- Run everything on your local machine
- Share access via ngrok/Cloudflare Tunnel (free)
- **Cost: $0**

### Phase 2: Free Cloud Deployment
- **Backend:** PythonAnywhere (free tier: 512MB storage, 100 CPU-sec/day)
- **Frontend:** Vercel (free tier: 100GB bandwidth)
- **Database:** SQLite (local to PythonAnywhere)
- **Cost: $0**

### Phase 3: Paid Upgrade (If Needed)
- PythonAnywhere Developer: $5/month
- Or Render Hobby: $7/month
- **Cost: $5-20/month**

---

## Success Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| **End-to-End Latency** | < 600ms | News → Analysis → Signal → Trade |
| **Paper Trading Accuracy** | > 55% win rate | Backtested over 1000 trades |
| **Agent Response Time** | < 500ms | NVIDIA NIM model routing |
| **Uptime** | 99%+ | Local execution + optional cloud sync |
| **Cost per Month** | $0-50 | NVIDIA NIM usage-based |

---

## Next Steps

1. **Create plan.md** ✅ (this document)
2. **Initialize project structure** - Create backend/ and frontend/ folders
3. **Set up FastAPI backend** - Base configuration, SQLite, logging
4. **Implement core agent framework** - Base agent class with NVIDIA NIM integration
5. **Build 4-stage pipeline** - Director → Quant → Risk → Execution
6. **Add Alpaca broker adapter** - Paper trading first
7. **Create React frontend** - Basic dashboard + agent status
8. **Test end-to-end flow** - News → Analysis → Paper Trade

---

## Key Decisions Made

1. **Local-first architecture** - Zero latency, zero hosting cost
2. **NVIDIA NIM for LLM** - Pay-per-use, multiple models, no upfront cost
3. **Alpaca for paper trading** - Free, unlimited, same API for live
4. **PythonAnywhere + Vercel for cloud** - No credit card required
5. **SQLite for database** - File-based, no server needed
6. **PWA for mobile** - No app store fees, works offline
7. **Phased rollout** - MVP first, then advanced features

---

*This plan is optimized for minimal cost ($0-50/month), maximum performance (400-600ms latency), and zero credit card requirement.*
