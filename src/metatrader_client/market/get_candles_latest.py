from typing import List, Optional, Sequence, Union
import pandas as pd
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


def get_candles_latest(
    connection,
    symbol_name: Union[str, Sequence[str]],
    timeframe: Union[str, Sequence[str]],
    count: int = 100,
    group: Optional[str] = None,
) -> pd.DataFrame:
    """Get the latest N candles for one or more symbols and timeframes.

    Args:
        connection: MT5 connection object
        symbol_name: Symbol, or list of symbols (e.g. 'EURUSD' or ['EURUSD', 'GBPUSD'])
        timeframe: Timeframe, or list of timeframes (e.g. 'H1' or ['H1', 'M15'])
        count: Number of candles per (symbol, timeframe) pair (default: 100).
            The total row count is count x symbols x timeframes.
        group: Row grouping when both lists have more than one entry -
            'timeframe', 'symbol' or 'none' (default: 'none')

    Returns:
        pd.DataFrame: Candles, with 'symbol' and/or 'timeframe' columns added
        only for the dimensions that vary. ``df.attrs['errors']`` lists the
        pairs that failed.

    Raises:
        ValueError: Empty symbol/timeframe list, bad group, or non-positive count.
        Any per-pair error, if every pair failed.
    """
    symbols = normalize_list(symbol_name)
    timeframes = normalize_list(timeframe)
    group = validate_group(group)
    count = validate_limit(count)

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
                frame = _fetch_one(symbol, tf_name, timeframe_codes[tf_name], count)
                results.append(CandleResult(symbol, tf_name, frame, None))
            except Exception as error:  # collected, then re-raised if nothing succeeds
                results.append(CandleResult(symbol, tf_name, None, error))

    return combine(results, symbols, timeframes, group)


def _fetch_one(symbol_name: str, timeframe: str, tf_code, count: int) -> pd.DataFrame:
    """Fetch the latest `count` candles for a single symbol and timeframe."""
    candles = mt5.copy_rates_from_pos(symbol_name, tf_code, 0, count)
    if candles is None or len(candles) == 0:
        raise MarketDataError(f"Failed to retrieve candle data for symbol '{symbol_name}' with timeframe '{timeframe}'")
    df = pd.DataFrame(candles)
    df['time'] = pd.to_datetime(df['time'], unit='s', utc=True)
    df = df.sort_values('time', ascending=False)
    return df
