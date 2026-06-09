# Jasper Trades Backend - Completion Plan

**Current Status:** ~60% Complete  
**Goal:** Production-ready, top-shelf AI trading backend

This plan breaks down remaining work into prioritized phases with specific tasks, estimated effort, and dependencies.

---

## Phase Overview

| Phase | Name | Focus | Effort | Priority |
|-------|------|-------|--------|----------|
| P1 | Broker Integration | Real trading connectivity | High | Critical |
| P2 | Portfolio & Positions | Core trading infrastructure | Medium | Critical |
| P3 | Signals & Copy Trading | Social trading features | Medium | High |
| P4 | Market Data Service | Price feeds & analytics | Medium | High |
| P5 | Background Tasks | Agent automation | Medium | High |
| P6 | Authentication | Security & user management | Low | Medium |
| P7 | Testing | Quality assurance | High | Medium |
| P8 | WebSocket | Real-time updates | Low | Low |
| P9 | Migrations | Database versioning | Low | Low |
| P10 | Backtest Engine | Strategy testing | High | Low |

---

## Phase 1: Broker Integration (Critical)

**Goal:** Real broker connectivity for paper and live trading

### 1.1 Alpaca Integration (Priority: Critical)
**File:** `backend/app/brokers/alpaca_service.py`

**Tasks:**
- [ ] Create `BrokersService` base class with abstract methods
- [ ] Implement Alpaca service with:
  - [ ] Account initialization (paper/live mode)
  - [ ] `submit_order()` - market, limit, stop orders
  - [ ] `cancel_order()` - order cancellation
  - [ ] `get_position()` - current position
  - [ ] `get_account()` - account details
  - [ ] `get_clock()` - market hours
- [ ] Add order type mapping (Jasper → Alpaca)
- [ ] Handle Alpaca-specific order types (trail, bracket)
- [ ] Implement retry logic with exponential backoff
- [ ] Add rate limiting (Alpaca: 200 req/min)

**Dependencies:** `alpaca-py` (already in requirements)

**Estimated Effort:** 4-6 hours

**Testing:**
- Paper trading account required
- Test all order types
- Verify order status updates

---

### 1.2 Binance/CCXT Integration (Priority: High)
**File:** `backend/app/brokers/binance_service.py`

**Tasks:**
- [ ] Create CCXT-based crypto service
- [ ] Implement:
  - [ ] Exchange initialization (sandbox/live)
  - [ ] `submit_order()` - market, limit, stop-market
  - [ ] `cancel_order()` - cancel open orders
  - [ ] `get_position()` - balance for symbol
  - [ ] `get_ticker()` - current price
- [ ] Handle crypto-specific concerns:
  - [ ] Minimum order sizes
  - [ ] Price/quantity precision (decimal places)
  - [ ] 24/7 market (no clock checks)
- [ ] Add rate limiting (CCXT built-in)

**Dependencies:** `ccxt` (already in requirements)

**Estimated Effort:** 3-4 hours

---

### 1.3 Interactive Brokers Integration (Priority: Medium)
**File:** `backend/app/brokers/ibkr_service.py`

**Tasks:**
- [ ] Implement IBKR service using `ib-insync`
- [ ] Requires IBKR Gateway running locally
- [ ] Implement:
  - [ ] Connection management (async)
  - [ ] `submit_order()` - stocks, options, futures
  - [ ] `cancel_order()` - order cancellation
  - [ ] `get_position()` - portfolio positions
  - [ ] `get_account()` - account values
- [ ] Handle IBKR-specific concepts:
  - [ ] Contract objects (Stock, Option, Future)
  - [ ] Order types (MKT, LMT, STP, etc.)
  - [ ] Smart routing

**Dependencies:** `ib-insync`, running IBKR TWS/Gateway

**Estimated Effort:** 6-8 hours

**Note:** Most complex broker due to IBKR's architecture

---

### 1.4 Solana/Jupiter Integration (Priority: Low)
**File:** `backend/app/brokers/solana_service.py`

**Tasks:**
- [ ] Implement Jupiter DEX aggregator client
- [ ] Use `httpx` for API calls
- [ ] Implement:
  - [ ] `get_quote()` - price quote for swap
  - [ ] `swap()` - execute token swap
  - [ ] `get_balance()` - token balance
  - [ ] `get_price()` - current token price
