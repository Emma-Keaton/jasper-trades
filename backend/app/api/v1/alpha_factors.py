"""
Alpha Factor Zoo endpoints - Browse, compute, and advise on the real 452-factor zoo.
"""
from fastapi import APIRouter, Body, Depends, Header, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, Any, Optional, List

from app.database import get_db
from app.services.alpha_factor_service import AlphaFactorService
from app.services.valuation_service import ValuationService

router = APIRouter()


@router.get("")
async def list_alpha_factors(
    category: Optional[str] = None,
    difficulty: Optional[str] = None,
    min_sharpe: Optional[float] = Query(default=None, ge=0),
    min_win_rate: Optional[float] = Query(default=None, ge=0, le=100),
    search: Optional[str] = Query(default=None, min_length=2),
    limit: int = Query(default=50, le=200),
    db: AsyncSession = Depends(get_db),
):
    """
    List alpha factors with optional filters.
    
    Returns the 452 alpha factors from the zoo.
    """
    factor_service = AlphaFactorService(db)
    
    factors = await factor_service.get_factors(
        category=category,
        difficulty=difficulty,
        min_sharpe=min_sharpe,
        min_win_rate=min_win_rate,
        search_query=search,
        limit=limit,
    )
    
    return {
        "factors": factors,
        "count": len(factors),
        "total_available": 452,
    }


@router.get("/categories")
async def get_categories(db: AsyncSession = Depends(get_db)):
    """Get unique factor categories."""
    factor_service = AlphaFactorService(db)
    categories = await factor_service.get_categories()
    
    return {
        "categories": categories,
    }


