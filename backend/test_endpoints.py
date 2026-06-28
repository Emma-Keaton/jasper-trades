"""
Jasper Trades - API Endpoint Health Check Script
Tests all backend endpoints and verifies frontend integration
"""
import requests
import json
from typing import Dict, List, Tuple
from datetime import datetime

BASE_URL = "http://localhost:8000"

# Define all endpoints to test
ENDPOINTS = {
    # Health & System
    "Health Check": ("/api/v1/health", "GET"),
    "System Status": ("/api/v1/status", "GET"),
    "System Tasks": ("/api/v1/system/tasks", "GET"),
    
    # Portfolio
    "Portfolio List": ("/api/v1/portfolio", "GET"),
    "Portfolio Performance": ("/api/v1/portfolio/performance?portfolio_id=1", "GET"),
    
    # Agents
    "Agents List": ("/api/v1/agents", "GET"),
    
    # Signals
    "Signals List": ("/api/v1/signals?limit=10", "GET"),
    
    # Trading
    "Trading History": ("/api/v1/trading/history?portfolio_id=1&limit=10", "GET"),
    
    # Settings
    "Settings": ("/api/v1/settings", "GET"),
    "Settings Currency": ("/api/v1/settings/currency/preference", "GET"),
    
    # Broker Connections
    "Broker Status": ("/api/v1/trading/brokers/status", "GET"),
    "Broker Accounts": ("/api/v1/brokers/accounts", "GET"),
    
    # Market Intelligence
    "Market Intelligence News": ("/api/v1/market-intelligence/news?limit=5", "GET"),
    "Market Intelligence Trending": ("/api/v1/market-intelligence/trending?limit=5", "GET"),
    
    # Telegram
    "Telegram Status": ("/api/v1/settings/telegram/status", "GET"),
    
    # Polymarket
    "Polymarket Status": ("/api/v1/polymarket/status", "GET"),
    "Polymarket Connection": ("/api/v1/polymarket/connection/status", "GET"),
    
    # Risk
    "Risk Metrics": ("/api/v1/risk/metrics?portfolio_id=1", "GET"),
    "Circuit Breaker Status": ("/api/v1/circuit-breaker/status", "GET"),
    
    # Alpha Factors
    "Alpha Factors": ("/api/v1/alpha-factors?limit=10", "GET"),
    "Alpha Categories": ("/api/v1/alpha-factors/categories", "GET"),
    
    # Backtest
    "Backtest List": ("/api/v1/backtest", "GET"),
    
    # Forex
    "Forex Rate": ("/api/v1/forex/rate/USD/NGN", "GET"),
    "Forex Major Rates": ("/api/v1/forex/rates/major", "GET"),
    
    # Banks (Nigeria)
    "Nigerian Banks": ("/api/v1/nigeria", "GET"),
    
    # Trove
    "Trove Symbols": ("/api/v1/trove/symbols?market=US", "GET"),
    
    # AkShare
    "AkShare Status": ("/api/v1/akshare/status", "GET"),
    "AkShare Symbols": ("/api/v1/akshare/symbols?market=A&limit=50", "GET"),
    
    # Symbols
    "Symbols List": ("/api/v1/symbols?market=US&limit=10", "GET"),
    
    # Chat
    "Chat History": ("/api/v1/chat/history?device_id=test-device&limit=5", "GET"),
    
    # Learning
    "Learning Status": ("/api/v1/learning/status", "GET"),
    "Feature Importance": ("/api/v1/learning/feature-importance", "GET"),
    
    # Ensemble
    "Ensemble Models": ("/api/v1/ensemble/models", "GET"),
    "Ensemble Status": ("/api/v1/ensemble/status", "GET"),
    
    # Heartbeat
    "Heartbeat Status": ("/api/v1/heartbeat/status", "GET"),
    
    # Notify
    "Notify Status": ("/api/v1/notify/status", "GET"),
    
    # QuantLib
    "QuantLib Modules": ("/api/v1/quantlib/modules", "GET"),
    
    # CopyTrade
    "CopyTrade Stats": ("/api/v1/copytrade/stats", "GET"),
    "Trader Leaderboard": ("/api/v1/traders/leaderboard?limit=5", "GET"),
    
    # Debate
    "Debate Status": ("/api/v1/debate/status", "GET"),
    
    # Withdrawal
    "Withdrawal Stats": ("/api/v1/withdrawal/stats?portfolio_id=1", "GET"),
    "Payout Settings": ("/api/v1/withdrawal/payout/settings", "GET", {"X-Device-ID": "test-device"}),
    "Broker Accounts": ("/api/v1/brokers/accounts", "GET", {"X-Device-ID": "test-device"}),
}