- [ ] Handle Solana-specific concerns:
  - [ ] Slippage tolerance
  - [ ] Priority fees
  - [ ] Transaction signing

**Dependencies:** `httpx`, Solana RPC endpoint

**Estimated Effort:** 4-5 hours

---

### 1.5 Update Execution Agent
**File:** `backend/app/agents/execution.py`

**Tasks:**
- [ ] Import broker services
- [ ] Replace `submit_to_broker()` stubs with actual calls
- [ ] Implement broker selection logic:
  - [ ] Asset class → broker mapping
  - [ ] Smart routing based on fees/liquidity
- [ ] Add order status polling
- [ ] Implement fill handling (update database on execution)

**Estimated Effort:** 3-4 hours

---

### 1.6 Broker Service Registry
**File:** `backend/app/brokers/__init__.py`

**Tasks:**
- [ ] Create broker registry/factory
- [ ] `get_broker(name)` - retrieve broker instance
- [ ] `list_brokers()` - available brokers
- [ ] Configuration-based broker initialization

**Estimated Effort:** 1 hour

---

**Phase 1 Total:** 21-28 hours

---

## Phase 2: Portfolio & Positions (Critical)

**Goal:** Full portfolio management with real-time positions

### 2.1 Portfolio Service
**File:** `backend/app/services/portfolio_service.py`

**Tasks:**
- [ ] Create `PortfolioService` class
- [ ] Implement:
  - [ ] `get_portfolio(portfolio_id)` - get portfolio with positions
  - [ ] `create_portfolio(name, initial_cash, is_paper)` - create new portfolio
  - [ ] `update_cash(portfolio_id, amount)` - add/withdraw cash
  - [ ] `get_total_value(portfolio_id)` - calculate total portfolio value
  - [ ] `get_pnl(portfolio_id)` - calculate PnL (realized + unrealized)
  - [ ] `get_allocation(portfolio_id)` - asset allocation percentages
- [ ] Implement position management:
  - [ ] `add_position()` - add/increase position
  - [ ] `reduce_position()` - decrease/close position
  - [ ] `update_prices()` - update current prices for all positions
  - [ ] `calculate_unrealized_pnl()` - per-position and total

**Estimated Effort:** 6-8 hours

---

### 2.2 Position Valuation Service
**File:** `backend/app/services/valuation_service.py`

**Tasks:**
- [ ] Create `ValuationService` class
- [ ] Implement price fetching:
  - [ ] Stocks: Alpaca API or yfinance
  - [ ] Crypto: CCXT (Binance, Coinbase)
  - [ ] Forex: CCXT or free API
- [ ] Implement:
  - [ ] `get_price(symbol)` - current price for symbol
  - [ ] `get_prices(symbols: list)` - batch price fetch
  - [ ] `update_position_prices(position_id)` - refresh position
  - [ ] Caching layer (in-memory, 1-minute TTL)
- [ ] Add fallback logic (primary → secondary → tertiary source)

**Estimated Effort:** 4-5 hours

---

### 2.3 Update Portfolio API
**File:** `backend/app/api/v1/portfolio.py`

**Tasks:**
- [ ] Import `PortfolioService`, `ValuationService`
- [ ] Implement `get_portfolio()` - real DB query + valuation
- [ ] Implement `get_performance()` - calculate returns for period
- [ ] Add endpoints:
  - [ ] `POST /` - create portfolio
  - [ ] `POST /{id}/cash` - add/withdraw cash
  - [ ] `GET /{id}/allocation` - asset allocation
  - [ ] `GET /{id}/pnl` - PnL breakdown
- [ ] Add portfolio filtering (paper vs live)

**Estimated Effort:** 4-5 hours

---

### 2.4 Update Trading API
**File:** `backend/app/api/v1/trading.py`

**Tasks:**
- [ ] Implement `get_positions()` - query Position model
- [ ] Implement `get_trade_history()` - query Trade model with filters
- [ ] Add endpoints:
  - [ ] `GET /positions/{symbol}` - single position
  - [ ] `DELETE /positions/{symbol}` - close position
  - [ ] `GET /history/{id}` - single trade details

