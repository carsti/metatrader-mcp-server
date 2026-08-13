"""Tests for the column selection applied to history frames.

mt5 returns every field it has on a deal or order. Most of them are constant,
redundant with another field, or broker-internal, so the DataFrame layer keeps
a working subset unless the caller asks for everything.
"""

from datetime import datetime
from importlib import import_module

import pandas as pd
import pytest

deals_module = import_module("metatrader_client.history.get_deals_as_dataframe")
orders_module = import_module("metatrader_client.history.get_orders_as_dataframe")
from metatrader_client.history.get_deals_as_dataframe import get_deals_as_dataframe
from metatrader_client.history.get_orders_as_dataframe import get_orders_as_dataframe

EPOCH = int(datetime(2026, 8, 13, 14, 0).timestamp())

RAW_DEAL = {
    "ticket": 987654321, "order": 987654320, "time": EPOCH, "time_msc": EPOCH * 1000,
    "type": 0, "entry": 1, "magic": 0, "position_id": 123456789, "reason": 3,
    "volume": 0.1, "price": 1.16471, "commission": -0.7, "swap": 0.0, "profit": 5.9,
    "fee": 0.0, "symbol": "EURUSD", "comment": "", "external_id": "",
}

RAW_ORDER = {
    "ticket": 555444333, "time_setup": EPOCH, "time_setup_msc": EPOCH * 1000,
    "time_done": EPOCH + 60, "time_done_msc": (EPOCH + 60) * 1000, "time_expiration": 0,
    "type": 0, "type_time": 0, "type_filling": 1, "state": 4, "magic": 0,
    "position_id": 123456789, "position_by_id": 0, "reason": 3,
    "volume_initial": 0.1, "volume_current": 0.0, "price_open": 1.16412,
    "sl": 1.16000, "tp": 1.17000, "price_current": 1.16471, "price_stoplimit": 0.0,
    "symbol": "EURUSD", "comment": "", "external_id": "",
}


@pytest.fixture
def deals(monkeypatch):
    monkeypatch.setattr(deals_module, "get_deals", lambda *a, **k: [dict(RAW_DEAL)])


@pytest.fixture
def orders(monkeypatch):
    monkeypatch.setattr(orders_module, "get_orders", lambda *a, **k: [dict(RAW_ORDER)])


# --- deals ------------------------------------------------------------------

def test_deals_keep_the_working_subset(deals):
    df = get_deals_as_dataframe(None)
    assert df.index.name == "time"
    assert list(df.columns) == [
        "ticket", "symbol", "type", "entry", "position_id",
        "volume", "price", "commission", "swap", "profit", "comment",
    ]


def test_deals_drop_the_redundant_and_broker_internal_fields(deals):
    df = get_deals_as_dataframe(None)
    for dropped in ("order", "time_msc", "magic", "reason", "fee", "external_id"):
        assert dropped not in df.columns


def test_deals_full_returns_everything(deals):
    df = get_deals_as_dataframe(None, full=True)
    assert "time_msc" in df.columns
    assert "external_id" in df.columns


def test_deals_tolerate_a_missing_field(monkeypatch):
    trimmed = {k: v for k, v in RAW_DEAL.items() if k != "comment"}
    monkeypatch.setattr(deals_module, "get_deals", lambda *a, **k: [trimmed])
    df = get_deals_as_dataframe(None)
    assert "comment" not in df.columns
    assert "ticket" in df.columns


def test_deals_empty_history_is_an_empty_frame(monkeypatch):
    monkeypatch.setattr(deals_module, "get_deals", lambda *a, **k: [])
    assert get_deals_as_dataframe(None).empty


# --- orders -----------------------------------------------------------------

def test_orders_keep_the_working_subset(orders):
    df = get_orders_as_dataframe(None)
    assert df.index.name == "time_setup"
    assert list(df.columns) == [
        "ticket", "time_done", "symbol", "type", "state",
        "volume_initial", "price_open", "sl", "tp", "position_id", "comment",
    ]


def test_orders_drop_the_redundant_and_broker_internal_fields(orders):
    for dropped in (
        "time_setup_msc", "time_done_msc", "time_expiration", "type_time",
        "type_filling", "magic", "position_by_id", "reason", "volume_current",
        "price_current", "price_stoplimit", "external_id",
    ):
        assert dropped not in get_orders_as_dataframe(None).columns


def test_orders_full_returns_everything(orders):
    df = get_orders_as_dataframe(None, full=True)
    assert "type_filling" in df.columns
    assert "price_stoplimit" in df.columns


def test_orders_still_parse_the_timestamps(orders):
    df = get_orders_as_dataframe(None)
    assert isinstance(df.index[0], pd.Timestamp)
    assert isinstance(df["time_done"].iloc[0], pd.Timestamp)


def test_orders_empty_history_is_an_empty_frame(monkeypatch):
    monkeypatch.setattr(orders_module, "get_orders", lambda *a, **k: [])
    assert get_orders_as_dataframe(None).empty


# --- row limits -------------------------------------------------------------

@pytest.fixture
def many_deals(monkeypatch):
    rows = [dict(RAW_DEAL, ticket=987654321 + i, time=EPOCH + i * 60) for i in range(50)]
    monkeypatch.setattr(deals_module, "get_deals", lambda *a, **k: rows)


@pytest.fixture
def many_orders(monkeypatch):
    rows = [dict(RAW_ORDER, ticket=555444333 + i, time_setup=EPOCH + i * 60) for i in range(50)]
    monkeypatch.setattr(orders_module, "get_orders", lambda *a, **k: rows)


def test_deals_are_newest_first(many_deals):
    df = get_deals_as_dataframe(None)
    assert df.index.is_monotonic_decreasing


def test_deals_limit_keeps_the_most_recent(many_deals):
    df = get_deals_as_dataframe(None, limit=5)
    assert len(df) == 5
    # The newest row is the last one generated.
    assert df["ticket"].iloc[0] == 987654321 + 49


def test_deals_report_the_truncation(many_deals):
    df = get_deals_as_dataframe(None, limit=5)
    assert df.attrs["truncated"] == [{"returned": 5, "available": 50}]


def test_deals_report_nothing_when_everything_fits(many_deals):
    assert get_deals_as_dataframe(None, limit=500).attrs["truncated"] == []


def test_deals_reject_a_bad_limit(many_deals):
    with pytest.raises(ValueError, match="limit"):
        get_deals_as_dataframe(None, limit=0)


def test_orders_are_newest_first(many_orders):
    assert get_orders_as_dataframe(None).index.is_monotonic_decreasing


def test_orders_limit_keeps_the_most_recent(many_orders):
    df = get_orders_as_dataframe(None, limit=5)
    assert len(df) == 5
    assert df["ticket"].iloc[0] == 555444333 + 49


def test_orders_report_the_truncation(many_orders):
    assert get_orders_as_dataframe(None, limit=5).attrs["truncated"] == [
        {"returned": 5, "available": 50}
    ]
