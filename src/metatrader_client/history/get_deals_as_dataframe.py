from typing import Optional
from datetime import datetime
import pandas as pd
import logging
from .get_deals import get_deals
from ..exceptions import DealsHistoryError
from ..utils import validate_limit

logger = logging.getLogger("MT5History")

# mt5 returns 18 fields per deal. These are the ones that inform a decision;
# the rest are redundant with another field ('order' with 'position_id',
# 'time_msc' with the index), constant for manual trading ('magic', 'fee'), or
# broker-internal ('reason', 'external_id'). Pass full=True to get them all.
DEAL_COLUMNS = (
    "ticket",
    "symbol",
    "type",
    "entry",
    "position_id",
    "volume",
    "price",
    "commission",
    "swap",
    "profit",
    "comment",
)


DEFAULT_LIMIT = 500


def get_deals_as_dataframe(
    connection,
    from_date: Optional[datetime] = None,
    to_date: Optional[datetime] = None,
    group: Optional[str] = None,
    full: bool = False,
    limit: int = DEFAULT_LIMIT,
) -> pd.DataFrame:
    """
    Get historical deals as a pandas DataFrame, newest first, indexed by time.

    Args:
        connection: MT5 connection object
        from_date: Start of the range (default: 30 days ago)
        to_date: End of the range (default: now)
        group: Symbol filter pattern
        full: Return every field mt5 provides instead of DEAL_COLUMNS (default: False)
        limit: Maximum rows, keeping the most recent (default: 500)

    Returns:
        pd.DataFrame: Deals indexed by 'time'. When rows were dropped to fit
        `limit`, ``df.attrs['truncated']`` carries {'returned', 'available'}.

    Raises:
        ValueError: If limit is not a positive integer.
    """
    limit = validate_limit(limit)

    try:
        deals = get_deals(connection, from_date, to_date, group)
        if not deals:
            logger.info("No deals found, returning empty DataFrame.")
            return pd.DataFrame()
        df = pd.DataFrame(deals)
        if 'time' in df.columns:
            df['time'] = pd.to_datetime(df['time'], unit='s')
            df.set_index('time', inplace=True)
            df = df.sort_index(ascending=False)
        if not full:
            df = df[[column for column in DEAL_COLUMNS if column in df.columns]]
        available = len(df)
        df = df.head(limit)
        df.attrs["truncated"] = (
            [{"returned": len(df), "available": available}] if available > len(df) else []
        )
        logger.debug(f"Created DataFrame with {len(df)} deals.")
        return df
    except DealsHistoryError:
        raise
    except Exception as e:
        msg = f"Error creating DataFrame from deals: {str(e)}"
        logger.error(msg)
        raise DealsHistoryError(msg)
