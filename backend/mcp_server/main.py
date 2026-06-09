"""
MCP Server for Jasper Trades
Enables external AI agents (Cursor, Claude Code, Codex) to control Jasper Trades.

22 MCP Tools:
1-4: Trading (place_order, cancel_order, get_positions, get_portfolio)
5-8: Backtesting (run_backtest, get_results, list_strategies, get_strategy)
9-12: Data (get_prices, get_news, get_signals, search_memories)
13-16: Agents (list_agents, start_agent, stop_agent, get_agent_status)
17-20: Risk (get_risk_metrics, assess_position, circuit_breaker_status, halt_trading)
21-22: System (health_check, get_settings)

Usage:
  uvx quantdinger-mcp  (or this MCP server)
  
Config:
  QUANTDINGER_BASE_URL=http://localhost:8000
  QUANTDINGER_AGENT_TOKEN=qd_agent_xxxxx
"""
from mcp.server.fastmcp import FastMCP
from mcp import types
import requests
import os
from typing import Optional, List, Dict, Any

# Configuration
BASE_URL = os.getenv("JASPER_BASE_URL", "http://localhost:8000")
AGENT_TOKEN = os.getenv("JASPER_AGENT_TOKEN", "")

# Create MCP server
mcp = FastMCP("Jasper Trades")

# Helper function
def make_request(endpoint: str, method: str = "GET", data: Optional[Dict] = None) -> Dict[str, Any]:
    """Make authenticated request to Jasper API."""
    url = f"{BASE_URL}{endpoint}"
    headers = {
        "Authorization": f"Bearer {AGENT_TOKEN}",
        "Content-Type": "application/json"
    }
    
    if method == "GET":
        response = requests.get(url, headers=headers, timeout=30)
    elif method == "POST":
        response = requests.post(url, headers=headers, json=data, timeout=30)
    elif method == "DELETE":
        response = requests.delete(url, headers=headers, timeout=30)
    else:
        raise ValueError(f"Unknown method: {method}")
    
    response.raise_for_status()
    return response.json()


# ========== TRADING TOOLS (1-4) ==========

@mcp.tool()
async def trading_place_order(
    symbol: str,
    side: str,
    quantity: float,
    order_type: str = "market",
    portfolio_id: Optional[int] = None
) -> Dict[str, Any]:
    """
    Place a trading order (paper or live).
    
    Args:
        symbol: Trading symbol (e.g., "AAPL", "BTC")
        side: "buy" or "sell"
        quantity: Number of shares/contracts
        order_type: "market", "limit", "stop", etc.
        portfolio_id: Portfolio to execute in (default: 1)
    
    Returns:
        Order confirmation with ID and status
    
    Safety:
        - Paper-only by default
        - Live trading requires explicit server unlock
        - All orders are audit-logged
    """
    return make_request("/api/v1/trading/execute", method="POST", data={
        "symbol": symbol,
        "side": side,
        "quantity": quantity,
        "order_type": order_type,
        "portfolio_id": portfolio_id or 1
    })


@mcp.tool()
async def trading_cancel_order(order_id: int) -> Dict[str, Any]:
    """
    Cancel a pending order.
    
    Args:
        order_id: Order ID to cancel
    
    Returns:
        Cancellation confirmation
    """
    return make_request(f"/api/v1/trading/{order_id}/cancel", method="POST")


@mcp.tool()
async def trading_get_positions(portfolio_id: int = 1) -> List[Dict[str, Any]]:
    """
    Get current positions in a portfolio.
    
    Args:
        portfolio_id: Portfolio ID
    
    Returns:
        List of positions with symbol, quantity, entry_price, current_price, pnl
    """
    return make_request(f"/api/v1/portfolio/{portfolio_id}/positions")


@mcp.tool()
async def trading_get_portfolio(portfolio_id: int = 1) -> Dict[str, Any]:
    """
    Get portfolio summary (cash, value, PnL).
    
    Args:
        portfolio_id: Portfolio ID
    
    Returns:
        Portfolio summary with cash, total_value, total_pnl, positions_count
    """
    return make_request(f"/api/v1/portfolio/{portfolio_id}")


