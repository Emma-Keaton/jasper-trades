"""
QuantLib API - 18 quantitative analysis modules
"""
from fastapi import APIRouter, HTTPException, Body, Query
from typing import Dict, Any, List
from pydantic import BaseModel, Field
import structlog

from app.services.quantlib_service import quantlib_service

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/v1/quantlib", tags=["QuantLib"])


# ========== Request Models ==========

class BlackScholesRequest(BaseModel):
    S: float = Field(..., description="Spot price")
    K: float = Field(..., description="Strike price")
    T: float = Field(..., description="Time to maturity (years)")
    r: float = Field(..., description="Risk-free rate")
    sigma: float = Field(..., description="Volatility")
    option_type: str = Field("call", description="call or put")


class GreeksRequest(BaseModel):
    S: float
    K: float
    T: float
    r: float
    sigma: float
    option_type: str = "call"


class BinomialTreeRequest(BaseModel):
    S: float
    K: float
    T: float
    r: float
    sigma: float
    N: int = Field(100, ge=10, le=500)
    option_type: str = "call"


class MonteCarloRequest(BaseModel):
    S: float
    mu: float
    sigma: float
    T: float = Field(1/252, description="Time horizon (default: 1 day)")
    n_simulations: int = Field(10000, ge=1000, le=100000)
    confidence_level: float = Field(0.95)


class VaRRequest(BaseModel):
    returns: List[float]
    confidence_level: float = Field(0.95, ge=0.90, le=0.99)


class PerformanceRatioRequest(BaseModel):
    returns: List[float]
    risk_free_rate: float = Field(0.02, description="Annualized")
    benchmark_returns: List[float] = Field(None, description="For Treynor/Information ratios")


class DrawdownRequest(BaseModel):
    equity_curve: List[float]


# ========== Endpoints ==========

@router.get("/modules")
async def list_quantlib_modules():
    """List all 18 QuantLib modules"""
    return {
        "modules": quantlib_service.get_all_modules(),
        "total": 18,
        "categories": ["options", "risk", "performance", "volatility", "simulation"],
    }


@router.post("/options/black-scholes")
async def black_scholes(request: BlackScholesRequest):
    """
    Black-Scholes option pricing.
    
    Returns fair value, intrinsic value, and time value.
    """
    return quantlib_service.black_scholes_price(
        S=request.S,
        K=request.K,
        T=request.T,
        r=request.r,
        sigma=request.sigma,
        option_type=request.option_type,
    )


@router.post("/options/greeks")
async def calculate_greeks(request: GreeksRequest):
    """
    Calculate option Greeks: Delta, Gamma, Vega, Theta, Rho.
    
    Measures sensitivity to underlying price, volatility, time, and rates.
    """
    return quantlib_service.calculate_greeks(
        S=request.S,
        K=request.K,
        T=request.T,
        r=request.r,
        sigma=request.sigma,
        option_type=request.option_type,
    )


@router.post("/options/binomial-tree")
async def binomial_tree(request: BinomialTreeRequest):
    """
    Binomial tree option pricing (Cox-Ross-Rubinstein).
    
    Supports American options and early exercise.
    """
    return quantlib_service.binomial_tree_price(
        S=request.S,
        K=request.K,
        T=request.T,
        r=request.r,
        sigma=request.sigma,
        N=request.N,
        option_type=request.option_type,
    )


@router.post("/risk/monte-carlo-var")
async def monte_carlo_var(request: MonteCarloRequest):
    """
    Monte Carlo Value at Risk.
    
    Simulates price paths to estimate VaR and Expected Shortfall.
    """
    return quantlib_service.monte_carlo_var(
        S=request.S,
        mu=request.mu,
        sigma=request.sigma,
        T=request.T,
        n_simulations=request.n_simulations,
        confidence_level=request.confidence_level,
    )


@router.post("/risk/historical-var")
async def historical_var(request: VaRRequest):
    """
    Historical Value at Risk (non-parametric).
    
    Uses empirical distribution of historical returns.
    """
    return quantlib_service.historical_var(
        returns=request.returns,
        confidence_level=request.confidence_level,
    )


@router.post("/risk/parametric-var")
async def parametric_var(request: VaRRequest):
    """
    Parametric VaR (Gaussian distribution).
    
    Faster than Monte Carlo but assumes normal distribution.
    """
    return quantlib_service.parametric_var(
        returns=request.returns,
        confidence_level=request.confidence_level,
    )


