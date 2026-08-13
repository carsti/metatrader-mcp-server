"""Tests for the field selection on symbol info.

mt5's SymbolInfo carries dozens of attributes. The default result keeps the
ones a trading decision needs - sizing, precision, limits, costs.
"""

from importlib import import_module

import pytest

info_module = import_module("metatrader_client.market.get_symbol_info")
from metatrader_client.market.get_symbol_info import SYMBOL_INFO_FIELDS, get_symbol_info


class FakeSymbolInfo:
    """Stands in for the SDK struct: the useful fields plus plenty of noise."""

    def __init__(self):
        self.name = "EURUSD"
        self.description = "Euro vs US Dollar"
        self.currency_base = "EUR"
        self.currency_profit = "USD"
        self.currency_margin = "EUR"
        self.digits = 5
        self.point = 1e-05
        self.spread = 10
        self.trade_mode = 4
        self.trade_stops_level = 0
        self.volume_min = 0.01
        self.volume_max = 500.0
        self.volume_step = 0.01
        self.trade_contract_size = 100000.0
        self.trade_tick_size = 1e-05
        self.trade_tick_value = 1.0
        self.swap_long = -7.5
        self.swap_short = 1.2
        self.visible = True
        self.path = "Forex\\EURUSD"
        # Noise the default result should leave out.
        self.session_deals = 0
        self.swap_rollover3days = 3
        self.margin_hedged = 0.0
        self.bidhigh = 1.16501
        self.ticks_bookdepth = 10
        self.expiration_time = 0

    def method_that_should_be_ignored(self):
        return "nope"


class FakeMT5:
    def __init__(self, found=True):
        self.found = found

    def symbols_get(self, group=None):
        return [FakeSymbolInfo()] if self.found else []


@pytest.fixture
def fake(monkeypatch):
    mt5 = FakeMT5()
    monkeypatch.setattr(info_module, "mt5", mt5)
    return mt5


def test_default_returns_the_trading_fields(fake):
    info = get_symbol_info(None, "EURUSD")
    assert set(info) == set(SYMBOL_INFO_FIELDS)
    assert info["name"] == "EURUSD"
    assert info["volume_min"] == 0.01
    assert info["digits"] == 5


def test_default_leaves_out_the_noise(fake):
    info = get_symbol_info(None, "EURUSD")
    for noisy in ("session_deals", "swap_rollover3days", "margin_hedged", "bidhigh"):
        assert noisy not in info


def test_full_returns_every_attribute(fake):
    info = get_symbol_info(None, "EURUSD", full=True)
    assert "session_deals" in info
    assert "bidhigh" in info
    assert "method_that_should_be_ignored" not in info


def test_a_field_the_broker_does_not_expose_is_skipped(fake, monkeypatch):
    class Sparse:
        name = "EURUSD"
        digits = 5

    monkeypatch.setattr(info_module.mt5, "symbols_get", lambda group=None: [Sparse()])
    info = get_symbol_info(None, "EURUSD")
    assert info == {"name": "EURUSD", "digits": 5}


def test_an_unknown_symbol_raises(fake):
    fake.found = False
    with pytest.raises(Exception, match="not found"):
        get_symbol_info(None, "NOPE")
