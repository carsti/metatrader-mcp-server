"""Tests for the session cache in front of mt5.symbols_get.

Fetching the symbol list marshals a full SymbolInfo struct per symbol across
the IPC boundary just to read a name, and the list does not change during a
session, so it is cached with a short TTL.
"""

from importlib import import_module

import pytest

symbols_module = import_module("metatrader_client.market.get_symbols")
from metatrader_client.market.get_symbols import clear_symbols_cache, get_symbols


class Sym:
    def __init__(self, name):
        self.name = name


class CountingMT5:
    def __init__(self, names=("EURUSD", "GBPUSD", "XAUUSD")):
        self.names = names
        self.calls = 0

    def symbols_get(self, group=None):
        self.calls += 1
        return [Sym(n) for n in self.names if group is None or group.strip("*") in n]


@pytest.fixture
def fake(monkeypatch):
    counting = CountingMT5()
    monkeypatch.setattr(symbols_module, "mt5", counting)
    clear_symbols_cache()
    yield counting
    clear_symbols_cache()


def test_repeated_calls_hit_the_terminal_once(fake):
    assert get_symbols(None) == ["EURUSD", "GBPUSD", "XAUUSD"]
    assert get_symbols(None) == ["EURUSD", "GBPUSD", "XAUUSD"]
    assert get_symbols(None) == ["EURUSD", "GBPUSD", "XAUUSD"]
    assert fake.calls == 1


def test_each_group_is_cached_separately(fake):
    get_symbols(None)
    get_symbols(None, "*USD*")
    get_symbols(None, "*USD*")
    assert fake.calls == 2


def test_the_cache_expires(fake, monkeypatch):
    get_symbols(None)
    monkeypatch.setattr(symbols_module, "CACHE_TTL_SECONDS", 0)
    get_symbols(None)
    assert fake.calls == 2


def test_clearing_the_cache_forces_a_refetch(fake):
    get_symbols(None)
    clear_symbols_cache()
    get_symbols(None)
    assert fake.calls == 2


def test_use_cache_false_bypasses_it(fake):
    get_symbols(None)
    get_symbols(None, use_cache=False)
    assert fake.calls == 2


def test_callers_cannot_mutate_the_cached_list(fake):
    first = get_symbols(None)
    first.append("TAMPERED")
    assert get_symbols(None) == ["EURUSD", "GBPUSD", "XAUUSD"]


def test_an_empty_result_is_cached_too(fake):
    fake.names = ()
    assert get_symbols(None) == []
    assert get_symbols(None) == []
    assert fake.calls == 1