**Estimated Effort:** 2-3 hours

---

**Phase 2 Total:** 16-21 hours

---

## Phase 3: Signals & Copy Trading (High Priority)

**Goal:** Signal generation and copy trading functionality

### 3.1 Signal Service
**File:** `backend/app/services/signal_service.py`

**Tasks:**
- [ ] Create `SignalService` class
- [ ] Implement:
  - [ ] `create_signal(signal)` - save signal to DB
  - [ ] `get_signals(filters)` - query with filters (symbol, agent, date)
  - [ ] `get_signal(id)` - single signal details
  - [ ] `expire_signals()` - mark expired signals
  - [ ] `get_active_signals()` - only non-expired signals
  - [ ] `publish_signal(signal_id, is_public)` - share signal
  - [ ] `delete_signal(signal_id)` - remove signal
- [ ] Implement signal expiration logic (default: 24 hours)
- [ ] Add signal scoring (track performance of historical signals)

**Estimated Effort:** 4-5 hours

---

### 3.2 GitHub Gist Integration (Copy Trading Sync)
**File:** `backend/app/services/signal_sync_service.py`

**Tasks:**
- [ ] Create `SignalSyncService` class
- [ ] Implement GitHub Gist API integration:
  - [ ] `create_gist(signals)` - create new gist with signals
  - [ ] `update_gist(gist_id, signals)` - update existing gist
  - [ ] `get_gist(gist_id)` - fetch signals from gist
  - [ ] `list_gists()` - list user's gists
  - [ ] `delete_gist(gist_id)` - delete gist
- [ ] Implement signal format (JSON structure)
- [ ] Add gist naming convention (`jasper-signals-{portfolio_id}`)
- [ ] Handle GitHub API rate limits (5000/hour authenticated)

**Dependencies:** `httpx`, GITHUB_TOKEN in .env

**Estimated Effort:** 4-5 hours

---

### 3.3 Copy Trading Service
**File:** `backend/app/services/copytrade_service.py`

**Tasks:**
- [ ] Create `CopyTradeService` class
- [ ] Implement:
  - [ ] `follow_trader(trader_id)` - start following a trader
  - [ ] `unfollow_trader(trader_id)` - stop following
  - [ ] `get_following(user_id)` - list followed traders
  - [ ] `sync_signals()` - fetch and process signals from followed traders
  - [ ] `execute_copy(signal)` - replicate signal in user's portfolio
  - [ ] `get_copy_trades()` - history of copied trades
- [ ] Implement position sizing:
  - [ ] Proportional to user's portfolio
  - [ ] Respect user's risk limits
  - [ ] Configurable copy percentage
- [ ] Add latency handling (async signal processing)

**Estimated Effort:** 6-8 hours

---

### 3.4 Update Signals API
**File:** `backend/app/api/v1/signals.py`

**Tasks:**
- [ ] Import `SignalService`, `SignalSyncService`, `CopyTradeService`
- [ ] Implement all endpoints:
  - [ ] `list_signals()` - with filtering
  - [ ] `get_signal(id)` - single signal
  - [ ] `copy_signal(id)` - copy a signal
  - [ ] `POST /publish/{id}` - publish signal to GitHub
  - [ ] `GET /sync` - sync signals from followed traders
  - [ ] `GET /following` - list followed traders
  - [ ] `POST /following/{trader_id}` - follow trader
  - [ ] `DELETE /following/{trader_id}` - unfollow trader

**Estimated Effort:** 4-5 hours

---

### 3.5 Trader Performance Tracking
**File:** `backend/app/services/trader_stats_service.py`

**Tasks:**
- [ ] Create `TraderStatsService` class
- [ ] Implement:
  - [ ] `calculate_win_rate(agent_name)` - win rate over last N signals
  - [ ] `calculate_total_return(agent_name)` - total return from signals
  - [ ] `calculate_sharpe(agent_name)` - risk-adjusted returns
  - [ ] `get_leaderboard(period, limit)` - top performing traders
  - [ ] `get_trader_profile(agent_name)` - trader stats + history
- [ ] Add signal performance tracking:
  - [ ] Track outcome of each signal (win/loss/neutral)
  - [ ] Calculate PnL from signal execution
  - [ ] Update Agent model stats

