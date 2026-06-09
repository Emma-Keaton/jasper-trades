"""
Brokers Module - Unified interface for all trading brokers.
Lazy-load IBKR to avoid Python 3.14 compatibility issues with ib_insync
"""
from app.brokers.base import BaseBrokerService, OrderResult, PositionData, AccountData
from app.brokers.alpaca_service import AlpacaBrokerService
from app.brokers.ccxt_service import CCXTBrokerService
from app.brokers.solana_service import SolanaBrokerService
from app.brokers.registry import (
    BrokerRegistry,
    broker_registry,
    initialize_brokers,
    get_broker,
    get_broker_for_asset,
)

# Lazy load IBKR to avoid eventkit issues on Python 3.14
def get_ibkr_service():
    """Lazy load IBKR service to avoid import-time event loop issues"""
    try:
        from app.brokers.ibkr_service import IBKRBrokerService
        return IBKRBrokerService
    except RuntimeError as e:
        if "event loop" in str(e):
            return None
        raise

__all__ = [
    "BaseBrokerService",
    "OrderResult",
    "PositionData",
    "AccountData",
    "AlpacaBrokerService",
    "CCXTBrokerService",
    "SolanaBrokerService",
    "get_ibkr_service",
    "BrokerRegistry",
    "broker_registry",
    "initialize_brokers",
    "get_broker",
    "get_broker_for_asset",
]