"""Unit tests for the MCP presentation helpers."""

import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir, "src")))

import pandas as pd

from metatrader_mcp.utils import candles_to_csv


def sample_frame():
    return pd.DataFrame({
        "symbol": ["EURUSD", "EURUSD"],
        "timeframe": ["H1", "M15"],
        "close": [1.16471, 1.16468],
    })


def test_candles_to_csv_omits_the_index():
    csv = candles_to_csv(sample_frame())
    assert csv.splitlines()[0] == "symbol,timeframe,close"
    assert csv.splitlines()[1] == "EURUSD,H1,1.16471"


def test_candles_to_csv_without_errors_has_no_errors_block():
    csv = candles_to_csv(sample_frame())
    assert "# errors" not in csv


def test_candles_to_csv_appends_the_errors_block():
    df = sample_frame()
    df.attrs["errors"] = [
        {"symbol": "XAUUSDX", "timeframe": "H1", "error": "Symbol 'XAUUSDX' not found"},
    ]
    csv = candles_to_csv(df)
    body, _, errors = csv.partition("\n\n# errors\n")
    assert errors == "symbol,timeframe,error\nXAUUSDX,H1,Symbol 'XAUUSDX' not found\n"
    assert "XAUUSDX" not in body


def test_candles_to_csv_accepts_a_frame_without_attrs():
    csv = candles_to_csv(pd.DataFrame({"close": [1.0]}))
    assert csv == "close\n1.0\n"


def test_candles_to_csv_passes_through_non_frames():
    assert candles_to_csv("already a string") == "already a string"