**Estimated Effort:** 4-5 hours

---

**Phase 3 Total:** 22-28 hours

---

## Phase 4: Market Data Service (High Priority)

**Goal:** Unified market data access with multiple providers

### 4.1 Market Data Service
**File:** `backend/app/services/market_data_service.py`

**Tasks:**
- [ ] Create `MarketDataService` class
- [ ] Implement data sources:
  - [ ] **Stocks:** Alpaca (free unlimited), yfinance (fallback)
  - [ ] **Crypto:** CCXT (Binance, Coinbase), CoinGecko API (free)
  - [ ] **Forex:** CCXT, Alpha Vantage (free tier)
- [ ] Implement:
  - [ ] `get_quote(symbol)` - current bid/ask/last
  - [ ] `get_ohlcv(symbol, timeframe, limit)` - candlestick data
  - [ ] `get_history(symbol, start_date, end_date)` - historical data
  - [ ] `get_daily_bars(symbols, date)` - batch historical bars
- [ ] Add data normalization (standardize across providers)
- [ ] Implement caching:
  - [ ] In-memory LRU cache (1000 symbols)
  - [ ] DuckDB for historical data storage
  - [ ] Cache TTL: 1 minute for quotes, permanent for historical

**Estimated Effort:** 8-10 hours

---

### 4.2 Data Connectors (Fincept Integration)
**File:** `backend/app/services/data_connectors/`

**Tasks:**
- [ ] Create connector interface
- [ ] Implement connectors:
  - [ ] `yfinance_connector.py` - Yahoo Finance
  - [ ] `alpaca_data_connector.py` - Alpaca Market Data
  - [ ] `akshare_connector.py` - AKShare (China A-shares, free)
  - [ ] `coingecko_connector.py` - CoinGecko (crypto)
- [ ] Add connector registry
- [ ] Automatic failover (try primary → secondary → tertiary)

**Estimated Effort:** 6-8 hours

---

**Phase 4 Total:** 14-18 hours

---

## Phase 5: Background Tasks (High Priority)

**Goal:** Autonomous agent execution and scheduled tasks

### 5.1 Task Scheduler
**File:** `backend/app/services/scheduler.py`

**Tasks:**
- [ ] Use `apscheduler` or `asyncio` tasks
- [ ] Implement scheduled tasks:
  - [ ] **Every 1 minute:** Update position prices
  - [ ] **Every 5 minutes:** Agent signal generation
  - [ ] **Every hour:** Signal expiration check
  - [ ] **Daily (market close):** PnL calculation, daily report
  - [ ] **Daily (end of day):** Cleanup old data
- [ ] Add task management:
  - [ ] Start/stop tasks
  - [ ] Task status monitoring
  - [ ] Error handling and retry
- [ ] Implement graceful shutdown

**Estimated Effort:** 4-5 hours

---

### 5.2 Agent Orchestration
**File:** `backend/app/services/agent_orchestrator.py`

**Tasks:**
- [ ] Create `AgentOrestratorService` class
- [ ] Implement agent pipeline:
  - [ ] **Step 1:** Director analyzes market → generates thesis
  - [ ] **Step 2:** Quant analyzes thesis → generates signal
  - [ ] **Step 3:** Risk assesses signal → approves/rejects
  - [ ] **Step 4:** Execution creates order → submits to broker
- [ ] Implement async pipeline execution
- [ ] Add inter-agent communication (message queue)
- [ ] Handle pipeline failures (partial execution recovery)
- [ ] Add execution modes:
  - [ ] **Autonomous:** Continuous execution
  - [ ] **Semi-auto:** Require user approval for trades
  - [ ] **Manual:** Generate signals only

**Estimated Effort:** 6-8 hours

---

### 5.3 Update Main App
**File:** `backend/app/main.py`

**Tasks:**
- [ ] Import and initialize scheduler
- [ ] Start background tasks on app startup
- [ ] Add shutdown handlers
- [ ] Add task status endpoint: `GET /api/v1/system/tasks`

**Estimated Effort:** 1-2 hours

---

**Phase 5 Total:** 11-15 hours

---

## Phase 6: Authentication (Medium Priority)

