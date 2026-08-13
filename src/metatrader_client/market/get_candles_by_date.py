from typing import List, Optional, Sequence, Tuple, Union
import pandas as pd
from datetime import datetime, timezone, timedelta
import MetaTrader5 as mt5
from ..exceptions import MarketDataError
from ._candles_common import (
    CandleResult,
    combine,
    normalize_list,
    validate_group,
    validate_limit,
    validate_symbols,
    validate_timeframes,
)

DEFAULT_LIMIT = 100
OPEN_ENDED_LOOKBACK_DAYS = 30


def get_candles_by_date(
    connection,
    symbol_name: Union[str, Sequence[str]],
    timeframe: Union[str, Sequence[str]],
    from_date: Optional[Union[str, datetime]] = None,
    to_date: Optional[Union[str, datetime]] = None,
    group: Optional[str] = None,
    limit: int = DEFAULT_LIMIT,
) -> pd.DataFrame:
    """Get candles in a date range for one or more symbols and timeframes.

    Args:
        connection: MT5 connection object
        symbol_name: Symbol, or list of symbols (e.g. 'EURUSD' or ['EURUSD', 'GBPUSD'])
        timeframe: Timeframe, or list of timeframes (e.g. 'H1' or ['H1', 'M15'])
        from_date: Start of the range, 'YYYY-MM-DD', 'YYYY-MM-DD HH:MM' or datetime
        to_date: End of the range, same formats as from_date
        group: Row grouping when both lists have more than one entry -
            'timeframe', 'symbol' or 'none' (default: 'none')
        limit: Maximum candles per (symbol, timeframe) pair, most recent first
            (default: 100). The total row count is limit x symbols x timeframes.

    Returns:
        pd.DataFrame: Candles, with 'symbol' and/or 'timeframe' columns added
        only for the dimensions that vary. ``df.attrs['errors']`` lists the
        pairs that failed and ``df.attrs['truncated']`` the pairs that had more
        candles available than `limit` allowed.

    Raises:
        ValueError: Unparseable date, empty symbol/timeframe list, bad group, or
            non-positive limit.
        Any per-pair error, if every pair failed.
    """
    symbols = normalize_list(symbol_name)
    timeframes = normalize_list(timeframe)
    group = validate_group(group)
    limit = validate_limit(limit)

    # Parse once up front: a bad date is a request-level error, not a per-pair one.
    from_datetime = parse_date(from_date) if from_date else None
    to_datetime = parse_date(to_date, is_to_date=True) if to_date else None
    if from_datetime and to_datetime and from_datetime > to_datetime:
        from_datetime, to_datetime = to_datetime, from_datetime

    # Resolved once each, rather than once per pair: a symbol lookup is an IPC
    # round-trip that marshals full symbol structs.
    symbol_errors = validate_symbols(connection, symbols)
    timeframe_codes, timeframe_errors = validate_timeframes(timeframes)

    results: List[CandleResult] = []
    for symbol in symbols:
        for tf_name in timeframes:
            known_error = symbol_errors.get(symbol) or timeframe_errors.get(tf_name)
            if known_error is not None:
                results.append(CandleResult(symbol, tf_name, None, known_error))
                continue
            try:
                frame, available = _fetch_one(
                    symbol, tf_name, timeframe_codes[tf_name], from_datetime, to_datetime, limit
                )
                results.append(CandleResult(symbol, tf_name, frame, None, available))
            except Exception as error:  # collected, then re-raised if nothing succeeds
                results.append(CandleResult(symbol, tf_name, None, error))

    return combine(results, symbols, timeframes, group)


def parse_date(date_str, is_to_date=False):
    """Coerce a date string or datetime into a UTC-aware datetime.

    A bare 'YYYY-MM-DD' is widened to cover the whole day: start of day for a
    range start, end of day for a range end.
    """
    if isinstance(date_str, datetime):
        if date_str.tzinfo is None:
            return date_str.replace(tzinfo=timezone.utc)
        return date_str
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(date_str, fmt)
            if fmt == "%Y-%m-%d":
                if is_to_date:
                    dt = dt.replace(hour=23, minute=59)
                else:
                    dt = dt.replace(hour=0, minute=0)
            return dt.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    raise ValueError(f"Invalid date format: {date_str}. Expected 'yyyy-MM-dd' or 'yyyy-MM-dd HH:mm'")


def _fetch_one(
    symbol_name: str,
    timeframe: str,
    tf_code,
    from_datetime: Optional[datetime],
    to_datetime: Optional[datetime],
    limit: int,
) -> Tuple[pd.DataFrame, int]:
    """Fetch one symbol and timeframe over the range, capped at `limit` rows.

    Returns:
        Tuple[pd.DataFrame, int]: the candles, and how many were available
        before the limit was applied.
    """
    if from_datetime and to_datetime:
        # A range has no natural size, so it is fetched whole and trimmed below.
        candles = mt5.copy_rates_range(symbol_name, tf_code, from_datetime, to_datetime)
    elif from_datetime:
        candles = mt5.copy_rates_from(symbol_name, tf_code, from_datetime, limit)
    elif to_datetime:
        start_date = to_datetime - timedelta(days=OPEN_ENDED_LOOKBACK_DAYS)
        candles = mt5.copy_rates_range(symbol_name, tf_code, start_date, to_datetime)
    else:
        candles = mt5.copy_rates_from_pos(symbol_name, tf_code, 0, limit)
    if candles is None or len(candles) == 0:
        raise MarketDataError(f"Failed to retrieve historical data for symbol '{symbol_name}' with timeframe '{timeframe}'")
    df = pd.DataFrame(candles)
    df['time'] = pd.to_datetime(df['time'], unit='s', utc=True)
    df = df.sort_values('time', ascending=False)
    available = len(df)
    return df.head(limit), available