@router.get("/{factor_id}")
async def get_factor(
    factor_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get detailed information about a specific alpha factor."""
    factor_service = AlphaFactorService(db)
    factor = await factor_service.get_factor_by_id(factor_id)
    
    if not factor:
        raise HTTPException(status_code=404, detail="Factor not found")
    
    return factor


@router.get("/{factor_id}/performance")
async def get_factor_performance(
    factor_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get historical performance metrics for an alpha factor."""
    factor_service = AlphaFactorService(db)
    performance = await factor_service.get_factor_performance(factor_id)
    
    if not performance:
        raise HTTPException(status_code=404, detail="Factor not found")
    
    return performance


@router.post("/{factor_id}/add-to-strategy")
async def add_factor_to_strategy(
    factor_id: str,
    strategy_name: str = Query(default="Default Strategy"),
    weight: float = Query(default=1.0, ge=0.1, le=10.0),
    db: AsyncSession = Depends(get_db),
):
    """Add an alpha factor to a backtest strategy."""
    factor_service = AlphaFactorService(db)
    result = await factor_service.add_factor_to_strategy(
        factor_id=factor_id,
        strategy_name=strategy_name,
        weight=weight,
    )
    
    if result.get("error"):
        raise HTTPException(status_code=404, detail=result["error"])
    
    return result


@router.post("/ensemble/performance")
async def get_ensemble_performance(
    factor_ids: List[str],
    strategy_name: str = "Custom Ensemble",
    db: AsyncSession = Depends(get_db),
):
    """Get estimated performance metrics for a factor ensemble."""
    factor_service = AlphaFactorService(db)
    result = await factor_service.get_ensemble_performance(
        factor_ids=factor_ids,
        strategy_name=strategy_name,
    )
    
    return result


# ---------------------------------------------------------------------------
# Live computation + automated strategy selection
# ---------------------------------------------------------------------------

def _build_panel(ohlcv: List[List[float]]) -> Dict[str, Any]:
    """Convert CCXT-style OHLCV rows to a wide panel dict for factor compute.

    Rows are [ts, open, high, low, close, volume] ascending by timestamp.
    """
    import pandas as pd

    ts = pd.to_datetime([int(r[0]) for r in ohlcv], unit="ms")
    idx = pd.DatetimeIndex(ts, name="date")
    cols = {"open": [], "high": [], "low": [], "close": [], "volume": []}
    for r in ohlcv:
        for k, i in zip(cols, (1, 2, 3, 4, 5)):
            cols[k].append(float(r[i]))
    if not cols["close"]:
        return {}
    return {k: pd.DataFrame({1: v}, index=idx) for k, v in cols.items()}


async def _fetch_ohlcv(symbol: str) -> Optional[List[List[float]]]:
    """Fetch hourly OHLCV for a symbol via CCXT (crypto) or yfinance (stocks)."""
    symbol = (symbol or "").upper()
    try:
        from app.services.ccxt_market_data_service import get_ccxt_market_data_service

        try:
            return await get_ccxt_market_data_service().get_ohlcv(symbol, timeframe="1h", limit=300)
        except Exception:  # noqa: BLE001
            pass

        from app.services.data_connectors import data_connector_service
        hist = await data_connector_service.get_yfinance_data(symbol, interval="1d", range_="6mo")
        if hist:
            import pandas as pd
            return [[int(pd.Timestamp(r["timestamp"]).timestamp() * 1000), r["open"], r["high"], r["low"], r["close"], r["volume"]]
                    for r in hist]
    except Exception:  # noqa: BLE001
        pass
    return None


@router.post("/evaluate")
async def evaluate_factor(
    factor_id: str,
    symbol: str = "BTC",
    ohlcv: Optional[List[List[float]]] = Body(default=None),
    db: AsyncSession = Depends(get_db),
):
    """Compute a single factor's latest values on live OHLCV for a symbol.

    If ``ohlcv`` is omitted it is fetched automatically (hourly, 300 bars).
    """
    factor_service = AlphaFactorService(db)
    factor = await factor_service.get_factor_by_id(factor_id)
    if not factor:
        raise HTTPException(status_code=404, detail="Factor not found")

    if not ohlcv:
        ohlcv = await _fetch_ohlcv(symbol)
    if not ohlcv or len(ohlcv) < 2:
        raise HTTPException(status_code=400, detail="Not enough OHLCV data to evaluate")

    panel = _build_panel(ohlcv)
    result = await factor_service.compute_factor(factor_id, panel)
    if result.get("error"):
        raise HTTPException(status_code=400, detail=result)

    return result


@router.post("/advise")
async def advise_trade(
    symbol: str = "BTC",
    side: str = "buy",
    limit_to_zoos: Optional[List[str]] = Body(default=None),
    top: int = Body(default=10, ge=1, le=50),
    auto_fetch: bool = Body(default=True),
    ohlcv: Optional[List[List[float]]] = Body(default=None),
    db: AsyncSession = Depends(get_db),
):
    """Advise the best factor-driven strategy for a pending trade.

    Computes every runnable zoo factor on the symbol's live OHLCV, ranks by
    signal strength, and returns the recommended strategy (theme + direction +
    confidence) plus the top contributing factors.
    """
    factor_service = AlphaFactorService(db)
    if not ohlcv and auto_fetch:
        ohlcv = await _fetch_ohlcv(symbol)
    if not ohlcv or len(ohlcv) < 2:
        raise HTTPException(status_code=400, detail="Not enough OHLCV data to advise")

    panel = _build_panel(ohlcv)
    result = await factor_service.advise_for_trade(
        symbol=symbol,
        panel=panel,
        side=side,
        limit_to_zoos=limit_to_zoos,
        top=top,
    )
    return result


@router.post("/auto-trade")
async def auto_trade(
    symbol: str = Body(...),
    side: Optional[str] = Body(default=None),
    max_position_pct: float = Body(default=0.05, ge=0.0, le=1.0),
    limit_to_zoos: Optional[List[str]] = Body(default=None),
    x_device_id: Optional[str] = Header(default=None),
    db: AsyncSession = Depends(get_db),
):
    """Take a trade automatically based on the winning factor consensus.

    Runs the full advisor on the symbol's live OHLCV; when the factor consensus
    picks a direction with sufficient confidence it executes a paper (or live)
    trade through the unified trade gate. ``side`` may be forced; otherwise the
    consensus direction is used.
    """
    device_id = (x_device_id or "").strip() or "default-device"
    factor_service = AlphaFactorService(db)

    ohlcv = await _fetch_ohlcv(symbol)
    if not ohlcv or len(ohlcv) < 2:
        raise HTTPException(status_code=400, detail="Not enough OHLCV data to auto-trade")

    panel = _build_panel(ohlcv)
    advise = await factor_service.advise_for_trade(
        symbol=symbol,
        panel=panel,
        side=side or "auto",
        limit_to_zoos=limit_to_zoos,
        top=10,
    )

    if not advise.get("strategy"):
        raise HTTPException(status_code=400, detail="No factor produced a computable signal for this symbol")

    direction = side or advise.get("recommended_direction")
    if advise.get("recommended_direction") == "neutral":
        return {
            "status": "hold",
            "symbol": symbol,
            "recommendation": advise,
            "message": "Factor consensus is neutral; holding (no trade taken).",
        }

    strategy = advise["strategy"]
    if strategy.get("net_signal") == 0:
        return {
            "status": "hold",
            "symbol": symbol,
            "recommendation": advise,
            "message": "Factor signals cancel out; no trade taken.",
        }

    # Position sizing: % of portfolio cash, capped by gate.
    from app.models import Portfolio
    from sqlalchemy import select

    res = await db.execute(select(Portfolio).limit(50))
    portfolios = list(res.scalars().all())
    portfolio = next((p for p in portfolios if (p.device_id or "") == device_id), portfolios[0] if portfolios else None)
    if portfolio is None:
        from app.services.portfolio_service import PortfolioService
        ps = PortfolioService(db)
        portfolio = await ps.create_portfolio(name="Default", initial_cash=100000.0, is_paper=True)

    equity = float(portfolio.cash or 0.0)
    notional = equity * max_position_pct
    price = await ValuationService().get_price(symbol)
    if not price or price <= 0:
        raise HTTPException(status_code=400, detail=f"Could not resolve a market price for {symbol}")
    qty = notional / price

    from app.services import trade_gate

    mode = await trade_gate.resolve_mode(db, device_id)
    buy_dir = direction in ("buy", "long")
    side_str = "buy" if buy_dir else "sell"
    asset_class = "crypto" if _is_crypto(symbol) else "stocks"

    gate = await trade_gate.check_prerequisites(
        db, device_id,
        symbol=symbol, side=side_str, qty=qty, price=price,
        intent=mode, asset_class=asset_class, portfolio_id=portfolio.id,
        route="factor-auto",
    )
    if not gate["passed"]:
        return {
            "status": "blocked",
            "symbol": symbol,
            "direction": direction,
            "reason": trade_gate.describe_failures(gate),
            "recommendation": {
                "strategy": strategy,
                "top_factors": advise["factors"][:5],
            },
        }

    if mode == "paper":
        result = await trade_gate.execute_paper(
            device_id=device_id, symbol=symbol, side=side_str,
            qty=qty, price=price, asset_class=asset_class,
            agent_name="factor-auto", reasoning=f"Winning factor consensus: {strategy['theme']}",
        )
    else:
        from app.services.signal_sources.ingest import _execute_live
        # Reuse the signal engine's live path with a placeholder tip-like object.
        class _TipProxy:
            id = 0
            device_id = device_id
            symbol = symbol
            side = "long" if buy_dir else "short"
            confidence = 0.95
            execution_status = "pending"
            executed = False
            entry_price = None
            execution_detail = ""
            executed_at = None
            rationale = f"factor-auto {strategy['theme']} consensus"
            text = ""

        result = await _execute_live(db, device_id, _TipProxy(), portfolio.id, side_str, qty, price)

    return {
        "status": "success",
        "symbol": symbol,
        "direction": direction,
        "mode": mode,
        "recommended_strategy": strategy,
        "top_factors": advise["factors"][:5],
        "trade": result,
        "message": f"Executed automated {side_str.upper()} {qty:g} {symbol} @ ${price:g} on {strategy['theme']} consensus.",
    }


def _is_crypto(symbol: str) -> bool:
    from app.services.signal_sources.ingest import _CRYPTO

    return (symbol or "").upper() in _CRYPTO