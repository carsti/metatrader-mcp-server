"""Fan-out tests for the candle fetchers with the MetaTrader 5 SDK stubbed out.

The live tests in test_market.py need a broker connection; these cover the
loop, the per-pair error capture and the argument plumbing without one.
"""

from datetime import datetime, timezone
from importlib import import_module

import pandas as pd
import pytest

from metatrader_client.market import get_candles_by_date, get_candles_latest

# The package __init__ rebinds these names to the functions, so reach for the
# modules themselves to patch their globals.
latest = import_module("metatrader_client.market.get_candles_latest")
by_date = import_module("metatrader_client.market.get_candles_by_date")
common = import_module("metatrader_client.market._candles_common")

KNOWN_SYMBOLS = {"EURUSD", "GBPUSD"}
BASE = int(datetime(2026, 8, 13, 14, 0, tzinfo=timezone.utc).timestamp())
STEP = {"H1": 3600, "M15": 900}


def rates(symbol, timeframe_seconds, count):
    """Stand in for the SDK's copy_rates_* return: newest first, epoch seconds."""
    return [
        {
            "time": BASE - i * timeframe_seconds,
            "open": 1.1,
            "high": 1.2,
            "low": 1.0,
            "close": 1.15,
            "tick_volume": 100,
            "spread": 1,
            "real_volume": 0,
        }
        for i in range(count)
    ]


class FakeMT5:
    """Records the calls made and serves candles for the known symbols."""

    def __init__(self):
        self.calls = []
        self.range_rows = 3

    def copy_rates_from_pos(self, symbol, tf, start, count):
        self.calls.append((symbol, tf, count))
        return rates(symbol, tf, count)

    def copy_rates_from(self, symbol, tf, date_from, count):
        self.calls.append((symbol, tf, date_from, count))
        return rates(symbol, tf, count)

    def copy_rates_range(self, symbol, tf, date_from, date_to):
        self.calls.append((symbol, tf, date_from, date_to))
        return rates(symbol, tf, self.range_rows)


@pytest.fixture
def fake_mt5(monkeypatch):
    """Patch both fetchers to hit a fake SDK and a fixed symbol universe."""
    fake = FakeMT5()
    fake.symbol_lookups = []

    def lookup(connection, name):
        fake.symbol_lookups.append(name)
        return [name] if name in KNOWN_SYMBOLS else []

    for module in (latest, by_date):
        monkeypatch.setattr(module, "mt5", fake)
    # Symbol and timeframe validation is shared, so both patches land on _candles_common.
    monkeypatch.setattr(common, "get_symbols", lookup)
    monkeypatch.setattr(common.Timeframe, "get", staticmethod(lambda name: STEP.get(name)))
    return fake


# --- symbol validation happens once per symbol, not once per pair -----------

def test_each_symbol_is_validated_once_regardless_of_timeframe_count(fake_mt5):
    get_candles_latest(None, ["EURUSD", "GBPUSD"], ["H1", "M15"], count=2)
    assert fake_mt5.symbol_lookups == ["EURUSD", "GBPUSD"]


def test_by_date_validates_each_symbol_once(fake_mt5):
    get_candles_by_date(None, ["EURUSD", "GBPUSD"], ["H1", "M15"], "2026-08-01", "2026-08-13")
    assert fake_mt5.symbol_lookups == ["EURUSD", "GBPUSD"]


def test_an_unknown_symbol_costs_one_lookup_and_no_fetches(fake_mt5):
    get_candles_latest(None, ["EURUSD", "XAUUSDX"], ["H1", "M15"], count=2)
    assert fake_mt5.symbol_lookups == ["EURUSD", "XAUUSDX"]
    assert all(call[0] == "EURUSD" for call in fake_mt5.calls)


# --- limit caps rows per pair and reports the truncation --------------------

