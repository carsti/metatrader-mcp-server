from typing import List, Optional, Sequence, Union
import pandas as pd
from datetime import datetime, timezone, timedelta
import MetaTrader5 as mt5
from ..types import Timeframe
from ..exceptions import SymbolNotFoundError, InvalidTimeframeError, MarketDataError
from .get_symbols import get_symbols
from ._candles_common import CandleResult, combine, normalize_list, validate_group


def get_candles_by_date(
    connection,
    symbol_name: Union[str, Sequence[str]],
    timeframe: Union[str, Sequence[str]],
    from_date: Optional[Union[str, datetime]] = None,
    to_date: Optional[Union[str, datetime]] = None,
    group: Optional[str] = None,
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

    Returns:
        pd.DataFrame: Candles, with 'symbol' and/or 'timeframe' columns added
        only for the dimensions that vary. ``df.attrs['errors']`` lists the
        pairs that failed.

    Raises:
        Any per-pair error, if every pair failed.
    """
    symbols = normalize_list(symbol_name)
    timeframes = normalize_list(timeframe)
    group = validate_group(group)

    # Parse once up front: a bad date is a request-level error, not a per-pair one.
    from_datetime = parse_date(from_date) if from_date else None
    to_datetime = parse_date(to_date, is_to_date=True) if to_date else None
    if from_datetime and to_datetime and from_datetime > to_datetime:
        from_datetime, to_datetime = to_datetime, from_datetime

    results: List[CandleResult] = []
    for symbol in symbols:
        for tf_name in timeframes:
            try:
                frame = _fetch_one(connection, symbol, tf_name, from_datetime, to_datetime)
                results.append(CandleResult(symbol, tf_name, frame, None))
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
    connection,
    symbol_name: str,
    timeframe: str,
    from_datetime: Optional[datetime],
    to_datetime: Optional[datetime],
) -> pd.DataFrame:
    """Fetch the candles of a single symbol and timeframe over the given range."""
    if not get_symbols(connection, symbol_name):
        raise SymbolNotFoundError(f"Symbol '{symbol_name}' not found")
    tf = Timeframe.get(timeframe)
    if tf is None:
        raise InvalidTimeframeError(f"Invalid timeframe: '{timeframe}'")
    if from_datetime and to_datetime:
        candles = mt5.copy_rates_range(symbol_name, tf, from_datetime, to_datetime)
    elif from_datetime:
        candles = mt5.copy_rates_from(symbol_name, tf, from_datetime, 1000)
    elif to_datetime:
        lookback_days = 30
        start_date = to_datetime - timedelta(days=lookback_days)
        candles = mt5.copy_rates_range(symbol_name, tf, start_date, to_datetime)
    else:
        candles = mt5.copy_rates_from_pos(symbol_name, tf, 0, 1000)
    if candles is None or len(candles) == 0:
        raise MarketDataError(f"Failed to retrieve historical data for symbol '{symbol_name}' with timeframe '{timeframe}'")
    df = pd.DataFrame(candles)
    df['time'] = pd.to_datetime(df['time'], unit='s', utc=True)
    df = df.sort_values('time', ascending=False)
    return df