**Goal:** Secure API with authentication and authorization

### 6.1 Authentication Service
**File:** `backend/app/services/auth_service.py`

**Tasks:**
- [ ] Implement JWT token generation
- [ ] Use `python-jose` for JWT
- [ ] Implement:
  - [ ] `create_access_token(user_id)` - generate JWT
  - [ ] `verify_access_token(token)` - validate JWT
  - [ ] `hash_password(password)` - bcrypt hashing
  - [ ] `verify_password(password, hash)` - password verification
- [ ] Add token expiration (default: 24 hours)
- [ ] Add refresh token support (optional)

**Estimated Effort:** 3-4 hours

---

### 6.2 User Model
**File:** `backend/app/models.py` (add User model)

**Tasks:**
- [ ] Add `User` model:
  ```python
  class User(Base):
      id = Column(Integer, primary_key=True)
      username = Column(String, unique=True, nullable=False)
      email = Column(String, unique=True)
      hashed_password = Column(String, nullable=False)
      is_active = Column(Boolean, default=True)
      created_at = Column(DateTime, default=datetime.utcnow)
  ```
- [ ] Add `APIKey` model for API key-based auth (for servers):
  ```python
  class APIKey(Base):
      id = Column(Integer, primary_key=True)
      key = Column(String, unique=True, nullable=False)
      name = Column(String)
      is_active = Column(Boolean, default=True)
      created_at = Column(DateTime, default=datetime.utcnow)
  ```

**Estimated Effort:** 1 hour

---

### 6.3 Auth Middleware
**File:** `backend/app/middleware/auth.py`

**Tasks:**
- [ ] Create FastAPI dependency `get_current_user()`
- [ ] Add Bearer token authentication
- [ ] Add API key authentication (header: `X-API-Key`)
- [ ] Protect sensitive endpoints:
  - [ ] `/api/v1/trading/execute`
  - [ ] `/api/v1/portfolio/*`
  - [ ] `/api/v1/agents/{name}/start`
- [ ] Allow public access to:
  - [ ] `/api/v1/health`
  - [ ] `/api/v1/status`
  - [ ] `/api/v1/agents` (read-only)

**Estimated Effort:** 3-4 hours

---

### 6.4 Auth Endpoints (Optional)
**File:** `backend/app/api/v1/auth.py`

**Tasks:**
- [ ] Create auth router
- [ ] Implement:
  - [ ] `POST /login` - username/password → JWT token
  - [ ] `POST /register` - create new user
  - [ ] `POST /refresh` - refresh access token
  - [ ] `POST /logout` - invalidate token (optional)

**Estimated Effort:** 2-3 hours

**Note:** Can skip for single-user/paper trading setup

---

**Phase 6 Total:** 9-12 hours

---

## Phase 7: Testing (Medium Priority)

**Goal:** Comprehensive test coverage

### 7.1 Test Setup
**Directory:** `backend/tests/`

**Tasks:**
- [ ] Create `conftest.py` with fixtures:
  - [ ] `test_db` - test database session
  - [ ] `test_client` - FastAPI test client
  - [ ] `sample_user` - test user fixture
  - [ ] `sample_portfolio` - test portfolio fixture
- [ ] Configure `pytest.ini`:
  - [ ] Test discovery
  - [ ] Async test support
  - [ ] Coverage settings

**Estimated Effort:** 2-3 hours

---

### 7.2 Unit Tests
**Files:** `backend/tests/unit/`

**Tasks:**
- [ ] `test_agents.py` - test agent logic
  - [ ] DirectorAgent analysis
  - [ ] QuantAgent signal generation
  - [ ] RiskAgent position sizing
- [ ] `test_services.py` - test services
  - [ ] PortfolioService calculations
  - [ ] ValuationService price fetching
  - [ ] SignalService CRUD operations
- [ ] `test_models.py` - test database models
  - [ ] CRUD operations
  - [ ] Relationships
  - [ ] Validation

**Estimated Effort:** 8-10 hours

---

### 7.3 Integration Tests
**Files:** `backend/tests/integration/`

**Tasks:**
- [ ] `test_trading.py` - trade execution flow
  - [ ] End-to-end trade execution
  - [ ] Broker integration (mock)
  - [ ] Position updates
