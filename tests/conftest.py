"""
Test isolation for the MetaTrader5 dependency.

The failure mode this file exists to prevent: installing a stub with
``sys.modules.setdefault("MetaTrader5", stub)`` at the top of a *test module*.
On a Windows box with the real MT5 installed, whichever module pytest collects
first wins. Collect the stubbing module first and every later test silently
receives the stub; collect it later and the stubbing module runs against the
real terminal. Collection order deciding semantics is how flaky suites are born.

So the decision is made once, here, before any test module is imported, and it
is explicit: use the real MetaTrader5 when it is importable, otherwise install
a stub that fails loudly the moment a test reaches for something it does not
model. Tests that genuinely need the terminal carry ``precisa_de_mt5_real`` and
skip honestly rather than passing against a stub.
"""

import importlib
import pathlib
import sys
import types

import pytest

# Anchor on this file, not the cwd. `sys.path.insert(0, "src")` breaks the
# moment pytest is invoked from anywhere but the repository root.
_ROOT = pathlib.Path(__file__).resolve().parent.parent
_SRC = _ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))


def _real_mt5_available() -> bool:
    """True only if the genuine MetaTrader5 package can be imported."""
    if "MetaTrader5" in sys.modules:
        return not getattr(sys.modules["MetaTrader5"], "__investia_stub__", False)
    try:
        importlib.import_module("MetaTrader5")
    except ImportError:
        return False
    return True


def _build_stub() -> types.ModuleType:
    """
    Build a MetaTrader5 stand-in.

    Constants live in disjoint numeric ranges on purpose. If ORDER_TYPE_BUY,
    TRADE_ACTION_DEAL and POSITION_TYPE_BUY were all 0 -- as they nearly are in
    a naive stub -- a future test asserting "order type X maps to Y" could pass
    by numeric coincidence while the mapping under test was wrong. Order types
    keep their real MQL5 values because code maps them by value; everything
    else is pushed into its own band.
    """
    stub = types.ModuleType("MetaTrader5")
    stub.__investia_stub__ = True

    # Timeframes: real MQL5 values. types/timeframe.py reads every one of these
    # in a class body at import time, so a missing name breaks collection
    # before a single test runs.
    for name, value in {
        "M1": 1, "M2": 2, "M3": 3, "M4": 4, "M5": 5, "M6": 6,
        "M10": 10, "M12": 12, "M15": 15, "M20": 20, "M30": 30,
        "H1": 16385, "H2": 16386, "H3": 16387, "H4": 16388,
        "H6": 16390, "H8": 16392, "H12": 16396,
        "D1": 16408, "W1": 32769, "MN1": 49153,
    }.items():
        setattr(stub, f"TIMEFRAME_{name}", value)

    # Order types: real values (0-8).
    for i, name in enumerate([
        "ORDER_TYPE_BUY", "ORDER_TYPE_SELL",
        "ORDER_TYPE_BUY_LIMIT", "ORDER_TYPE_SELL_LIMIT",
        "ORDER_TYPE_BUY_STOP", "ORDER_TYPE_SELL_STOP",
        "ORDER_TYPE_BUY_STOP_LIMIT", "ORDER_TYPE_SELL_STOP_LIMIT",
        "ORDER_TYPE_CLOSE_BY",
    ]):
        setattr(stub, name, i)

    for i, name in enumerate([
        "TRADE_ACTION_DEAL", "TRADE_ACTION_PENDING", "TRADE_ACTION_SLTP",
        "TRADE_ACTION_MODIFY", "TRADE_ACTION_REMOVE", "TRADE_ACTION_CLOSE_BY",
    ]):
        setattr(stub, name, 1000 + i)

    for i, name in enumerate([
        "ORDER_TIME_GTC", "ORDER_TIME_DAY",
        "ORDER_TIME_SPECIFIED", "ORDER_TIME_SPECIFIED_DAY",
    ]):
        setattr(stub, name, 2000 + i)

    for i, name in enumerate([
        "ORDER_FILLING_FOK", "ORDER_FILLING_IOC",
        "ORDER_FILLING_RETURN", "ORDER_FILLING_BOC",
    ]):
        setattr(stub, name, 3000 + i)

    for i, name in enumerate(["POSITION_TYPE_BUY", "POSITION_TYPE_SELL"]):
        setattr(stub, name, 4000 + i)

    for i, name in enumerate(["DEAL_TYPE_BUY", "DEAL_TYPE_SELL"]):
        setattr(stub, name, 5000 + i)

    for i, name in enumerate([
        "ORDER_STATE_STARTED", "ORDER_STATE_PLACED", "ORDER_STATE_CANCELED",
        "ORDER_STATE_PARTIAL", "ORDER_STATE_FILLED", "ORDER_STATE_REJECTED",
        "ORDER_STATE_EXPIRED",
    ]):
        setattr(stub, name, 6000 + i)

    # Real value. A placeholder here would let a retcode comparison pass by
    # accident while the production constant it stands for is 10009.
    stub.TRADE_RETCODE_DONE = 10009

    # Neutral defaults. Tests that care install their own spy via monkeypatch.
    stub.initialize = lambda *a, **k: True
    stub.shutdown = lambda *a, **k: None
    stub.last_error = lambda: (0, "ok")
    stub.account_info = lambda *a, **k: None
    stub.history_deals_get = lambda *a, **k: ()
    stub.history_orders_get = lambda *a, **k: ()
    stub.history_deals_total = lambda *a, **k: 0
    stub.history_orders_total = lambda *a, **k: 0
    stub.symbols_get = lambda *a, **k: ()
    stub.symbol_info = lambda *a, **k: None
    stub.symbol_info_tick = lambda *a, **k: None
    stub.symbol_select = lambda *a, **k: True
    stub.positions_get = lambda *a, **k: ()
    stub.orders_get = lambda *a, **k: ()
    stub.copy_rates_range = lambda *a, **k: ()
    stub.copy_rates_from_pos = lambda *a, **k: ()
    stub.order_send = lambda *a, **k: None
    stub.order_check = lambda *a, **k: None
    stub.terminal_info = lambda *a, **k: None
    stub.version = lambda: (0, 0, "stub")

    def _missing(name):
        raise AttributeError(
            f"MetaTrader5 stub has no '{name}'. The test reached code that "
            "needs a real MT5 terminal (Windows only). Either extend the stub "
            "in tests/conftest.py or mark the test with precisa_de_mt5_real. "
            "Failing loudly beats a silent Mock that fakes a passing result."
        )

    stub.__getattr__ = _missing
    return stub


MT5_REAL_DISPONIVEL = _real_mt5_available()

if not MT5_REAL_DISPONIVEL:
    sys.modules["MetaTrader5"] = _build_stub()

#: Mark tests that genuinely need the terminal. Skipping is honest; running
#: them against the stub and reporting green is not.
precisa_de_mt5_real = pytest.mark.skipif(
    not MT5_REAL_DISPONIVEL,
    reason="requer o MetaTrader5 real instalado (somente Windows com terminal)",
)


@pytest.fixture
def mt5_stub():
    """The MetaTrader5 module in play, for tests that spy on its calls."""
    return sys.modules["MetaTrader5"]
