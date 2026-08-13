"""Unit tests for the multi-symbol / multi-timeframe candle helpers.

These do not require a live MetaTrader 5 connection: they exercise the pure
combination logic that sits between the per-pair fetch and the caller.
"""

import pandas as pd
import pytest

from metatrader_client.market._candles_common import (
    CandleResult,
    combine,
    normalize_list,
    validate_group,
)


def frame(*times, close=1.0):
    """Build a minimal candle frame, newest first, like the fetchers return."""
    df = pd.DataFrame({
        "time": pd.to_datetime(list(times), utc=True),
        "open": [close] * len(times),
        "close": [close] * len(times),
    })
    return df.sort_values("time", ascending=False)


# --- normalize_list ---------------------------------------------------------

def test_normalize_list_wraps_single_string():
    assert normalize_list("EURUSD") == ["EURUSD"]


def test_normalize_list_strips_and_dedupes_preserving_order():
    assert normalize_list([" EURUSD ", "GBPUSD", "EURUSD"]) == ["EURUSD", "GBPUSD"]


def test_normalize_list_rejects_empty():
    with pytest.raises(ValueError):
        normalize_list([])
    with pytest.raises(ValueError):
        normalize_list("   ")
    with pytest.raises(ValueError):
        normalize_list(None)


# --- validate_group ---------------------------------------------------------

def test_validate_group_defaults_to_none():
    assert validate_group(None) == "none"


def test_validate_group_is_case_insensitive():
    assert validate_group("TimeFrame") == "timeframe"


def test_validate_group_rejects_unknown():
    with pytest.raises(ValueError):
        validate_group("ticker")


# --- combine: 1x1 stays exactly as it is today ------------------------------

def test_combine_single_pair_adds_no_columns():
    df = frame("2026-08-13 14:00", "2026-08-13 13:00")
    out = combine(
        [CandleResult("EURUSD", "H1", df, None)],
        symbols=["EURUSD"],
        timeframes=["H1"],
        group="symbol",
    )
    assert list(out.columns) == ["time", "open", "close"]
    assert len(out) == 2
    assert out.attrs["errors"] == []


def test_combine_resets_the_index():
    df = frame("2026-08-13 14:00", "2026-08-13 13:00")
    out = combine(
        [CandleResult("EURUSD", "H1", df, None)],
        symbols=["EURUSD"],
        timeframes=["H1"],
    )
    assert list(out.index) == [0, 1]


# --- combine: one dimension varies, group is ignored ------------------------

def test_combine_single_symbol_many_timeframes_adds_timeframe_column():
    out = combine(
        [
            CandleResult("EURUSD", "H1", frame("2026-08-13 14:00"), None),
            CandleResult("EURUSD", "M15", frame("2026-08-13 14:30"), None),
        ],
        symbols=["EURUSD"],
        timeframes=["H1", "M15"],
        group="none",
    )
    assert list(out.columns) == ["timeframe", "time", "open", "close"]
    # Input order of timeframes wins over the timestamps.
    assert list(out["timeframe"]) == ["H1", "M15"]


def test_combine_many_symbols_single_timeframe_adds_symbol_column():
    out = combine(
        [
            CandleResult("EURUSD", "H1", frame("2026-08-13 14:00"), None),
            CandleResult("GBPUSD", "H1", frame("2026-08-13 14:00"), None),
        ],
        symbols=["EURUSD", "GBPUSD"],
        timeframes=["H1"],
        group="timeframe",
    )
    assert list(out.columns) == ["symbol", "time", "open", "close"]
    assert list(out["symbol"]) == ["EURUSD", "GBPUSD"]


# --- combine: NxM, group decides column and row order -----------------------

def nxm_results():
    return [
        CandleResult("EURUSD", "H1", frame("2026-08-13 14:00", "2026-08-13 13:00"), None),
        CandleResult("EURUSD", "M15", frame("2026-08-13 14:30", "2026-08-13 14:15"), None),
        CandleResult("GBPUSD", "H1", frame("2026-08-13 14:00", "2026-08-13 13:00"), None),
        CandleResult("GBPUSD", "M15", frame("2026-08-13 14:30", "2026-08-13 14:15"), None),
    ]


