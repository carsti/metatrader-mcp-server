"""Shared helpers for multi-symbol / multi-timeframe candle retrieval.

``get_candles_latest`` and ``get_candles_by_date`` both fetch one (symbol,
timeframe) pair at a time and then hand the results here to be merged into a
single DataFrame. Keeping the merge logic in one place keeps the two fetchers
free of presentation concerns and makes the ordering rules testable without a
live MetaTrader 5 connection.
"""

from typing import Any, Dict, List, NamedTuple, Optional, Sequence, Tuple, Union

import pandas as pd

from ..exceptions import InvalidTimeframeError, MarketDataError, SymbolNotFoundError
from ..types import Timeframe
from .get_symbols import get_symbols

GROUP_TIMEFRAME = "timeframe"
GROUP_SYMBOL = "symbol"
GROUP_NONE = "none"
VALID_GROUPS = (GROUP_TIMEFRAME, GROUP_SYMBOL, GROUP_NONE)

_SYMBOL_RANK = "_symbol_rank"
_TIMEFRAME_RANK = "_timeframe_rank"


class CandleResult(NamedTuple):
    """Outcome of fetching a single (symbol, timeframe) pair.

    Exactly one of ``frame`` and ``error`` is set. ``available`` is the row
    count before a limit was applied, and is None when nothing was trimmed.
    """

    symbol: str
    timeframe: str
    frame: Optional[pd.DataFrame]
    error: Optional[BaseException]
    available: Optional[int] = None


def normalize_list(value: Union[str, Sequence[str], None]) -> List[str]:
    """Accept a single string or a sequence of strings, return a clean list.

    Entries are stripped, blanks are dropped, and duplicates are removed while
    preserving the caller's order (that order drives the row ordering later).

    Args:
        value: A string, or any sequence of strings.

    Returns:
        List[str]: Non-empty list of unique, stripped values.

    Raises:
        ValueError: If nothing usable remains.
    """
    if value is None:
        raise ValueError("Expected a symbol/timeframe or a list of them, got None")
    if isinstance(value, str):
        raw: List[Any] = [value]
    elif isinstance(value, (list, tuple)):
        raw = list(value)
    else:
        raise ValueError(
            f"Expected a string or a list of strings, got {type(value).__name__}"
        )

    items: List[str] = []
    for entry in raw:
        if entry is None:
            continue
        if not isinstance(entry, str):
            raise ValueError(f"Expected string entries, got {type(entry).__name__}")
        cleaned = entry.strip()
        if cleaned and cleaned not in items:
            items.append(cleaned)

    if not items:
        raise ValueError("Expected at least one non-empty symbol/timeframe")
    return items


def validate_group(group: Optional[str]) -> str:
    """Normalize the grouping mode, defaulting to ``'none'``.

    Args:
        group: One of 'timeframe', 'symbol', 'none' (case-insensitive), or None.

    Returns:
        str: The normalized group name.

    Raises:
        ValueError: If the value is not a recognized grouping mode.
    """
    if group is None or not str(group).strip():
        return GROUP_NONE
    if not isinstance(group, str):
        raise ValueError(f"Expected a string group, got {type(group).__name__}")
    normalized = group.strip().lower()
    if normalized not in VALID_GROUPS:
        raise ValueError(
            f"Invalid group: '{group}'. Expected one of: {', '.join(VALID_GROUPS)}"
        )
    return normalized


def validate_symbols(connection, symbols: Sequence[str]) -> Dict[str, Optional[BaseException]]:
    """Look each symbol up once, not once per (symbol, timeframe) pair.

    Args:
        connection: MT5 connection object
        symbols: Symbol names to check

    Returns:
        Dict[str, Optional[BaseException]]: name -> None when usable, otherwise
        the error to attribute to every pair using that symbol.
    """
    checked: Dict[str, Optional[BaseException]] = {}
    for name in symbols:
        checked[name] = (
            None if get_symbols(connection, name)
            else SymbolNotFoundError(f"Symbol '{name}' not found")
        )
    return checked


def validate_timeframes(
    timeframes: Sequence[str],
) -> Tuple[Dict[str, Any], Dict[str, BaseException]]:
    """Resolve each timeframe name to its MT5 code once.

    Args:
        timeframes: Timeframe names to resolve

    Returns:
        Tuple[Dict[str, Any], Dict[str, BaseException]]: the resolved codes, and
        the errors for the names that could not be resolved.
    """
    codes: Dict[str, Any] = {}
    errors: Dict[str, BaseException] = {}
    for name in timeframes:
        code = Timeframe.get(name)
        if code is None:
            errors[name] = InvalidTimeframeError(f"Invalid timeframe: '{name}'")
        else:
            codes[name] = code
    return codes, errors


def validate_limit(limit: Optional[int]) -> Optional[int]:
    """Check a per-pair row limit, which must be a positive integer or None."""
    if limit is None:
        return None
    if isinstance(limit, bool) or not isinstance(limit, int):
        raise ValueError(f"Expected an integer limit, got {type(limit).__name__}")
    if limit < 1:
        raise ValueError(f"Expected a limit of at least 1, got {limit}")
    return limit


