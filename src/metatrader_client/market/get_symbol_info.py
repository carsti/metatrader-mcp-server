from typing import Any, Dict
import MetaTrader5 as mt5
from ..exceptions import SymbolNotFoundError

# mt5's SymbolInfo carries dozens of attributes, most of which say nothing about
# how to trade the instrument. These are what sizing, precision, limits and cost
# decisions need. Pass full=True for the whole struct.
SYMBOL_INFO_FIELDS = (
    "name",
    "description",
    "currency_base",
    "currency_profit",
    "currency_margin",
    "digits",
    "point",
    "spread",
    "trade_mode",
    "trade_stops_level",
    "volume_min",
    "volume_max",
    "volume_step",
    "trade_contract_size",
    "trade_tick_size",
    "trade_tick_value",
    "swap_long",
    "swap_short",
    "visible",
    "path",
)


def get_symbol_info(connection, symbol_name: str, full: bool = False) -> Dict[str, Any]:
    """Get information about a trading symbol.

    Args:
        connection: MT5 connection object
        symbol_name: The symbol to describe (e.g. 'EURUSD')
        full: Return every attribute of the SDK struct instead of
            SYMBOL_INFO_FIELDS (default: False)

    Returns:
        Dict[str, Any]: The symbol's fields. Fields the broker does not expose
        are omitted rather than returned as None.

    Raises:
        SymbolNotFoundError: If the symbol does not exist.
    """
    symbols = mt5.symbols_get(symbol_name)
    if not symbols or len(symbols) == 0:
        raise SymbolNotFoundError(f"Symbol '{symbol_name}' not found")
    symbol_info = symbols[0]

    if full:
        return {
            attr: getattr(symbol_info, attr)
            for attr in dir(symbol_info)
            if not attr.startswith('__') and not callable(getattr(symbol_info, attr))
        }

    return {
        field: getattr(symbol_info, field)
        for field in SYMBOL_INFO_FIELDS
        if hasattr(symbol_info, field)
    }
