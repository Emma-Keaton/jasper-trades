---
name: akshare-china-stock-integration
description: Complete AKShare integration for Chinese A-shares and B-shares trading with paper trading support
source: auto-skill
extracted_at: '2026-06-22T17:15:19.443Z'
---

## AKShare China Stock Integration - Complete Implementation Guide

### Overview
This skill implements full integration with AKShare for trading Chinese stocks (A-shares and B-shares) on Shanghai (SSE) and Shenzhen (SZSE) exchanges. AKShare is a free, open-source Python library that provides access to Chinese market data. Since AKShare is data-only, this implementation uses paper trading mode for simulation.

### Key Components Created

#### 1. Broker Service (`backend/app/brokers/akshare_service.py`)
```python
class AKShareBrokerService(BaseBrokerService):
    - Supports A-shares (CNY): 600xxx, 688xxx (SSE), 000xxx, 300xxx (SZSE)
    - Supports B-shares (USD/HKD): 900xxx (SSE), 200xxx (SZSE)
    - Paper trading with configurable initial capital (default: 1M CNY)
    - Real-time market data via akshare.stock_zh_a_spot_em()
    - Historical data via akshare.stock_zh_a_hist()
    - Automatic position tracking and PnL calculation
```

**Key Methods:**
- `get_market_data(symbol, exchange)` - Real-time quotes
- `get_historical_data(symbol, start_date, end_date, period)` - OHLCV history
- `submit_order(symbol, side, quantity, price, order_type, exchange)` - Paper trading
- `get_positions()` - Current holdings
- `get_account_data()` - Balance and equity

#### 2. API Endpoints (`backend/app/api/v1/akshare.py`)
```
GET  /api/v1/akshare/market-data?symbol=600000&exchange=SSE
GET  /api/v1/akshare/historical?symbol=600000&start_date=2024-01-01&end_date=2024-06-22
GET  /api/v1/akshare/symbols?market=A&exchange=SSE
POST /api/v1/akshare/order?symbol=600000&side=buy&quantity=100&order_type=market
GET  /api/v1/akshare/portfolio
GET  /api/v1/akshare/status
```

#### 3. Settings Endpoints (`backend/app/api/v1/akshare_settings.py`)
```
GET  /api/v1/settings/akshare - Get device config
POST /api/v1/settings/akshare - Save device config
```

#### 4. Frontend Component (`frontend/components/settings/AKShareSettings.tsx`)
React component with:
- Enable/disable toggle
- Paper trading toggle
- Initial capital input (CNY)
- Currency selector (CNY/USD/HKD)
- Live market data test
- Popular stocks reference list

#### 5. Broker Registry Integration (`backend/app/brokers/registry.py`)
```python
# Auto-detect by symbol format
if symbol.isdigit() and len(symbol) == 6:
    if symbol.startswith(("600", "601", "603", "605", "688")):  # SSE
        return broker_registry.get("akshare")
    elif symbol.startswith(("000", "001", "002", "003", "300", "301")):  # SZSE
        return broker_registry.get("akshare")
    elif symbol.startswith(("900",)):  # SSE B-shares
        return broker_registry.get("akshare")
    elif symbol.startswith(("200",)):  # SZSE B-shares
        return broker_registry.get("akshare")
```

#### 6. Database Model Update (`backend/app/models.py`)
```python
class DeviceSettings(Base):
    akshare_config = Column(String, nullable=True)  # JSON string
    # Structure: {"enabled": true, "paper_trading": true, "initial_capital": 1000000, "currency": "CNY"}
```

### Installation Steps

1. **Add to requirements.txt:**
```txt
akshare>=1.14.0
```

2. **Install dependencies:**
```bash
cd backend
pip install -r requirements.txt
```

3. **Register routers in main.py:**
```python
from app.api.v1 import akshare
from app.api.v1 import akshare_settings

app.include_router(akshare.router, prefix="/api/v1", tags=["akshare"])
app.include_router(akshare_settings.router, tags=["akshare-settings"])
```

4. **Import in broker registry:**
```python
from app.brokers.akshare_service import AKShareBrokerService
```

5. **Add to initialize_brokers():**
```python
if config.get("akshare", {}).get("enabled", True):
    akshare = AKShareBrokerService(
        paper_trading=True,
        initial_capital=1000000.0,
        currency="CNY"
    )
    registry.register("akshare", akshare)
```

6. **Add frontend component to SettingsTab.tsx:**
```tsx
import AKShareSettings from './settings/AKShareSettings';

// In JSX:
<div data-tour="akshare-section">
  <AKShareSettings triggerToast={triggerToast} />
</div>
```

### Market Data Examples

**Popular Chinese Stocks:**
- 600000 - Shanghai Pudong Development Bank (SSE)
- 600036 - China Merchants Bank (SSE)
- 000001 - Ping An Bank (SZSE)
- 000002 - China Vanke (SZSE)
- 688981 - SMIC - Semiconductor (SSE STAR)
- 300750 - CATL - Batteries (SZSE)

**Test API call:**
```bash
curl http://localhost:8000/api/v1/akshare/market-data?symbol=600000&exchange=SSE
```

### Important Notes

**AKShare Limitations:**
- Data-only library (no direct trading execution)
- Paper trading mode simulates orders
- For real trading, would need integration with CICC or China Connect brokers
- Chinese documentation (may need translation wrappers)
- Potential IP blocks from Chinese servers when accessing from Nigeria
  - Use proxies if connection issues occur
  - Rate limit requests to avoid bans

**Trading Hours (China Standard Time UTC+8):**
- Morning: 09:30 - 11:30
- Afternoon: 13:00 - 15:00

**Currency Support:**
- A-shares: CNY (Chinese Yuan)
- B-shares Shanghai: USD
- B-shares Shenzhen: HKD

### Verification Checklist

- [ ] `pip install akshare` completes successfully
- [ ] Backend starts without import errors
- [ ] `/api/v1/akshare/status` returns healthy status
- [ ] Market data fetches for 600000 (test symbol)
- [ ] Frontend builds without webpack errors
- [ ] AKShare settings visible in Settings page
- [ ] Paper trading orders execute successfully
- [ ] Portfolio shows Chinese stock positions

### Why This Approach

**Chosen over alternatives because:**
1. **Free and open-source** - No API costs for Nigerian users
2. **Comprehensive coverage** - 100+ data sources for Chinese markets
3. **Python-native** - Easy integration with existing FastAPI backend
4. **Paper trading first** - Safe testing before real capital deployment
5. **Complements Trove** - Trove covers US/NGX, AKShare covers China

**Not suitable for:**
- High-frequency trading (data polling latency)
- Direct execution (need broker partnership for real trades)
- Real-time order book data (only OHLCV supported)