- [ ] `test_signals.py` - signal lifecycle
  - [ ] Signal generation
  - [ ] Signal expiration
  - [ ] Copy trading sync
- [ ] `test_api.py` - API endpoint tests
  - [ ] All endpoints respond correctly
  - [ ] Error handling
  - [ ] Authentication

**Estimated Effort:** 6-8 hours

---

### 7.4 Broker Tests
**Files:** `backend/tests/brokers/`

**Tasks:**
- [ ] `test_alpaca.py` - Alpaca integration (paper account)
  - [ ] Submit order (paper trading)
  - [ ] Cancel order
  - [ ] Get position
- [ ] `test_binance.py` - Binance integration (sandbox)
- [ ] Use mocks for expensive/slow operations

**Estimated Effort:** 4-5 hours

---

**Phase 7 Total:** 20-26 hours

---

## Phase 8: WebSocket (Low Priority)

**Goal:** Real-time updates for frontend

### 8.1 WebSocket Endpoint
**File:** `backend/app/api/websocket/streams.py`

**Tasks:**
- [ ] Create WebSocket router
- [ ] Implement:
  - [ ] `WS /api/ws/market-data` - real-time prices
  - [ ] `WS /api/ws/signals` - new signal notifications
  - [ ] `WS /api/ws/trades` - trade execution updates
  - [ ] `WS /api/ws/portfolio` - portfolio value updates
- [ ] Connection management:
  - [ ] Track active connections
  - [ ] Subscribe/unsubscribe to topics
  - [ ] Heartbeat/ping-pong

**Estimated Effort:** 4-5 hours

---

### 8.2 WebSocket Manager
**File:** `backend/app/services/websocket_manager.py`

**Tasks:**
- [ ] Create `WebSocketManager` class
- [ ] Implement:
  - [ ] `connect(websocket)` - add connection
  - [ ] `disconnect(websocket)` - remove connection
  - [ ] `send_message(websocket, message)` - send to specific connection
  - [ ] `broadcast(message)` - send to all connections
  - [ ] `broadcast_topic(topic, message)` - send to topic subscribers
- [ ] Integrate with background tasks for real-time pushes

**Estimated Effort:** 3-4 hours

---

**Phase 8 Total:** 7-9 hours

---

## Phase 9: Migrations (Low Priority)

**Goal:** Database versioning with Alembic

### 9.1 Alembic Setup
**Directory:** `backend/alembic/`

**Tasks:**
- [ ] Initialize Alembic:
  ```bash
  alembic init alembic
  ```
- [ ] Configure `alembic.ini`:
  - [ ] Database URL from .env
  - [ ] Script location
- [ ] Update `alembic/env.py`:
  - [ ] Import all models
  - [ ] Set target_metadata from models.Base.metadata

**Estimated Effort:** 1-2 hours

---

### 9.2 Initial Migration
**Tasks:**
- [ ] Generate initial migration:
  ```bash
  alembic revision --autogenerate -m "Initial migration"
  ```
- [ ] Review and apply migration:
  ```bash
  alembic upgrade head
  ```
- [ ] Create migration workflow documentation

**Estimated Effort:** 1 hour

---

**Phase 9 Total:** 2-3 hours

---

## Phase 10: Backtest Engine (Future Enhancement)

**Goal:** Strategy backtesting with 7 engines (from Vibe-Trading)

**Note:** This is a major feature. Defer until core trading is stable.

### 10.1 Backtest Service
**File:** `backend/app/services/backtest_service.py`

**Tasks:**
- [ ] Create base backtester class
- [ ] Implement engines:
  - [ ] Event-driven backtester
  - [ ] Vectorized backtester
  - [ ] Multi-factor backtester
  - [ ] Options backtester
  - [ ] Crypto backtester
  - [ ] Futures backtester
  - [ ] A-shares backtester
- [ ] Implement metrics calculation
- [ ] Add trade simulation logic

**Estimated Effort:** 20-30 hours (major undertaking)

---

## Summary & Recommendations

### Critical Path (Phases 1-3)
**Total Effort:** 59-77 hours  
**Timeline:** 2-3 weeks full-time, 4-6 weeks part-time

