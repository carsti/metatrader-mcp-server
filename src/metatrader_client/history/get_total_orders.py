from typing import Optional
from datetime import datetime
import logging

try:
    import MetaTrader5 as mt5
except ImportError:
    raise ImportError("MetaTrader5 package is not installed. Please install it with: pip install MetaTrader5")

from ..exceptions import OrdersHistoryError, ConnectionError
from ._time_window import normalize_window

logger = logging.getLogger("MT5History")

def get_total_orders(
    connection,
    from_date: Optional[datetime] = None,
    to_date: Optional[datetime] = None
) -> int:
    """
    Get total number of orders in history.
    """
    if not connection.is_connected():
        raise ConnectionError("Not connected to MetaTrader 5 terminal.")
    logger.debug(f"Retrieving total orders count with parameters: from_date={from_date}, to_date={to_date}")
    from_date, to_date = normalize_window(from_date, to_date)
    total = mt5.history_orders_total(from_date, to_date)
    if total is None:
        error = mt5.last_error()
        msg = f"Failed to retrieve orders count: {error[1]}"
        logger.error(msg)
        raise OrdersHistoryError(msg, error[0])
    logger.debug(f"Retrieved total orders count: {total}")
    return total
