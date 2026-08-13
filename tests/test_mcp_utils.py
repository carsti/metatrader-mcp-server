"""Unit tests for the MCP presentation helpers."""

import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir, "src")))

import pandas as pd

from metatrader_mcp.utils import candles_to_csv, frame_to_csv


def sample_frame():
    return pd.DataFrame({
        "symbol": ["EURUSD", "EURUSD"],
        "timeframe": ["H1", "M15"],
        "close": [1.16471, 1.16468],
    })


def candle_frame(**overrides):
    data = {
        "time": pd.to_datetime(["2026-08-13 14:00", "2026-08-13 13:00"], utc=True),
        "open": [1.16412, 1.16350],
        "close": [1.16471, 1.16412],
        "tick_volume": [4821, 5107],
        "spread": [1, 1],
        "real_volume": [0, 0],
    }
    data.update(overrides)
    return pd.DataFrame(data)


# --- frame_to_csv -----------------------------------------------------------

def test_frame_to_csv_omits_the_index_by_default():
    csv = frame_to_csv(sample_frame())
    assert csv.splitlines()[0] == "symbol,timeframe,close"
    assert csv.splitlines()[1] == "EURUSD,H1,1.16471"


def test_frame_to_csv_keeps_a_named_index_when_asked():
    df = sample_frame().set_index("symbol")
    csv = frame_to_csv(df, index=True)
    assert csv.splitlines()[0] == "symbol,timeframe,close"


def test_frame_to_csv_pins_the_line_terminator():
    assert frame_to_csv(pd.DataFrame({"close": [1.0]})) == "close\n1.0\n"


def test_frame_to_csv_passes_through_non_frames():
    assert frame_to_csv("already a string") == "already a string"


# --- candles_to_csv: compact time -------------------------------------------

def test_candles_to_csv_compacts_the_timestamp():
    csv = candles_to_csv(candle_frame())
    assert csv.splitlines()[1].startswith("2026-08-13T14:00,")
    assert "+00:00" not in csv


def test_candles_to_csv_leaves_a_non_datetime_time_column_alone():
    csv = candles_to_csv(candle_frame(time=["a", "b"]))
    assert csv.splitlines()[1].startswith("a,")


# --- candles_to_csv: drop columns that carry no information -----------------

def test_candles_to_csv_drops_an_all_zero_column():
    csv = candles_to_csv(candle_frame())
    assert "real_volume" not in csv


def test_candles_to_csv_keeps_a_constant_non_zero_column():
    csv = candles_to_csv(candle_frame())
    assert "spread" in csv


def test_candles_to_csv_keeps_a_column_that_is_only_partly_zero():
    csv = candles_to_csv(candle_frame(real_volume=[0, 17]))
    assert "real_volume" in csv


def test_candles_to_csv_does_not_touch_price_columns_that_are_zero():
    csv = candles_to_csv(candle_frame(open=[0.0, 0.0]))
    assert "open" in csv


# --- candles_to_csv: trailing report blocks ---------------------------------

def test_candles_to_csv_without_reports_has_no_blocks():
    csv = candles_to_csv(candle_frame())
    assert "# errors" not in csv
    assert "# truncated" not in csv


def test_candles_to_csv_appends_the_errors_block():
    df = candle_frame()
    df.attrs["errors"] = [
        {"symbol": "XAUUSDX", "timeframe": "H1", "error": "Symbol 'XAUUSDX' not found"},
    ]
    csv = candles_to_csv(df)
    body, _, errors = csv.partition("\n\n# errors\n")
    assert errors == "symbol,timeframe,error\nXAUUSDX,H1,Symbol 'XAUUSDX' not found\n"
    assert "XAUUSDX" not in body


def test_candles_to_csv_appends_the_truncation_block():
    df = candle_frame()
    df.attrs["truncated"] = [
        {"symbol": "EURUSD", "timeframe": "H1", "returned": 100, "available": 744},
    ]
    csv = candles_to_csv(df)
    _, _, report = csv.partition("\n\n# truncated\n")
    assert report == "symbol,timeframe,returned,available\nEURUSD,H1,100,744\n"


def test_candles_to_csv_reports_truncation_before_errors():
    df = candle_frame()
    df.attrs["truncated"] = [{"symbol": "EURUSD", "timeframe": "H1", "returned": 1, "available": 9}]
    df.attrs["errors"] = [{"symbol": "XAUUSDX", "timeframe": "H1", "error": "nope"}]
    csv = candles_to_csv(df)
    assert csv.index("# truncated") < csv.index("# errors")


def test_candles_to_csv_accepts_a_frame_without_attrs():
    assert candles_to_csv(pd.DataFrame({"close": [1.0]})) == "close\n1.0\n"


def test_candles_to_csv_passes_through_non_frames():
    assert candles_to_csv("already a string") == "already a string"