**Priority Order:**
1. **Phase 1:** Broker Integration (Alpaca first for paper trading)
2. **Phase 2:** Portfolio & Positions (core functionality)
3. **Phase 3:** Signals & Copy Trading (differentiating feature)

### Quick Wins (Do These First)
1. **Alpaca paper trading integration** (4-6 hours) - immediate trading capability
2. **Portfolio service + valuation** (6-8 hours) - real portfolio data
3. **Signal service** (4-5 hours) - AI signals working

### Full Backend Completion
**Total All Phases:** ~130-170 hours  
**Timeline:** 4-6 weeks full-time, 8-12 weeks part-time

### Skipping/Moving to "Nice to Have"
- **Phase 6 (Auth):** Skip if single-user/paper trading
- **Phase 8 (WebSocket):** Use polling for MVP
- **Phase 9 (Migrations):** Can defer until production
- **Phase 10 (Backtest):** Major feature, defer until stable

### Recommended Next Steps

1. **Create `backend/app/brokers/` directory**
2. **Implement `alpaca_service.py` first** (quickest path to working trades)
3. **Update `execution.py`** to use real Alpaca service
4. **Implement `portfolio_service.py`** and `valuation_service.py`
5. **Update portfolio API** with real data
6. **Test end-to-end trade flow** with paper trading

This gives you a **minimum viable trading system** in ~20 hours of focused work.

---

## File Structure (After Completion)

```
backend/
├── app/
│   ├── main.py ✓
│   ├── config.py ✓
│   ├── database.py ✓
│   ├── models.py ✓
│   ├── nvidia_nim.py ✓
│   ├── agents/ ✓
│   │   ├── base.py ✓
│   │   ├── director.py ✓
│   │   ├── quant.py ✓
│   │   ├── risk.py ✓
│   │   └── execution.py (needs broker updates)
│   ├── api/v1/
│   │   ├── health.py ✓
│   │   ├── agents.py ✓
│   │   ├── trading.py (needs position/signal impl)
│   │   ├── portfolio.py (needs service impl)
│   │   ├── signals.py (needs service impl)
│   │   └── auth.py (Phase 6)
│   ├── api/websocket/ (Phase 8)
│   ├── brokers/ (NEW - Phase 1)
│   │   ├── __init__.py
│   │   ├── base.py
│   │   ├── alpaca_service.py
│   │   ├── binance_service.py
│   │   ├── ibkr_service.py
│   │   └── solana_service.py
│   ├── services/ (NEW - Phase 2-5)
│   │   ├── portfolio_service.py
│   │   ├── valuation_service.py
│   │   ├── signal_service.py
│   │   ├── signal_sync_service.py
│   │   ├── copytrade_service.py
│   │   ├── trader_stats_service.py
│   │   ├── market_data_service.py
│   │   ├── scheduler.py
│   │   ├── agent_orchestrator.py
│   │   ├── auth_service.py (Phase 6)
│   │   └── websocket_manager.py (Phase 8)
│   ├── middleware/ (NEW - Phase 6)
│   │   └── auth.py
│   └── data_connectors/ (NEW - Phase 4)
│       ├── base.py
│       ├── alpaca_data.py
│       ├── yfinance_data.py
│       ├── akshare_data.py
│       └── coingecko_data.py
├── alembic/ (Phase 9)
├── tests/ (NEW - Phase 7)
│   ├── conftest.py
│   ├── unit/
│   ├── integration/
│   └── brokers/
└── requirements.txt (add: apscheduler, python-jose, passlib)
```

---

## Success Criteria

### MVP (Phases 1-3 Complete)
- ✅ Can execute paper trades via Alpaca
- ✅ Real portfolio tracking with live positions
- ✅ AI agents generating signals autonomously
- ✅ Signal feed viewable and copyable
- ✅ Copy trading working via GitHub Gists

### Production Ready (All Phases Complete)
- ✅ Multiple broker support (stocks, crypto, DeFi)
- ✅ Full portfolio analytics
- ✅ Real-time WebSocket updates
- ✅ User authentication
- ✅ Comprehensive test coverage
- ✅ Database migrations
- ✅ Autonomous AI trading pipeline

---

**Status:** Ready to begin implementation. Start with Phase 1.1 (Alpaca Service).