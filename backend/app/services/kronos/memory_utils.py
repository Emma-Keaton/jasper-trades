"""
Kronos Integration for 4GB RAM Systems
Memory-optimized time-series forecasting service.
"""

# Memory management utilities
import gc
import psutil
import torch
from typing import Optional, Dict, Any, List
from datetime import datetime
import structlog

logger = structlog.get_logger(__name__)


def get_memory_usage() -> Dict[str, Any]:
    """Get current memory usage statistics."""
    process = psutil.Process()
    mem_info = process.memory_info()
    
    return {
        "rss_mb": mem_info.rss / (1024 * 1024),  # Resident Set Size
        "vms_mb": mem_info.vms / (1024 * 1024),  # Virtual Memory Size
        "percent": process.memory_percent(),
        "system_available_mb": psutil.virtual_memory().available / (1024 * 1024),
        "system_total_mb": psutil.virtual_memory().total / (1024 * 1024),
        "system_percent": psutil.virtual_memory().percent,
    }


def force_gc():
    """Aggressively free memory."""
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()


def set_memory_limits(max_ram_mb: int = 2048):
    """
    Set aggressive memory limits for Python process.
    
    Args:
        max_ram_mb: Maximum RAM usage in MB (default 2GB for 4GB system)
    """
    try:
        import resource
        # Set soft limit to max_ram_mb
        soft, hard = resource.getrlimit(resource.RLIMIT_AS)
        resource.setrlimit(resource.RLIMIT_AS, (max_ram_mb * 1024 * 1024, hard))
        logger.info(f"Set memory limit to {max_ram_mb}MB")
    except Exception as e:
        logger.warning(f"Could not set memory limit: {e}")


def configure_torch_cpu():
    """
    Configure PyTorch for CPU-only, low-memory operation.
    Critical for 4GB RAM systems.
    """
    # Force CPU usage (no GPU memory overhead)
    torch.set_num_threads(2)  # Limit CPU threads
    torch.set_num_interop_threads(1)
    
    # Disable MKL/DNNL (reduces memory footprint)
    torch.backends.mkldnn.enabled = False
    
    # Set default tensor type to float32 (not float64)
    torch.set_default_dtype(torch.float32)
    
    logger.info("Configured PyTorch for CPU-only, low-memory operation")


# Global memory state
_memory_monitoring_enabled = True
_memory_threshold_percent = 85.0  # Pause if RAM > 85%


def check_memory_safe() -> bool:
    """
    Check if it's safe to proceed with memory-intensive operation.
    
    Returns:
        True if memory usage is below threshold
    """
    if not _memory_monitoring_enabled:
        return True
    
    usage = get_memory_usage()
    is_safe = usage["system_percent"] < _memory_threshold_percent
    
    if not is_safe:
        logger.warning(f"Memory usage at {usage['system_percent']:.1f}% - pausing Kronos inference")
    
    return is_safe


def wait_for_memory(min_free_percent: float = 5.0, max_wait_sec: int = 60):
    """
    Wait until memory usage drops below threshold.
    
    Args:
        min_free_percent: Minimum free RAM percentage to wait for
        max_wait_sec: Maximum time to wait
    """
    import time
    
    start_time = time.time()
    while time.time() - start_time < max_wait_sec:
        usage = get_memory_usage()
        if usage["system_percent"] < (100 - min_free_percent):
            return
        time.sleep(2)
    
    logger.warning(f"Timed out waiting for memory, proceeding anyway")