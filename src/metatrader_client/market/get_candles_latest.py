from typing import List, Optional, Sequence, Union
import pandas as pd
import MetaTrader5 as mt5
from ..types import Timeframe
from ..exceptions import SymbolNotFoundError, InvalidTimeframeError, MarketDataError
from .get_symbols import get_symbols
from ._candles_common import CandleResult, combine, normalize_list, validate_group


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
        count: Number of candles per (symbol, timeframe) pair (default: 100)
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

    results: List[CandleResult] = []
    for symbol in symbols:
        for tf_name in timeframes:
            try:
                results.append(
                    CandleResult(symbol, tf_name, _fetch_one(connection, symbol, tf_name, count), None)
                )
            except Exception as error:  # collected, then re-raised if nothing succeeds
                results.append(CandleResult(symbol, tf_name, None, error))

    return combine(results, symbols, timeframes, group)


def _fetch_one(connection, symbol_name: str, timeframe: str, count: int) -> pd.DataFrame:
    """Fetch the latest `count` candles for a single symbol and timeframe."""
    if not get_symbols(connection, symbol_name):
        raise SymbolNotFoundError(f"Symbol '{symbol_name}' not found")
    tf = Timeframe.get(timeframe)
    if tf is None:
        raise InvalidTimeframeError(f"Invalid timeframe: '{timeframe}'")
    candles = mt5.copy_rates_from_pos(symbol_name, tf, 0, count)
    if candles is None or len(candles) == 0:
        raise MarketDataError(f"Failed to retrieve candle data for symbol '{symbol_name}' with timeframe '{timeframe}'")
    df = pd.DataFrame(candles)
    df['time'] = pd.to_datetime(df['time'], unit='s', utc=True)
    df = df.sort_values('time', ascending=False)
    return df