def test_combine_group_timeframe_blocks_by_timeframe_then_symbol():
    out = combine(
        nxm_results(),
        symbols=["EURUSD", "GBPUSD"],
        timeframes=["H1", "M15"],
        group="timeframe",
    )
    assert list(out.columns) == ["timeframe", "symbol", "time", "open", "close"]
    assert list(zip(out["timeframe"], out["symbol"], out["time"].dt.strftime("%H:%M"))) == [
        ("H1", "EURUSD", "14:00"),
        ("H1", "EURUSD", "13:00"),
        ("H1", "GBPUSD", "14:00"),
        ("H1", "GBPUSD", "13:00"),
        ("M15", "EURUSD", "14:30"),
        ("M15", "EURUSD", "14:15"),
        ("M15", "GBPUSD", "14:30"),
        ("M15", "GBPUSD", "14:15"),
    ]


def test_combine_group_symbol_blocks_by_symbol_then_timeframe():
    out = combine(
        nxm_results(),
        symbols=["EURUSD", "GBPUSD"],
        timeframes=["H1", "M15"],
        group="symbol",
    )
    assert list(out.columns) == ["symbol", "timeframe", "time", "open", "close"]
    assert list(zip(out["symbol"], out["timeframe"], out["time"].dt.strftime("%H:%M"))) == [
        ("EURUSD", "H1", "14:00"),
        ("EURUSD", "H1", "13:00"),
        ("EURUSD", "M15", "14:30"),
        ("EURUSD", "M15", "14:15"),
        ("GBPUSD", "H1", "14:00"),
        ("GBPUSD", "H1", "13:00"),
        ("GBPUSD", "M15", "14:30"),
        ("GBPUSD", "M15", "14:15"),
    ]


def test_combine_group_none_merges_chronologically():
    out = combine(
        nxm_results(),
        symbols=["EURUSD", "GBPUSD"],
        timeframes=["H1", "M15"],
        group="none",
    )
    assert list(out.columns) == ["symbol", "timeframe", "time", "open", "close"]
    assert list(zip(out["time"].dt.strftime("%H:%M"), out["symbol"], out["timeframe"])) == [
        ("14:30", "EURUSD", "M15"),
        ("14:30", "GBPUSD", "M15"),
        ("14:15", "EURUSD", "M15"),
        ("14:15", "GBPUSD", "M15"),
        ("14:00", "EURUSD", "H1"),
        ("14:00", "GBPUSD", "H1"),
        ("13:00", "EURUSD", "H1"),
        ("13:00", "GBPUSD", "H1"),
    ]


def test_combine_group_defaults_to_none():
    default = combine(nxm_results(), ["EURUSD", "GBPUSD"], ["H1", "M15"])
    explicit = combine(nxm_results(), ["EURUSD", "GBPUSD"], ["H1", "M15"], group="none")
    pd.testing.assert_frame_equal(default, explicit)


# --- combine: partial failures ----------------------------------------------

def test_combine_keeps_successes_and_reports_failures():
    out = combine(
        [
            CandleResult("EURUSD", "H1", frame("2026-08-13 14:00"), None),
            CandleResult("EURUSD", "M15", frame("2026-08-13 14:30"), None),
            CandleResult("XAUUSDX", "H1", None, ValueError("Symbol 'XAUUSDX' not found")),
            CandleResult("XAUUSDX", "M15", None, ValueError("Symbol 'XAUUSDX' not found")),
        ],
        symbols=["EURUSD", "XAUUSDX"],
        timeframes=["H1", "M15"],
        group="symbol",
    )
    assert set(out["symbol"]) == {"EURUSD"}
    assert out.attrs["errors"] == [
        {"symbol": "XAUUSDX", "timeframe": "H1", "error": "Symbol 'XAUUSDX' not found"},
        {"symbol": "XAUUSDX", "timeframe": "M15", "error": "Symbol 'XAUUSDX' not found"},
    ]


def test_combine_raises_when_every_pair_fails():
    first = ValueError("Symbol 'AAA' not found")
    with pytest.raises(ValueError) as excinfo:
        combine(
            [
                CandleResult("AAA", "H1", None, first),
                CandleResult("BBB", "H1", None, ValueError("Symbol 'BBB' not found")),
            ],
            symbols=["AAA", "BBB"],
            timeframes=["H1"],
        )
    assert excinfo.value is first


def test_combine_raises_on_the_single_pair_failure():
    boom = ValueError("Invalid timeframe: 'XX'")
    with pytest.raises(ValueError) as excinfo:
        combine(
            [CandleResult("EURUSD", "XX", None, boom)],
            symbols=["EURUSD"],
            timeframes=["XX"],
        )
    assert excinfo.value is boom
