"""
Polymarket API - Prediction market data and simulated trading
Inspired by AI-Trader Polymarket integration
"""
from fastapi import APIRouter, HTTPException, Query, Body, Header, Depends
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
import structlog
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime

from app.services.polymarket_service import polymarket_service, PolymarketMarket, PolymarketOrderbook
from app.database import get_db

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/v1/polymarket", tags=["Polymarket"])


class MarketSummary(BaseModel):
    """Market summary response"""
    market_id: str
    question: str
    slug: str
    outcomes: List[str]
    volume: float
    liquidity: float
    status: str
    best_prices: Dict[str, float]


class OrderbookSummary(BaseModel):
    """Orderbook summary response"""
    token_id: str
    best_bid: float
    best_ask: float
    mid_price: float
    spread: float
    spread_pct: float


class MarketAnalysis(BaseModel):
    """Market analysis response"""
    market_id: str
    question: str
    outcomes: List[str]
    prices: Dict[str, float]
    total_implied_probability: float
    arbitrage_detected: bool
    recommendation: Optional[str]
    confidence: float


@router.get("/search")
async def search_markets(
    query: str = Query(..., description="Search query (e.g., 'BTC', 'election', 'Fed')"),
    limit: int = Query(20, ge=1, le=100, description="Maximum results")
) -> List[Dict[str, Any]]:
    """
    Search for Polymarket markets by keyword.
    
    Returns market metadata including:
    - Question and slug
    - Outcomes and token IDs
    - Volume and liquidity
    - Status and closing date
    """
    try:
        markets = await polymarket_service.search_markets(query, limit)
        
        return [
            {
                "market_id": m.market_id,
                "question": m.question,
                "slug": m.slug,
                "outcomes": m.outcomes,
                "clob_token_ids": m.clob_token_ids,
                "volume": m.volume,
                "liquidity": m.liquidity,
                "status": m.status,
                "closing_date": m.closing_date
            }
            for m in markets
        ]
    
    except Exception as e:
        logger.error(f"Polymarket search failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/market/{slug:path}")