@router.post("/risk/cvar")
async def conditional_var(request: VaRRequest):
    """
    Conditional VaR (CVaR / Expected Shortfall).
    
    Average loss beyond VaR threshold. More conservative than VaR.
    """
    return quantlib_service.conditional_var(
        returns=request.returns,
        confidence_level=request.confidence_level,
    )


@router.post("/risk/max-drawdown")
async def maximum_drawdown(request: DrawdownRequest):
    """
    Maximum Drawdown from equity curve.
    
    Largest peak-to-trough decline.
    """
    return quantlib_service.maximum_drawdown(
        equity_curve=request.equity_curve,
    )


@router.post("/performance/sharpe")
async def sharpe_ratio(request: PerformanceRatioRequest):
    """
    Sharpe Ratio - Risk-adjusted return.
    
    Excess return per unit of volatility.
    """
    return quantlib_service.sharpe_ratio(
        returns=request.returns,
        risk_free_rate=request.risk_free_rate,
    )


@router.post("/performance/sortino")
async def sortino_ratio(request: PerformanceRatioRequest):
    """
    Sortino Ratio - Downside risk-adjusted return.
    
    Penalizes only downside volatility.
    """
    return quantlib_service.sortino_ratio(
        returns=request.returns,
        risk_free_rate=request.risk_free_rate,
    )


@router.post("/performance/treynor")
async def treynor_ratio(request: PerformanceRatioRequest):
    """
    Treynor Ratio - Systematic risk-adjusted return.
    
    Uses beta instead of total volatility.
    """
    if not request.benchmark_returns:
        raise HTTPException(status_code=400, detail="benchmark_returns required for Treynor ratio")
    
    return quantlib_service.treynor_ratio(
        returns=request.returns,
        benchmark_returns=request.benchmark_returns,
        risk_free_rate=request.risk_free_rate,
    )


@router.post("/performance/information")
async def information_ratio(request: PerformanceRatioRequest):
    """
    Information Ratio - Active return per unit of tracking error.
    
    Measures manager skill vs benchmark.
    """
    if not request.benchmark_returns:
        raise HTTPException(status_code=400, detail="benchmark_returns required for Information ratio")
    
    return quantlib_service.information_ratio(
        returns=request.returns,
        benchmark_returns=request.benchmark_returns,
    )


@router.post("/performance/calmar")
async def calmar_ratio(request: PerformanceRatioRequest):
    """
    Calmar Ratio - Return / Max Drawdown.
    
    Good for CTAs and hedge funds.
    """
    return quantlib_service.calmar_ratio(
        returns=request.returns,
    )


@router.post("/performance/sterling")
async def sterling_ratio(request: PerformanceRatioRequest):
    """
    Sterling Ratio - Return / Average Drawdown.
    
    Less sensitive to single extreme events.
    """
    return quantlib_service.sterling_ratio(
        returns=request.returns,
    )


@router.post("/performance/burke")
async def burke_ratio(request: PerformanceRatioRequest):
    """
    Burke Ratio - Return / RMS of drawdowns.
    
    Penalizes frequent small drawdowns.
    """
    return quantlib_service.burke_ratio(
        returns=request.returns,
    )


@router.post("/simulation/monte-carlo")
async def monte_carlo_simulator(request: MonteCarloRequest):
    """
    Monte Carlo price path simulator.
    
    Uses Geometric Brownian Motion.
    """
    return quantlib_service.montecarlo_simulator(
        S=request.S,
        mu=request.mu,
        sigma=request.sigma,
        T=request.T,
        n_steps=252,
        n_simulations=min(request.n_simulations, 1000),  # Limit for API
    )


@router.post("/volatility/historical")
async def historical_volatility(
    prices: List[float] = Body(..., description="Price history"),
    window: int = Body(20, ge=5, le=100),
):
    """
    Historical volatility (rolling).
    
    Standard deviation of log returns, annualized.
    """
    return quantlib_service.historical_volatility(
        prices=prices,
        window=window,
    )


@router.get("/status")
async def get_quantlib_status():
    """Get QuantLib service status"""
    return {
        "enabled": True,
        "modules_count": 18,
        "categories": ["options", "risk", "performance", "volatility", "simulation"],
        "status": "healthy",
    }