def test_limit_is_used_as_the_fetch_size_when_no_range_is_given(fake_mt5):
    get_candles_by_date(None, "EURUSD", "H1", limit=25)
    assert fake_mt5.calls == [("EURUSD", 3600, 25)]


def test_limit_is_used_as_the_fetch_size_with_only_a_start_date(fake_mt5):
    get_candles_by_date(None, "EURUSD", "H1", "2026-08-01", limit=25)
    assert fake_mt5.calls[0][3] == 25


def test_limit_trims_a_range_to_the_most_recent_rows(fake_mt5):
    fake_mt5.range_rows = 10
    df = get_candles_by_date(None, "EURUSD", "H1", "2026-08-01", "2026-08-13", limit=4)
    assert len(df) == 4
    # Newest first, so trimming keeps the head.
    assert df["time"].max() == pd.Timestamp(BASE, unit="s", tz="UTC")


def test_truncation_is_reported(fake_mt5):
    fake_mt5.range_rows = 10
    df = get_candles_by_date(None, "EURUSD", "H1", "2026-08-01", "2026-08-13", limit=4)
    assert df.attrs["truncated"] == [
        {"symbol": "EURUSD", "timeframe": "H1", "returned": 4, "available": 10}
    ]


def test_nothing_is_reported_when_the_range_fits(fake_mt5):
    fake_mt5.range_rows = 3
    df = get_candles_by_date(None, "EURUSD", "H1", "2026-08-01", "2026-08-13", limit=100)
    assert df.attrs["truncated"] == []


def test_limit_defaults_to_one_hundred(fake_mt5):
    get_candles_by_date(None, "EURUSD", "H1")
    assert fake_mt5.calls == [("EURUSD", 3600, 100)]


def test_limit_must_be_positive(fake_mt5):
    with pytest.raises(ValueError, match="limit"):
        get_candles_by_date(None, "EURUSD", "H1", limit=0)


def test_latest_reports_no_truncation(fake_mt5):
    df = get_candles_latest(None, "EURUSD", "H1", count=2)
    assert df.attrs["truncated"] == []


# --- get_candles_latest -----------------------------------------------------

def test_latest_single_pair_matches_the_old_shape(fake_mt5):
    df = get_candles_latest(None, "EURUSD", "H1", count=3)
    assert list(df.columns) == [
        "time", "open", "high", "low", "close", "tick_volume", "spread", "real_volume"
    ]
    assert list(df.index) == [0, 1, 2]
    assert fake_mt5.calls == [("EURUSD", 3600, 3)]


def test_latest_fans_out_symbol_outer_timeframe_inner(fake_mt5):
    get_candles_latest(None, ["EURUSD", "GBPUSD"], ["H1", "M15"], count=2)
    assert fake_mt5.calls == [
        ("EURUSD", 3600, 2),
        ("EURUSD", 900, 2),
        ("GBPUSD", 3600, 2),
        ("GBPUSD", 900, 2),
    ]


def test_latest_group_timeframe_orders_rows(fake_mt5):
    df = get_candles_latest(
        None, ["EURUSD", "GBPUSD"], ["H1", "M15"], count=2, group="timeframe"
    )
    assert list(df.columns)[:2] == ["timeframe", "symbol"]
    assert df[["timeframe", "symbol"]].drop_duplicates().values.tolist() == [
        ["H1", "EURUSD"], ["H1", "GBPUSD"], ["M15", "EURUSD"], ["M15", "GBPUSD"]
    ]
    assert len(df) == 8


def test_latest_group_none_is_one_chronological_stream(fake_mt5):
    df = get_candles_latest(
        None, ["EURUSD", "GBPUSD"], ["H1", "M15"], count=2, group="none"
    )
    assert list(df.columns)[:2] == ["symbol", "timeframe"]
    assert df["time"].is_monotonic_decreasing