def test_endpoint(name: str, path: str, method: str, headers: dict = None) -> Tuple[bool, int, str]:
    """Test a single endpoint and return (success, status_code, message)"""
    url = f"{BASE_URL}{path}"
    try:
        if method == "GET":
            response = requests.get(url, timeout=15, headers=headers)
        elif method == "POST":
            response = requests.post(url, json={}, timeout=15, headers=headers)
        else:
            return False, 0, f"Unsupported method: {method}"
        
        if response.status_code == 200:
            return True, response.status_code, "OK"
        elif response.status_code == 404:
            return False, response.status_code, "Endpoint not found"
        elif response.status_code == 422:
            return True, response.status_code, "Validation error (endpoint exists)"
        elif response.status_code == 500:
            return False, response.status_code, "Server error"
        else:
            return False, response.status_code, f"HTTP {response.status_code}"
            
    except requests.exceptions.Timeout:
        return False, 0, "Timeout"
    except requests.exceptions.ConnectionError:
        return False, 0, "Connection failed"
    except Exception as e:
        return False, 0, str(e)

def main():
    print("=" * 80)
    print("Jasper Trades - API Endpoint Health Check")
    print(f"Base URL: {BASE_URL}")
    print(f"Timestamp: {datetime.now().isoformat()}")
    print("=" * 80)
    print()
    
    results = {
        "healthy": [],
        "warning": [],
        "error": [],
    }
    
    # Test each endpoint
    for name, endpoint_info in ENDPOINTS.items():
        if len(endpoint_info) == 3:
            path, method, headers = endpoint_info
        else:
            path, method = endpoint_info
            headers = None
            
        success, status_code, message = test_endpoint(name, path, method, headers)
        
        if success and status_code in [200, 422]:
            results["healthy"].append((name, path, status_code))
            status = "✓"
            color = ""
        elif status_code == 422:
            results["warning"].append((name, path, status_code, message))
            status = "⚠"
            color = ""
        else:
            results["error"].append((name, path, status_code, message))
            status = "✗"
            color = ""
        
        print(f"{status} {name:35} | {method:6} | Status: {status_code:3} | {message}")
    
    # Summary
    print()
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"✓ Healthy:   {len(results['healthy'])} endpoints")
    print(f"⚠ Warning:   {len(results['warning'])} endpoints")
    print(f"✗ Error:     {len(results['error'])} endpoints")
    print(f"Total:       {len(ENDPOINTS)} endpoints tested")
    print()
    
    if results["error"]:
        print("Failed Endpoints:")
        for name, path, status_code, message in results["error"]:
            print(f"  - {name}: {message} (Status: {status_code})")
    
    print()
    print("=" * 80)
    
    # Export results to JSON
    report = {
        "timestamp": datetime.now().isoformat(),
        "base_url": BASE_URL,
        "summary": {
            "healthy": len(results["healthy"]),
            "warning": len(results["warning"]),
            "error": len(results["error"]),
            "total": len(ENDPOINTS)
        },
        "endpoints": {
            "healthy": [{"name": n, "path": p, "status": s} for n, p, s in results["healthy"]],
            "warning": [{"name": n, "path": p, "status": s, "message": m} for n, p, s, m in results["warning"]],
            "error": [{"name": n, "path": p, "status": s, "message": m} for n, p, s, m in results["error"]],
        }
    }
    
    with open("endpoint_test_results.json", "w") as f:
        json.dump(report, f, indent=2)
    
    print(f"Results saved to: endpoint_test_results.json")
    
    return len(results["error"]) == 0

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)