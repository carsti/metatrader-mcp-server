"""Tests that MT5Order forwards what its callers pass.

The wrapper is thin, but a dropped keyword here is invisible until runtime: the
REST market-order endpoint passed stop_loss and take_profit into a signature
that did not accept them, so every protected market order returned HTTP 500.
"""

from importlib import import_module

import pytest

import metatrader_client.client_order as client_order
from metatrader_client.client_order import MT5Order


@pytest.fixture
def order(monkeypatch):
    calls = {}

    def record(name):
        def inner(*args, **kwargs):
            calls[name] = {"args": args, "kwargs": kwargs}
            return {"error": False, "message": "ok", "data": None}
        return inner

    for name in (
        "place_market_order", "place_pending_order",
        "calculate_margin", "calculate_profit", "calculate_price_target",
        "close_all_positions", "close_all_losing_positions",
        "close_all_profitable_positions", "close_all_positions_by_symbol",
        "cancel_all_pending_orders", "cancel_pending_orders_by_symbol",
    ):
        monkeypatch.setattr(client_order, name, record(name))

    handler = MT5Order("CONNECTION")
    handler.calls = calls
    return handler


# --- the protective levels must survive the wrapper -------------------------

def test_market_order_forwards_stop_loss_and_take_profit(order):
    order.place_market_order(type="BUY", symbol="EURUSD", volume=0.1, stop_loss=1.16, take_profit=1.17)
    kwargs = order.calls["place_market_order"]["kwargs"]
    assert kwargs["stop_loss"] == 1.16
    assert kwargs["take_profit"] == 1.17


def test_market_order_defaults_the_levels_to_zero(order):
    order.place_market_order(type="BUY", symbol="EURUSD", volume=0.1)
    kwargs = order.calls["place_market_order"]["kwargs"]
    assert kwargs["stop_loss"] == 0.0
    assert kwargs["take_profit"] == 0.0


def test_pending_order_forwards_the_levels_too(order):
    order.place_pending_order(type="BUY", symbol="EURUSD", volume=0.1, price=1.15, stop_loss=1.14, take_profit=1.18)
    kwargs = order.calls["place_pending_order"]["kwargs"]
    assert kwargs["stop_loss"] == 1.14
    assert kwargs["take_profit"] == 1.18


# --- the calculators are reachable at all -----------------------------------

def test_calculate_margin_is_exposed(order):
    order.calculate_margin(order_type="BUY", symbol="EURUSD", volume=0.1, price=1.16)
    assert order.calls["calculate_margin"]["args"] == ("BUY", "EURUSD", 0.1, 1.16)


def test_calculate_profit_is_exposed(order):
    order.calculate_profit(order_type="BUY", symbol="EURUSD", volume=0.1, price_open=1.16, price_close=1.17)
    assert order.calls["calculate_profit"]["args"] == ("BUY", "EURUSD", 0.1, 1.16, 1.17)


def test_calculate_price_target_is_exposed(order):
    order.calculate_price_target(order_type="BUY", symbol="EURUSD", volume=0.1, entry_price=1.16, target=-50.0)
    assert order.calls["calculate_price_target"]["args"] == ("BUY", "EURUSD", 0.1, 1.16, -50.0)


def test_the_calculators_take_no_connection(order):
    """They talk to the terminal directly, unlike every other order function."""
    order.calculate_margin(order_type="BUY", symbol="EURUSD", volume=0.1, price=1.16)
    assert "CONNECTION" not in order.calls["calculate_margin"]["args"]


# --- dry_run reaches the bulk operations ------------------------------------

@pytest.mark.parametrize("method", [
    "close_all_positions",
    "close_all_losing_positions",
    "close_all_profitable_positions",
    "cancel_all_pending_orders",
])
def test_bulk_operations_forward_dry_run(order, method):
    getattr(order, method)(dry_run=True)
    assert order.calls[method]["args"] == ("CONNECTION", True)


@pytest.mark.parametrize("method", [
    "close_all_positions_by_symbol",
    "cancel_pending_orders_by_symbol",
])
def test_bulk_operations_by_symbol_forward_dry_run(order, method):
    getattr(order, method)("EURUSD", dry_run=True)
    assert order.calls[method]["args"] == ("CONNECTION", "EURUSD", True)


@pytest.mark.parametrize("method", [
    "close_all_positions",
    "cancel_all_pending_orders",
])
def test_bulk_operations_default_to_executing(order, method):
    getattr(order, method)()
    assert order.calls[method]["args"] == ("CONNECTION", False)