def test_latest_reports_the_unknown_symbol_and_keeps_the_rest(fake_mt5):
    df = get_candles_latest(None, ["EURUSD", "XAUUSDX"], ["H1", "M15"], count=2)
    assert set(df["symbol"]) == {"EURUSD"}
    assert df.attrs["errors"] == [
        {"symbol": "XAUUSDX", "timeframe": "H1", "error": "Symbol 'XAUUSDX' not found"},
        {"symbol": "XAUUSDX", "timeframe": "M15", "error": "Symbol 'XAUUSDX' not found"},
    ]


def test_latest_raises_when_no_pair_survives(fake_mt5):
    with pytest.raises(Exception, match="Symbol 'AAA' not found"):
        get_candles_latest(None, ["AAA", "BBB"], "H1", count=2)


def test_latest_reports_the_unknown_timeframe(fake_mt5):
    df = get_candles_latest(None, "EURUSD", ["H1", "NOPE"], count=2)
    assert set(df["timeframe"]) == {"H1"}
    assert df.attrs["errors"] == [
        {"symbol": "EURUSD", "timeframe": "NOPE", "error": "Invalid timeframe: 'NOPE'"},
    ]


def test_latest_rejects_an_unknown_group(fake_mt5):
    with pytest.raises(ValueError, match="Invalid group"):
        get_candles_latest(None, "EURUSD", "H1", count=2, group="ticker")


def test_latest_dedupes_repeated_inputs(fake_mt5):
    df = get_candles_latest(None, ["EURUSD", "EURUSD"], ["H1", "H1"], count=2)
    assert fake_mt5.calls == [("EURUSD", 3600, 2)]
    assert "symbol" not in df.columns


# --- get_candles_by_date ----------------------------------------------------

def test_by_date_parses_the_range_once_and_fans_out(fake_mt5):
    get_candles_by_date(
        None, ["EURUSD", "GBPUSD"], ["H1", "M15"], "2026-08-01", "2026-08-13"
    )
    expected_from = datetime(2026, 8, 1, 0, 0, tzinfo=timezone.utc)
    expected_to = datetime(2026, 8, 13, 23, 59, tzinfo=timezone.utc)
    assert fake_mt5.calls == [
        ("EURUSD", 3600, expected_from, expected_to),
        ("EURUSD", 900, expected_from, expected_to),
        ("GBPUSD", 3600, expected_from, expected_to),
        ("GBPUSD", 900, expected_from, expected_to),
    ]


def test_by_date_swaps_a_reversed_range(fake_mt5):
    get_candles_by_date(None, "EURUSD", "H1", "2026-08-13", "2026-08-01")
    _, _, date_from, date_to = fake_mt5.calls[0]
    assert date_from < date_to


def test_by_date_rejects_a_bad_date_before_fetching_anything(fake_mt5):
    with pytest.raises(ValueError, match="Invalid date format"):
        get_candles_by_date(None, ["EURUSD", "GBPUSD"], "H1", "13/08/2026", "2026-08-14")
    assert fake_mt5.calls == []


def test_by_date_group_symbol_orders_rows(fake_mt5):
    df = get_candles_by_date(
        None,
        ["EURUSD", "GBPUSD"],
        ["H1", "M15"],
        "2026-08-01",
        "2026-08-13",
        group="symbol",
    )
    assert list(df.columns)[:2] == ["symbol", "timeframe"]
    assert df[["symbol", "timeframe"]].drop_duplicates().values.tolist() == [
        ["EURUSD", "H1"], ["EURUSD", "M15"], ["GBPUSD", "H1"], ["GBPUSD", "M15"]
    ]


def test_by_date_accepts_datetime_objects(fake_mt5):
    get_candles_by_date(
        None, "EURUSD", "H1", datetime(2026, 8, 1), datetime(2026, 8, 13)
    )
    _, _, date_from, date_to = fake_mt5.calls[0]
    assert date_from == datetime(2026, 8, 1, tzinfo=timezone.utc)
    assert date_to == datetime(2026, 8, 13, tzinfo=timezone.utc)
