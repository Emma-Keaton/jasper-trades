"""Signal Source package: scrapers + tip extraction."""
from .registry import get_registry, SignalSourceRegistry

__all__ = ["get_registry", "SignalSourceRegistry"]
