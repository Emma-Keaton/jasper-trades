"""
Brokers Module - Unified interface for all trading brokers.
"""
from app.brokers.base import BaseBrokerService, OrderResult, PositionData, AccountData
from app.brokers.ccxt_service import CCXTBrokerService
from app.brokers.solana_service import SolanaBrokerService
from app.brokers.registry import (
    BrokerRegistry,
    broker_registry,
    initialize_brokers,
    get_broker,
    get_broker_for_asset,
)

__all__ = [
    "BaseBrokerService",
    "OrderResult",
    "PositionData",
    "AccountData",
    "CCXTBrokerService",
    "SolanaBrokerService",
    "BrokerRegistry",
    "broker_registry",
    "initialize_brokers",
    "get_broker",
    "get_broker_for_asset",
]