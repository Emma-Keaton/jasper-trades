---
name: polymarket-prediction-market-integration
description: Integrate Polymarket prediction markets using official SDK without API key
source: auto-skill
extracted_at: '2026-06-05T10:35:00.000Z'
---

# Polymarket Prediction Market Integration

## Overview

Polymarket is a prediction market platform where users trade on real-world events (politics, crypto, sports, economics). The official `polymarket-client` SDK provides access to public market data **without requiring an API key**.

## Installation

```bash
pip install polymarket-client
```

## Service Architecture

### 1. Service Initialization

```python
# backend/app/services/polymarket_service.py
from polymarket import AsyncPublicClient

class PolymarketService:
    def __init__(self):
        self.enabled = True
        self._client = AsyncPublicClient()  # Public client - no credentials
        self.cache = {}
        self.orderbook_cache = {}
```

### 2. Market Data Sources

**Gamma API** (via SDK):
- Market metadata (slug, question, outcomes)
- Volume, liquidity, status
- Token IDs for outcomes

**CLOB API** (via SDK):
- Orderbook data (bids/asks)
- Real-time pricing
- Best bid/ask/mid prices

### 3. Core Methods

#### Search Markets
```python
async def search_markets(self, query: str, limit: int = 20):
    """Search for markets by keyword"""
    client = await self._get_client()
    
    # For crypto queries, use list_markets ordered by volume
    if query.lower() in ['btc', 'bitcoin', 'crypto']:
        markets_response = client.list_markets(
            page_size=limit,
            closed=False,
            order="-volume"
        )
        markets_data = await markets_response.first_page()
        return [self._parse_market(m) for m in markets_data.items]
    
    # For general queries, use search
    search_results = client.search(q=query, page_size=limit)
    search_data = await search_results.first_page()
    
    markets = []
    for item in search_data.items:
        if hasattr(item, 'events'):
            for event in item.events:
                if hasattr(event, 'id'):
                    market_data = await client.get_market(event.id)
                    markets.append(self._parse_market(market_data))
    
    return markets
```

#### Get Market by Slug
```python
async def get_market_by_slug(self, slug: str):
    """Get specific market data"""
    markets_response = client.list_markets(slug=slug, page_size=1)
    markets_data = await markets_response.first_page()
    
    if markets_data.items:
        return self._parse_market(markets_data.items[0])
    return None
```

#### Get Orderbook & Pricing
```python
async def get_orderbook(self, token_id: str):
    """Get CLOB orderbook for outcome token"""
    orderbook_data = await client.get_order_book(token_id)
    
    bids = [{"price": float(b["price"]), "size": float(b["size"])} 
            for b in orderbook_data.bids[:10]]
    asks = [{"price": float(a["price"]), "size": float(a["size"])} 
            for a in orderbook_data.asks[:10]]
    
    best_bid = max(b["price"] for b in bids) if bids else 0.0
    best_ask = min(a["price"] for a in asks) if asks else 0.0
    mid_price = (best_bid + best_ask) / 2
    
    return {
        "token_id": token_id,
        "best_bid": best_bid,
        "best_ask": best_ask,
        "mid_price": mid_price,
        "spread": best_ask - best_bid
    }

async def analyze_market(self, slug: str):
    """Analyze for trading opportunities"""
    market = await self.get_market_by_slug(slug)
    
    # Get prices for all outcomes
    prices = {}
    for token_id in market.clob_token_ids:
        price = await self.get_outcome_price(token_id)
        if price:
            prices[token_id] = price
    
    # Check for arbitrage (sum should be ~1.0)
    total_implied = sum(prices.values())
    
    if total_implied < 0.90:
        return {"recommendation": "Arbitrage opportunity", "confidence": 0.5}
    elif total_implied > 1.10:
        return {"recommendation": "Market overpriced", "confidence": 0.5}
    else:
        best_outcome = min(prices, key=prices.get)
        return {"recommendation": f"Best value: {best_outcome}", "confidence": 0.3}
```

### 4. API Endpoints

```python
# backend/app/api/v1/polymarket.py
from fastapi import APIRouter

router = APIRouter(prefix="/api/v1/polymarket", tags=["Polymarket"])

@router.get("/search")
async def search_markets(query: str, limit: int = 20):
    return await polymarket_service.search_markets(query, limit)

@router.get("/market/{slug:path}")
async def get_market(slug: str):
    return await polymarket_service.get_market_by_slug(slug)

@router.get("/orderbook/{token_id}")
async def get_orderbook(token_id: str):
    return await polymarket_service.get_orderbook(token_id)

@router.get("/price/{token_id}")
async def get_price(token_id: str):
    return await polymarket_service.get_outcome_price(token_id)

@router.get("/analyze/{slug:path}")
async def analyze_market(slug: str):
    return await polymarket_service.analyze_market(slug)

@router.get("/trending")
async def get_trending(limit: int = 10):
    return await polymarket_service.get_trending_markets(limit)

@router.get("/category/{category}")
async def get_by_category(category: str, limit: int = 20):
    return await polymarket_service.get_markets_by_category(category, limit)
```

### 5. Response Formats

**Market Response:**
```json
{
  "market_id": "12345",
  "question": "Will BTC be above $120k on June 30?",
  "slug": "will-btc-be-above-120k-on-june-30",
  "outcomes": ["Yes", "No"],
  "clob_token_ids": ["token_yes_123", "token_no_456"],
  "volume": 125000.00,
  "liquidity": 50000.00,
  "status": "open"
}
```

**Analysis Response:**
```json
{
  "market_id": "12345",
  "question": "Will BTC be above $120k on June 30?",
  "prices": {
    "token_yes_123": 0.65,
    "token_no_456": 0.35
  },
  "total_implied_probability": 1.00,
  "arbitrage_detected": false,
  "recommendation": "Best value: Yes @ 65.0%",
  "confidence": 0.3
}
```

## Integration Patterns

### AI Agent Integration
```python
# AI chat asks about Polymarket events
market_analysis = await polymarket_service.analyze_market("will-btc-hit-100k")
ai_response = f"Polymarket gives {market_analysis['prices']} probability"
```

### Frontend Usage
```typescript
// React component
const { data: markets } = useSWR('/api/v1/polymarket/trending?limit=5');
markets.map(m => (
  <MarketCard 
    key={m.market_id}
    question={m.question}
    probability={m.price}
  />
));
```

## Important Notes

1. **No API Key Required**: SDK uses public endpoints only
2. **Rate Limits**: Respect Polymarket's API rate limits (SDK handles retries)
3. **Cache Strategy**: Implement 5-minute TTL for market data
4. **Market Status**: Check if markets are open/closed before displaying
5. **Token IDs**: Map outcomes to CLOB token IDs for pricing

## Troubleshooting

**SDK Import Fails:**
```bash
pip install polymarket-client>=0.1.0b3
```

**Market Not Found:**
- Slug may be case-sensitive
- Market may be closed/resolved
- Try searching by condition ID instead

**Orderbook Empty:**
- Market may have no liquidity
- Token ID may be incorrect
- Check market status is "open"

## Files Created

- `backend/app/services/polymarket_service.py` - Core service
- `backend/app/api/v1/polymarket.py` - API router
- `backend/requirements.txt` - Added `polymarket-client>=0.1.0b3`