# ========== BACKTESTING TOOLS (5-8) ==========

@mcp.tool()
async def backtest_run(
    strategy: str,
    symbol: str,
    start_date: str,
    end_date: str,
    initial_capital: float = 100000.0
) -> Dict[str, Any]:
    """
    Run a backtest for a strategy.
    
    Args:
        strategy: Strategy name
        symbol: Trading symbol
        start_date: Start date (YYYY-MM-DD)
        end_date: End date (YYYY-MM-DD)
        initial_capital: Starting capital
    
    Returns:
        Backtest results with returns, sharpe, drawdown, trades
    """
    return make_request("/api/v1/backtest/run", method="POST", data={
        "strategy": strategy,
        "symbol": symbol,
        "start_date": start_date,
        "end_date": end_date,
        "initial_capital": initial_capital
    })


@mcp.tool()
async def backtest_get_results(backtest_id: int) -> Dict[str, Any]:
    """
    Get backtest results by ID.
    
    Args:
        backtest_id: Backtest result ID
    
    Returns:
        Full backtest results with metrics and trade list
    """
    return make_request(f"/api/v1/backtest/{backtest_id}")


@mcp.tool()
async def backtest_list_strategies() -> List[Dict[str, Any]]:
    """
    List available backtest strategies.
    
    Returns:
        List of strategy names and descriptions
    """
    return make_request("/api/v1/backtest/strategies")


@mcp.tool()
async def backtest_get_strategy(strategy_name: str) -> Dict[str, Any]:
    """
    Get details of a specific strategy.
    
    Args:
        strategy_name: Strategy name
    
    Returns:
        Strategy details including parameters and logic
    """
    return make_request(f"/api/v1/backtest/strategies/{strategy_name}")


# ========== DATA TOOLS (9-12) ==========

@mcp.tool()
async def data_get_prices(
    symbol: str,
    start_date: str,
    end_date: str,
    timeframe: str = "1d"
) -> List[Dict[str, Any]]:
    """
    Get historical price data.
    
    Args:
        symbol: Trading symbol
        start_date: Start date (YYYY-MM-DD)
        end_date: End date (YYYY-MM-DD)
        timeframe: "1m", "5m", "15m", "1h", "1d", "1w"
    
    Returns:
        List of OHLCV bars
    """
    return make_request("/api/v1/market-data/prices", method="POST", data={
        "symbol": symbol,
        "start_date": start_date,
        "end_date": end_date,
        "timeframe": timeframe
    })


@mcp.tool()
async def data_get_news(symbol: Optional[str] = None, limit: int = 10) -> List[Dict[str, Any]]:
    """
    Get latest news.
    
    Args:
        symbol: Filter by symbol (optional)
        limit: Number of articles
    
    Returns:
        List of news articles with title, content, sentiment, timestamp
    """
    params = {"limit": limit}
    if symbol:
        params["symbol"] = symbol
    return make_request(f"/api/v1/news?{'&'.join(f'{k}={v}' for k,v in params.items())}")


@mcp.tool()
async def data_get_signals(
    symbol: Optional[str] = None,
    agent: Optional[str] = None,
    limit: int = 20
) -> List[Dict[str, Any]]:
    """
    Get AI trading signals.
    
    Args:
        symbol: Filter by symbol
        agent: Filter by agent name
        limit: Number of signals
    
    Returns:
        List of signals with action, confidence, reasoning
    """
    params = {"limit": limit}
    if symbol:
        params["symbol"] = symbol
    if agent:
        params["agent"] = agent
    return make_request(f"/api/v1/signals?{'&'.join(f'{k}={v}' for k,v in params.items())}")


@mcp.tool()
async def data_search_memories(
    query: str,
    category: Optional[str] = None,
    limit: int = 10
) -> List[Dict[str, Any]]:
    """
    Search persistent memories (cross-session knowledge).
    
    Args:
        query: Search query
        category: Filter by category
        limit: Max results
    
    Returns:
        List of matching memories with content and relevance
    """
    return make_request("/api/v1/memory/search", method="POST", data={
        "query": query,
        "category": category,
        "limit": limit
    })