async def get_market(slug: str) -> Dict[str, Any]:
    """
    Get market metadata by slug.
    
    Example slug: `will-btc-be-above-120k-on-june-30`
    
    Use this endpoint to:
    - Resolve market details
    - Get outcome token IDs
    - Read volume and liquidity
    """
    try:
        market = await polymarket_service.get_market_by_slug(slug)
        
        if not market:
            raise HTTPException(status_code=404, detail="Market not found")
        
        return {
            "market_id": market.market_id,
            "question": market.question,
            "slug": market.slug,
            "condition_id": market.condition_id,
            "outcomes": market.outcomes,
            "clob_token_ids": market.clob_token_ids,
            "volume": market.volume,
            "liquidity": market.liquidity,
            "open_interest": market.open_interest,
            "status": market.status,
            "closing_date": market.closing_date,
            "resolved_prices": market.resolved_prices
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get market {slug}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/market/by-condition/{condition_id}")
async def get_market_by_condition(condition_id: str) -> Dict[str, Any]:
    """
    Get market by on-chain condition ID.
    
    Condition IDs are Ethereum identifiers for prediction markets.
    """
    try:
        market = await polymarket_service.get_market_by_condition_id(condition_id)
        
        if not market:
            raise HTTPException(status_code=404, detail="Market not found")
        
        return asdict(market)
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get market by condition {condition_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/orderbook/{token_id}")
async def get_orderbook(token_id: str) -> Dict[str, Any]:
    """
    Get orderbook for a specific outcome token.
    
    Returns:
    - Bid/ask orders with prices and sizes
    - Best bid/ask prices
    - Mid price (fair value estimate)
    - Spread (bid-ask difference)
    """
    try:
        orderbook = await polymarket_service.get_orderbook(token_id)
        
        if not orderbook:
            raise HTTPException(status_code=404, detail="Orderbook not found")
        
        return {
            "token_id": orderbook.token_id,
            "bids": orderbook.bids[:10],  # Top 10 bids
            "asks": orderbook.asks[:10],  # Top 10 asks
            "best_bid": orderbook.best_bid,
            "best_ask": orderbook.best_ask,
            "mid_price": orderbook.mid_price,
            "spread": orderbook.spread,
            "last_update": orderbook.last_update
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get orderbook for {token_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/price/{token_id}")
async def get_price(token_id: str) -> Dict[str, Any]:
    """
    Get current mid price for an outcome token.
    
    Price represents implied probability (0.0-1.0):
    - 0.65 = 65% probability
    - 0.50 = 50/50 coin flip
    - 0.25 = 25% probability
    
    Example: A "Yes" token at 0.70 means the market assigns
    70% probability to that outcome occurring.
    """
    try:
        price = await polymarket_service.get_outcome_price(token_id)
        
        if price is None:
            raise HTTPException(status_code=404, detail="Price not available")
        
        return {
            "token_id": token_id,
            "mid_price": price,
            "implied_probability": f"{price:.1%}"
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get price for {token_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/analyze/{slug:path}")
async def analyze_market(slug: str) -> Dict[str, Any]:
    """
    Analyze a Polymarket for trading opportunities.
    
    Analysis includes:
    - Current outcome prices
    - Total implied probability check
    - Arbitrage detection (sum != 1.0)
    - Value recommendation
    - Confidence score
    
    **Example opportunity**: If all outcomes sum to <0.90,
    buying all outcomes guarantees profit (arbitrage).
    """
    try:
        analysis = await polymarket_service.analyze_market(slug)
        
        if not analysis:
            raise HTTPException(status_code=404, detail="Market not found or analysis failed")
        
        return {
            "market_id": analysis["market_id"],
            "question": analysis["question"],
            "outcomes": analysis["outcomes"],
            "prices": analysis["prices"],
            "total_implied_probability": analysis["total_implied_probability"],
            "arbitrage_detected": analysis["arbitrage_detected"],
            "recommendation": analysis["recommendation"],
            "confidence": analysis["confidence"]
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Market analysis failed for {slug}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/trending")
async def get_trending_markets(limit: int = Query(10, ge=1, le=50)) -> List[Dict[str, Any]]:
    """
    Get trending/volatile markets.
    
    Useful for discovering active prediction markets with high volume.
    """
    try:
        markets = await polymarket_service.get_trending_markets(limit)
        
        return [
            {
                "market_id": m.market_id,
                "question": m.question,
                "slug": m.slug,
                "outcomes": m.outcomes,
                "volume": m.volume,
                "liquidity": m.liquidity,
                "status": m.status
            }
            for m in markets
        ]
    
    except Exception as e:
        logger.error(f"Failed to get trending markets: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/category/{category}")
async def get_markets_by_category(
    category: str,
    limit: int = Query(20, ge=1, le=100)
) -> List[Dict[str, Any]]:
    """
    Get markets by category.
    
    **Categories:**
    - `crypto`: Bitcoin, Ethereum, crypto price predictions
    - `politics`: Elections, policy decisions
    - `sports`: Game outcomes, championships
    - `economics`: Fed rates, GDP, inflation
    - `current-events`: News events
    """
    try:
        markets = await polymarket_service.get_markets_by_category(category, limit)
        
        return [
            {
                "market_id": m.market_id,
                "question": m.question,
                "slug": m.slug,
                "outcomes": m.outcomes,
                "volume": m.volume,
                "liquidity": m.liquidity,
                "status": m.status
            }
            for m in markets
        ]
    
    except Exception as e:
        logger.error(f"Failed to get {category} markets: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status")
async def get_polymarket_status():
    """Get Polymarket service status"""
    return polymarket_service.get_cache_status()


@router.post("/cache/refresh")
async def refresh_cache():
    """Refresh cached market data"""
    try:
        await polymarket_service.refresh_cache()
        return {"status": "success", "message": "Cache refreshed"}

    except Exception as e:
        logger.error(f"Cache refresh failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============ Account Connection & Trading Endpoints ============

from app.models_ext.polymarket import PolymarketAccount, PolymarketLeaderConfig, PolymarketPosition, PolymarketTrade
from app.services.encryption import encrypt_value, decrypt_value
from sqlalchemy import select
from pydantic import BaseModel
from typing import Optional, List, Dict, Any


class PolymarketCredentials(BaseModel):
    """API credentials for connecting Polymarket account"""
    api_key: str
    api_secret: str


class TradeRequest(BaseModel):
    """Trade execution request"""
    market_slug: str
    outcome: str
    amount: float
    side: str = "BUY"
    price: Optional[float] = None


@router.post("/connection/configure")
async def configure_polymarket(
    credentials: PolymarketCredentials,
    device_id: str = Header(None, alias="X-Device-ID"),
    db: AsyncSession = Depends(get_db),
):
    """
    Connect Polymarket account with API credentials.
    Credentials are encrypted before storage.
    """
    if not device_id:
        raise HTTPException(status_code=400, detail="X-Device-ID header required")
    
    try:
        # Check if account already exists
        result = await db.execute(
            select(PolymarketAccount).where(PolymarketAccount.device_id == device_id)
        )
        existing = result.scalar_one_or_none()
        
        if existing:
            raise HTTPException(status_code=400, detail="Polymarket account already connected")
        
        # Encrypt credentials
        encrypted_key = encrypt_value(credentials.api_key)
        encrypted_secret = encrypt_value(credentials.api_secret)
        
        # Create account record
        account = PolymarketAccount(
            device_id=device_id,
            encrypted_api_key=encrypted_key,
            encrypted_api_secret=encrypted_secret,
            is_connected=True,
            connection_status="connected",
        )
        
        db.add(account)
        await db.commit()
        await db.refresh(account)
        
        logger.info(f"Polymarket account connected for device {device_id}")
        
        return {
            "success": True,
            "message": "Polymarket account connected successfully",
            "wallet_address": account.wallet_address,
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to connect Polymarket account: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/connection/status")
async def get_polymarket_connection_status(
    device_id: str = Header(None, alias="X-Device-ID"),
    db: AsyncSession = Depends(get_db),
):
    """Check if device has connected Polymarket account"""
    if not device_id:
        return {"connected": False, "message": "X-Device-ID header required"}
    
    try:
        result = await db.execute(
            select(PolymarketAccount).where(PolymarketAccount.device_id == device_id)
        )
        account = result.scalar_one_or_none()
        
        if not account:
            return {
                "connected": False,
                "message": "No Polymarket account connected",
                "ai_trading_enabled": False,
                "copytrading_enabled": False,
            }
        
        return {
            "connected": True,
            "wallet_address": account.wallet_address,
            "account_balance": account.account_balance,
            "ai_trading_enabled": account.ai_trading_enabled,
            "copytrading_enabled": account.copytrading_enabled,
            "is_active": account.is_active,
            "connection_status": account.connection_status,
            "last_balance_sync": account.last_balance_sync_at.isoformat() if account.last_balance_sync_at else None,
        }
        
    except Exception as e:
        logger.error(f"Failed to get connection status: {e}")
        return {"connected": False, "error": str(e)}


@router.delete("/connection")
async def disconnect_polymarket(
    device_id: str = Header(None, alias="X-Device-ID"),
    db: AsyncSession = Depends(get_db),
):
    """Disconnect Polymarket account and delete credentials"""
    if not device_id:
        raise HTTPException(status_code=400, detail="X-Device-ID header required")
    
    try:
        result = await db.execute(
            select(PolymarketAccount).where(PolymarketAccount.device_id == device_id)
        )
        account = result.scalar_one_or_none()
        
        if not account:
            raise HTTPException(status_code=404, detail="No Polymarket account found")
        
        # Delete account (this removes encrypted credentials)
        await db.delete(account)
        await db.commit()
        
        logger.info(f"Polymarket account disconnected for device {device_id}")
        
        return {
            "success": True,
            "message": "Polymarket account disconnected",
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to disconnect: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/trade/execute")
async def execute_polymarket_trade(
    request: TradeRequest,
    device_id: str = Header(None, alias="X-Device-ID"),
    db: AsyncSession = Depends(get_db),
):
    """
    Execute trade on connected Polymarket account.
    Can be called by AI agents or manually by user.
    """
    if not device_id:
        raise HTTPException(status_code=400, detail="X-Device-ID header required")
    
    try:
        # Get account
        result = await db.execute(
            select(PolymarketAccount).where(PolymarketAccount.device_id == device_id)
        )
        account = result.scalar_one_or_none()
        
        if not account or not account.is_connected:
            raise HTTPException(status_code=400, detail="Polymarket account not connected")
        
        if not account.is_active:
            raise HTTPException(status_code=400, detail="Polymarket account is disabled")
        
        # Decrypt API credentials
        api_key = decrypt_value(account.encrypted_api_key)
        api_secret = decrypt_value(account.encrypted_api_secret)
        
        # Place order via CLOB
        order_result = await polymarket_service.place_order(
            api_key=api_key,
            api_secret=api_secret,
            market_slug=request.market_slug,
            outcome=request.outcome,
            amount=request.amount,
            side=request.side,
            price=request.price,
        )
        
        if not order_result or 'error' in order_result:
            raise HTTPException(
                status_code=400,
                detail=order_result.get('error', 'Order execution failed')
            )
        
        # Record trade in database
        trade = PolymarketTrade(
            account_id=account.id,
            market_id=order_result.get('market_id'),
            outcome=request.outcome,
            side=request.side,
            quantity=order_result.get('quantity'),
            execution_price=order_result.get('price'),
            total_value=request.amount,
            clob_order_id=order_result.get('order_id'),
            execution_timestamp=order_result.get('created_at'),
        )
        
        db.add(trade)
        
        # Update account last trade time
        account.last_trade_at = datetime.utcnow()
        
        await db.commit()
        
        logger.info(
            f"Polymarket trade executed",
            market=request.market_slug,
            outcome=request.outcome,
            side=request.side,
            amount=request.amount,
        )
        
        return {
            "success": True,
            "order_id": order_result.get('order_id'),
            "market_slug": request.market_slug,
            "outcome": request.outcome,
            "side": request.side,
            "amount": request.amount,
            "price": order_result.get('price'),
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Trade execution failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/account/balance")
async def get_polymarket_balance(
    device_id: str = Header(None, alias="X-Device-ID"),
    db: AsyncSession = Depends(get_db),
):
    """Get account balance and positions"""
    if not device_id:
        raise HTTPException(status_code=400, detail="X-Device-ID header required")
    
    try:
        result = await db.execute(
            select(PolymarketAccount).where(PolymarketAccount.device_id == device_id)
        )
        account = result.scalar_one_or_none()
        
        if not account or not account.is_connected:
            raise HTTPException(status_code=400, detail="Polymarket account not connected")
        
        # Decrypt credentials
        api_key = decrypt_value(account.encrypted_api_key)
        api_secret = decrypt_value(account.encrypted_api_secret)
        
        # Fetch balance from Polymarket
        balance_data = await polymarket_service.get_account_balance(api_key, api_secret)
        
        if not balance_data:
            raise HTTPException(status_code=500, detail="Failed to fetch balance from Polymarket")
        
        # Update local cache
        account.account_balance = balance_data.get('balance', 0)
        account.account_equity = balance_data.get('equity', 0)
        account.wallet_address = balance_data.get('wallet_address', account.wallet_address)
        account.last_balance_sync_at = datetime.utcnow()
        
        await db.commit()
        
        return balance_data
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Balance fetch failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/leaders")
async def get_polymarket_leaders(
    limit: int = 20,
    device_id: str = Header(None, alias="X-Device-ID"),
    db: AsyncSession = Depends(get_db),
):
    """
    Get top Polymarket traders for copytrading.
    AI analyzes these leaders to identify best performers to follow.
    """
    try:
        leaders = await polymarket_service.get_leader_traders(limit)
        
        # Check if user has account connected
        if device_id:
            result = await db.execute(
                select(PolymarketAccount).where(PolymarketAccount.device_id == device_id)
            )
            account = result.scalar_one_or_none()
            
            # Filter out leaders already being followed
            if account:
                leader_configs_result = await db.execute(
                    select(PolymarketLeaderConfig).where(
                        PolymarketLeaderConfig.account_id == account.id,
                        PolymarketLeaderConfig.is_active == True
                    )
                )
                following = {lc.leader_id for lc in leader_configs_result.scalars().all()}
                
                for leader in leaders:
                    leader['is_following'] = leader['leader_id'] in following
        
        return {"leaders": leaders}
        
    except Exception as e:
        logger.error(f"Leader fetch failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/leader/{leader_id}/follow")
async def follow_polymarket_leader(
    leader_id: str,
    config: Dict[str, Any] = Body({}),
    device_id: str = Header(None, alias="X-Device-ID"),
    db: AsyncSession = Depends(get_db),
):
    """
    Follow a Polymarket leader for copytrading.
    AI will automatically copy this leader's trades based on config.
    """
    if not device_id:
        raise HTTPException(status_code=400, detail="X-Device-ID header required")
    
    try:
        # Get account
        result = await db.execute(
            select(PolymarketAccount).where(PolymarketAccount.device_id == device_id)
        )
        account = result.scalar_one_or_none()
        
        if not account:
            raise HTTPException(status_code=400, detail="Polymarket account not connected")
        
        # Create or update leader config
        leader_config_result = await db.execute(
            select(PolymarketLeaderConfig).where(
                PolymarketLeaderConfig.account_id == account.id,
                PolymarketLeaderConfig.leader_id == leader_id
            )
        )
        existing = leader_config_result.scalar_one_or_none()
        
        if existing:
            # Update existing config
            existing.allocation_weight = config.get('allocation_weight', 0.5)
            existing.min_confidence = config.get('min_confidence', 0.7)
            existing.max_copy_amount = config.get('max_copy_amount', 50.0)
            existing.is_active = True
        else:
            # Create new config
            leader_config = PolymarketLeaderConfig(
                account_id=account.id,
                leader_id=leader_id,
                leader_name=config.get('leader_name', f'Leader_{leader_id}'),
                leader_wallet=config.get('leader_wallet', ''),
                allocation_weight=config.get('allocation_weight', 0.5),
                min_confidence=config.get('min_confidence', 0.7),
                max_copy_amount=config.get('max_copy_amount', 50.0),
            )
            db.add(leader_config)
        
        await db.commit()
        
        logger.info(f"Following Polymarket leader {leader_id}")
        
        return {
            "success": True,
            "message": f"Now following leader {leader_id}",
            "allocation_weight": config.get('allocation_weight', 0.5),
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to follow leader: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/leader/{leader_id}/unfollow")
async def unfollow_polymarket_leader(
    leader_id: str,
    device_id: str = Header(None, alias="X-Device-ID"),
    db: AsyncSession = Depends(get_db),
):
    """Stop following a Polymarket leader"""
    if not device_id:
        raise HTTPException(status_code=400, detail="X-Device-ID header required")
    
    try:
        result = await db.execute(
            select(PolymarketAccount).where(PolymarketAccount.device_id == device_id)
        )
        account = result.scalar_one_or_none()
        
        if not account:
            raise HTTPException(status_code=400, detail="Polymarket account not connected")
        
        # Find and delete config
        leader_config_result = await db.execute(
            select(PolymarketLeaderConfig).where(
                PolymarketLeaderConfig.account_id == account.id,
                PolymarketLeaderConfig.leader_id == leader_id
            )
        )
        leader_config = leader_config_result.scalar_one_or_none()
        
        if not leader_config:
            raise HTTPException(status_code=404, detail="Not following this leader")
        
        await db.delete(leader_config)
        await db.commit()
        
        logger.info(f"Unfollowed Polymarket leader {leader_id}")
        
        return {
            "success": True,
            "message": f"No longer following leader {leader_id}",
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to unfollow leader: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ============ Account Connection Endpoints ============

from app.models_ext.polymarket import PolymarketAccount, PolymarketLeaderConfig
from app.services.encryption import encrypt_value, decrypt_value
