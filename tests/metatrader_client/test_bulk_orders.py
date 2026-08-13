"""Tests for the shared bulk-order helper and the operations built on it."""

from importlib import import_module

import pandas as pd
import pytest

from metatrader_client.order._bulk import apply_to_each

close_all = import_module("metatrader_client.order.close_all_positions")
close_losing = import_module("metatrader_client.order.close_all_losing_positions")
cancel_all = import_module("metatrader_client.order.cancel_all_pending_orders")
from metatrader_client.order.close_all_positions import close_all_positions
from metatrader_client.order.close_all_losing_positions import close_all_losing_positions
from metatrader_client.order.cancel_all_pending_orders import cancel_all_pending_orders


def positions(*rows):
    return pd.DataFrame(rows or None, columns=[
        "id", "time", "symbol", "type", "volume", "open", "stop_loss", "take_profit", "profit",
    ])


def position(id, symbol="EURUSD", profit=5.0, type="BUY"):
    return {
        "id": id, "time": "2026-08-13 14:00", "symbol": symbol, "type": type,
        "volume": 0.1, "open": 1.16412, "stop_loss": 0.0, "take_profit": 0.0,
        "profit": profit,
    }


class Recorder:
    """Stands in for close_position / cancel_pending_order."""

    def __init__(self, failing=()):
        self.failing = set(failing)
        self.called = []

    def __call__(self, connection, id):
        self.called.append(id)
        if id in self.failing:
            return {"error": True, "message": f"Invalid position ID '{id}'", "data": None}
        return {"error": False, "message": "ok", "data": None}


# --- apply_to_each ----------------------------------------------------------

def test_dry_run_touches_nothing_and_lists_the_targets():
    action = Recorder()
    result = apply_to_each(
        None, positions(position(1), position(2)), action,
        verb="Close", subject="positions", dry_run=True,
    )
    assert action.called == []
    assert result["error"] is False
    assert result["data"]["dry_run"] is True
    assert [t["id"] for t in result["data"]["targets"]] == [1, 2]
    assert "Dry run" in result["message"]


def test_dry_run_previews_the_context_a_caller_needs():
    result = apply_to_each(
        None, positions(position(1, profit=-12.5)), Recorder(),
        verb="Close", subject="positions", dry_run=True,
    )
    target = result["data"]["targets"][0]
    assert target["symbol"] == "EURUSD"
    assert target["volume"] == 0.1
    assert target["profit"] == -12.5
    # Bookkeeping the caller did not ask for stays out.
    assert "stop_loss" not in target


def test_every_item_succeeding_reports_success():
    action = Recorder()
    result = apply_to_each(
        None, positions(position(1), position(2)), action,
        verb="Close", subject="positions",
    )
    assert action.called == [1, 2]
    assert result["error"] is False
    assert result["message"] == "Close 2 positions success"
    assert result["data"]["failed"] == []


def test_a_failure_is_reported_rather_than_counted_as_success():
    action = Recorder(failing=[2])
    result = apply_to_each(
        None, positions(position(1), position(2), position(3)), action,
        verb="Close", subject="positions",
    )
    assert action.called == [1, 2, 3]
    assert result["error"] is True
    assert result["message"] == "Close 2 of 3 positions; 1 failed."
    assert [f["id"] for f in result["data"]["failed"]] == [2]
    assert result["data"]["failed"][0]["reason"] == "Invalid position ID '2'"


def test_a_failure_does_not_stop_the_remaining_items():
    action = Recorder(failing=[1])
    apply_to_each(None, positions(position(1), position(2)), action,
                  verb="Close", subject="positions")
    assert action.called == [1, 2]


def test_no_targets_is_not_an_error():
    action = Recorder()
    result = apply_to_each(None, positions(), action, verb="Close", subject="positions")
    assert action.called == []
    assert result["error"] is False
    assert result["message"] == "Close 0 positions success"


# --- the operations built on it ---------------------------------------------

@pytest.fixture
def open_positions(monkeypatch):
    frame = positions(
        position(1, profit=10.0),
        position(2, profit=-5.0),
        position(3, symbol="GBPUSD", profit=-2.0),
    )
    for module in (close_all, close_losing):
        monkeypatch.setattr(module, "get_all_positions", lambda connection: frame)
    return frame


def test_close_all_positions_targets_everything(open_positions, monkeypatch):
    action = Recorder()
    monkeypatch.setattr(close_all, "close_position", action)
    close_all_positions(None)
    assert action.called == [1, 2, 3]


def test_close_all_positions_dry_run(open_positions, monkeypatch):
    action = Recorder()
    monkeypatch.setattr(close_all, "close_position", action)
    result = close_all_positions(None, dry_run=True)
    assert action.called == []
    assert len(result["data"]["targets"]) == 3


def test_close_all_losing_positions_filters_first(open_positions, monkeypatch):
    action = Recorder()
    monkeypatch.setattr(close_losing, "close_position", action)
    close_all_losing_positions(None)
    assert action.called == [2, 3]


def test_close_all_losing_positions_dry_run_lists_only_the_losers(open_positions, monkeypatch):
    action = Recorder()
    monkeypatch.setattr(close_losing, "close_position", action)
    result = close_all_losing_positions(None, dry_run=True)
    assert action.called == []
    assert [t["id"] for t in result["data"]["targets"]] == [2, 3]


def test_cancel_all_pending_orders_dry_run(monkeypatch):
    frame = positions(position(9), position(10))
    monkeypatch.setattr(cancel_all, "get_all_pending_orders", lambda connection: frame)
    action = Recorder()
    monkeypatch.setattr(cancel_all, "cancel_pending_order", action)
    result = cancel_all_pending_orders(None, dry_run=True)
    assert action.called == []
    assert [t["id"] for t in result["data"]["targets"]] == [9, 10]
