from typing import Optional
import pandas as pd
import logging
from .get_orders import get_orders
from ..exceptions import OrdersHistoryError
from ..utils import validate_limit

logger = logging.getLogger("MT5History")

# mt5 returns 24 fields per historical order. These are the ones that inform a
# decision; the rest are millisecond twins of a field already present, zero for
# a completed order ('volume_current', 'price_stoplimit', 'time_expiration'),
# constant for manual trading ('magic'), or broker-internal. Pass full=True to
# get them all.
ORDER_COLUMNS = (
    "ticket",
    "time_done",
    "symbol",
    "type",
    "state",
    "volume_initial",
    "price_open",
    "sl",
    "tp",
    "position_id",
    "comment",
)


DEFAULT_LIMIT = 500


def get_orders_as_dataframe(
    connection,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    group: Optional[str] = None,
    full: bool = False,
    limit: int = DEFAULT_LIMIT,
) -> pd.DataFrame:
    """
    Get historical orders as a pandas DataFrame, newest first, indexed by setup time.

    Args:
        connection: MT5 connection object
        from_date: Start of the range (default: 30 days ago)
        to_date: End of the range (default: now)
        group: Symbol filter pattern
        full: Return every field mt5 provides instead of ORDER_COLUMNS (default: False)
        limit: Maximum rows, keeping the most recent (default: 500)

    Returns:
        pd.DataFrame: Orders indexed by 'time_setup'. When rows were dropped to
        fit `limit`, ``df.attrs['truncated']`` carries {'returned', 'available'}.

    Raises:
        ValueError: If limit is not a positive integer.
    """
    limit = validate_limit(limit)

    try:
        orders = get_orders(connection, from_date, to_date, group)
        if not orders:
            logger.info("No orders found, returning empty DataFrame.")
            return pd.DataFrame()
        df = pd.DataFrame(orders)
        for col in ['time_setup', 'time_done', 'time_expiration']:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], unit='s')
        if 'time_setup' in df.columns:
            df.set_index('time_setup', inplace=True)
            df = df.sort_index(ascending=False)
        if not full:
            df = df[[column for column in ORDER_COLUMNS if column in df.columns]]
        available = len(df)
        df = df.head(limit)
        df.attrs["truncated"] = (
            [{"returned": len(df), "available": available}] if available > len(df) else []
        )
        logger.debug(f"Created DataFrame with {len(df)} orders.")
        return df
    except OrdersHistoryError:
        raise
    except Exception as e:
        msg = f"Error creating DataFrame from orders: {str(e)}"
        logger.error(msg)
        raise OrdersHistoryError(msg)
