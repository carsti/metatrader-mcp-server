from typing import Dict, Any, List, Optional, Union
from datetime import datetime, timedelta
import logging

import MetaTrader5 as mt5  # type: ignore
# pylint: disable=no-member
from ..exceptions import DealsHistoryError, ConnectionError

logger = logging.getLogger("MT5History")


def _parse_date_arg(value: Union[str, datetime], *, end_of_day: bool = False) -> datetime:
    """Parse a date/datetime argument for a history query.

    Accepts a date-only string ('YYYY-MM-DD'), an ISO datetime
    ('YYYY-MM-DD HH:MM:SS' or 'YYYY-MM-DDTHH:MM:SS'), or a datetime object
    (passed through unchanged).

    A date-only value is taken as the START of that day for a lower bound
    (from_date) or the END of that day (23:59:59) for an upper bound (to_date),
    so that to_date='YYYY-MM-DD' INCLUDES the whole named day. history_deals_get's
    date_to upper bound is inclusive in practice (a deal whose time equals date_to
    is returned) -- MT5's observed behavior, not spelled out in the MQL5 docs --
    and the previous code parsed to_date at midnight (00:00:00), which excluded
    every deal that occurred during the named day. Accepting an explicit time also
    lets callers bound a query precisely.
    """
    if not isinstance(value, str):
        return value
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            pass
    parsed = datetime.strptime(value, "%Y-%m-%d")  # date-only
    if end_of_day:
        parsed = parsed.replace(hour=23, minute=59, second=59)
    return parsed


def get_deals(
    connection,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    group: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Get historical deals.
    """
    if not connection.is_connected():
        raise ConnectionError("Not connected to MetaTrader 5 terminal.")
    deals = None
    logger.debug(f"Retrieving deals with parameters: from_date={from_date}, to_date={to_date}, group={group}")
    
    try:
        if from_date is None:
            from_date = datetime.now() - timedelta(days=30)
        else:
            from_date = _parse_date_arg(from_date, end_of_day=False)

        if to_date is None:
            to_date = datetime.now()
        else:
            to_date = _parse_date_arg(to_date, end_of_day=True)

        logger.debug(f"Retrieving deals by date range: {from_date} to {to_date}")
        if group is not None:
            deals = mt5.history_deals_get(from_date, to_date, group=group)
        else:
            deals = mt5.history_deals_get(from_date, to_date)
    except Exception as e:
        error_code = -1
        if hasattr(mt5, 'last_error'):
            error = mt5.last_error()
            if error and len(error) > 1:
                error_code = error[0]
        msg = f"Failed to retrieve deals history: {str(e)}"
        logger.error(msg)
        raise DealsHistoryError(msg, error_code)
    if deals is None:
        error = mt5.last_error()
        msg = f"Failed to retrieve deals history: {error[1]}"
        logger.error(msg)
        raise DealsHistoryError(msg, error[0])
    if len(deals) == 0:
        logger.info("No deals found with the specified parameters.")
        return []
    result = [deal._asdict() for deal in deals]
    logger.debug(f"Retrieved {len(result)} deals.")
    return result
