import time
from typing import Dict, List, Optional, Tuple
import MetaTrader5 as mt5

# mt5.symbols_get marshals a full SymbolInfo struct per symbol across the IPC
# boundary, and this function only reads the names off them. Brokers commonly
# expose thousands of symbols and the list does not change within a session, so
# results are held briefly. The TTL keeps a reconnect to a different account
# from serving a stale list for long.
CACHE_TTL_SECONDS = 60.0

_cache: Dict[Optional[str], Tuple[float, List[str]]] = {}


def get_symbols(connection, group: Optional[str] = None, use_cache: bool = True) -> List[str]:
    """
    Get list of all available market symbols.
    Args:
        connection: MT5Connection instance (not used directly, but kept for API consistency)
        group: Filter symbols by group pattern (e.g., "*USD*" for USD pairs).
        use_cache: Serve from the session cache when a fresh entry exists (default: True).
    Returns:
        List[str]: List of symbol names matching the filter criteria.
    """
    if use_cache:
        cached = _cache.get(group)
        if cached is not None and (time.monotonic() - cached[0]) < CACHE_TTL_SECONDS:
            return list(cached[1])

    symbols = mt5.symbols_get() if group is None else mt5.symbols_get(group)
    names = [symbol.name for symbol in symbols] if symbols else []
    _cache[group] = (time.monotonic(), names)
    return list(names)


def clear_symbols_cache() -> None:
    """Drop every cached symbol list. Call on connect/disconnect."""
    _cache.clear()