def combine(
    results: Sequence[CandleResult],
    symbols: Sequence[str],
    timeframes: Sequence[str],
    group: Optional[str] = None,
) -> pd.DataFrame:
    """Merge per-pair results into one DataFrame.

    Identifier columns are added only for the dimensions that actually vary, so
    a single symbol with a single timeframe returns exactly the frame the
    fetcher produced. ``group`` only takes effect when both dimensions vary.

    Row ordering:
        - group='timeframe': timeframe, then symbol, then time descending
        - group='symbol': symbol, then timeframe, then time descending
        - group='none': time descending across everything (chronological merge)

    Symbol and timeframe ordering follows the caller's input order, not
    alphabetical order.

    Args:
        results: One CandleResult per (symbol, timeframe) pair attempted.
        symbols: Requested symbols, in request order.
        timeframes: Requested timeframes, in request order.
        group: Grouping mode (default: 'none').

    Returns:
        pd.DataFrame: The merged candles. ``df.attrs['errors']`` holds one
        ``{'symbol', 'timeframe', 'error'}`` dict per failed pair, and
        ``df.attrs['truncated']`` one ``{'symbol', 'timeframe', 'returned',
        'available'}`` dict per pair that hit its row limit.

    Raises:
        BaseException: The first pair's error, if every pair failed. This keeps
            the single-pair case behaving exactly as it did before.
    """
    group = validate_group(group)

    errors: List[Dict[str, str]] = [
        {"symbol": r.symbol, "timeframe": r.timeframe, "error": str(r.error)}
        for r in results
        if r.error is not None
    ]
    succeeded = [r for r in results if r.error is None and r.frame is not None]
    truncated: List[Dict[str, Any]] = [
        {
            "symbol": r.symbol,
            "timeframe": r.timeframe,
            "returned": len(r.frame),
            "available": r.available,
        }
        for r in succeeded
        if r.available is not None and r.available > len(r.frame)
    ]

    if not succeeded:
        first_error = next((r.error for r in results if r.error is not None), None)
        if first_error is not None:
            raise first_error
        raise MarketDataError("Failed to retrieve candle data: no results returned")

    multi_symbol = len(symbols) > 1
    multi_timeframe = len(timeframes) > 1

    if not multi_symbol and not multi_timeframe:
        df = succeeded[0].frame.reset_index(drop=True)
        df.attrs["errors"] = errors
        df.attrs["truncated"] = truncated
        return df

    symbol_rank = {name: i for i, name in enumerate(symbols)}
    timeframe_rank = {name: i for i, name in enumerate(timeframes)}

    parts = []
    for result in succeeded:
        part = result.frame.copy()
        if multi_symbol:
            part["symbol"] = result.symbol
        if multi_timeframe:
            part["timeframe"] = result.timeframe
        part[_SYMBOL_RANK] = symbol_rank.get(result.symbol, len(symbols))
        part[_TIMEFRAME_RANK] = timeframe_rank.get(result.timeframe, len(timeframes))
        parts.append(part)

    df = pd.concat(parts, ignore_index=True)

    lead, sort_keys = _ordering(group, multi_symbol, multi_timeframe)
    sort_keys = [(column, asc) for column, asc in sort_keys if column in df.columns]
    if sort_keys:
        df = df.sort_values(
            by=[column for column, _ in sort_keys],
            ascending=[asc for _, asc in sort_keys],
            kind="mergesort",
        )
    df = df.reset_index(drop=True).drop(columns=[_SYMBOL_RANK, _TIMEFRAME_RANK])

    rest = [column for column in df.columns if column not in lead]
    df = df[lead + rest]
    df.attrs["errors"] = errors
    df.attrs["truncated"] = truncated
    return df


def _ordering(
    group: str, multi_symbol: bool, multi_timeframe: bool
) -> Tuple[List[str], List[Tuple[str, bool]]]:
    """Return the leading columns and the (column, ascending) sort keys."""
    if multi_symbol and multi_timeframe:
        if group == GROUP_TIMEFRAME:
            return (
                ["timeframe", "symbol"],
                [(_TIMEFRAME_RANK, True), (_SYMBOL_RANK, True), ("time", False)],
            )
        if group == GROUP_SYMBOL:
            return (
                ["symbol", "timeframe"],
                [(_SYMBOL_RANK, True), (_TIMEFRAME_RANK, True), ("time", False)],
            )
        # group == GROUP_NONE: a single chronological stream, no blocks.
        return (
            ["symbol", "timeframe"],
            [("time", False), (_SYMBOL_RANK, True), (_TIMEFRAME_RANK, True)],
        )
    if multi_symbol:
        return ["symbol"], [(_SYMBOL_RANK, True), ("time", False)]
    return ["timeframe"], [(_TIMEFRAME_RANK, True), ("time", False)]