# ========== AGENT TOOLS (13-16) ==========

@mcp.tool()
async def agents_list_agents() -> List[Dict[str, Any]]:
    """
    List all AI agents.
    
    Returns:
        List of agents with name, type, status, model
    """
    return make_request("/api/v1/agents")


@mcp.tool()
async def agents_start_agent(agent_name: str) -> Dict[str, Any]:
    """
    Start an AI agent.
    
    Args:
        agent_name: Agent name to start
    
    Returns:
        Agent status confirmation
    """
    return make_request(f"/api/v1/agents/{agent_name}/start", method="POST")


@mcp.tool()
async def agents_stop_agent(agent_name: str) -> Dict[str, Any]:
    """
    Stop an AI agent.
    
    Args:
        agent_name: Agent name to stop
    
    Returns:
        Agent stop confirmation
    """
    return make_request(f"/api/v1/agents/{agent_name}/stop", method="POST")


@mcp.tool()
async def agents_get_agent_status(agent_name: str) -> Dict[str, Any]:
    """
    Get agent status and performance.
    
    Args:
        agent_name: Agent name
    
    Returns:
        Agent status with is_active, total_signals, win_rate, pnl
    """
    return make_request(f"/api/v1/agents/{agent_name}")


# ========== RISK TOOLS (17-20) ==========

@mcp.tool()
async def risk_get_metrics(portfolio_id: int = 1) -> Dict[str, Any]:
    """
    Get portfolio risk metrics (VaR, drawdown, Sharpe).
    
    Args:
        portfolio_id: Portfolio ID
    
    Returns:
        Risk metrics including var_95, max_drawdown, sharpe_ratio
    """
    return make_request(f"/api/v1/risk/metrics?portfolio_id={portfolio_id}")


@mcp.tool()
async def risk_assess_position(
    symbol: str,
    quantity: float,
    entry_price: float
) -> Dict[str, Any]:
    """
    Assess risk for a potential position.
    
    Args:
        symbol: Trading symbol
        quantity: Position size
        entry_price: Entry price
    
    Returns:
        Risk assessment with risk_level, max_position_size, approval
    """
    return make_request("/api/v1/risk/assess", method="POST", data={
        "symbol": symbol,
        "quantity": quantity,
        "entry_price": entry_price
    })


@mcp.tool()
async def risk_circuit_breaker_status() -> Dict[str, Any]:
    """
    Get circuit breaker status (trading halt state).
    
    Returns:
        Status with state (IDLE/WARNING/HALTED), triggers, halted_at
    """
    return make_request("/api/v1/circuit-breaker/status")


@mcp.tool()
async def risk_halt_trading(reason: str) -> Dict[str, Any]:
    """
    Manually halt trading (circuit breaker).
    
    Args:
        reason: Reason for halt
    
    Returns:
        Halt confirmation
    """
    return make_request("/api/v1/circuit-breaker/halt", method="POST", data={
        "reason": reason
    })


# ========== SYSTEM TOOLS (21-22) ==========

@mcp.tool()
async def system_health_check() -> Dict[str, Any]:
    """
    Check system health status.
    
    Returns:
        Health status with all service states
    """
    return make_request("/api/v1/health")


@mcp.tool()
async def system_get_settings() -> Dict[str, Any]:
    """
    Get current system settings.
    
    Returns:
        Settings including model config, broker connections, features
    """
    return make_request("/api/v1/settings")


# Run MCP server
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Jasper Trades MCP Server")
    parser.add_argument("--transport", default="stdio", choices=["stdio", "streamable-http"])
    args = parser.parse_args()
    
    print(f"Starting Jasper Trades MCP Server (transport={args.transport})")
    print("Configure with:")
    print("  QUANTDINGER_BASE_URL=http://localhost:8000")
    print("  QUANTDINGER_AGENT_TOKEN=your_token_here")
    print()
    mcp.run(transport=args.transport)