import os
import pytest
from dotenv import load_dotenv
from metatrader_client import MT5Client
import platform

def print_header():
    if platform.system() == "Windows":
        os.system('cls')
    else:
        os.system('clear')
    print("\n🧪 MetaTrader 5 MCP Account System Full Test Suite 🧪\n")

@pytest.fixture(scope="module")
def mt5_account():
    print_header()
    print("🔑 Loading credentials and connecting to MetaTrader 5...")
    load_dotenv()
    login = os.getenv("LOGIN")
    password = os.getenv("PASSWORD")
    server = os.getenv("SERVER")
    if not login or not password or not server:
        print("❌ Error: Missing required environment variables!")
        print("Please create a .env file with LOGIN, PASSWORD, and SERVER variables.")
        pytest.skip("Missing environment variables for MetaTrader 5 connection")
    config = {
        "login": int(login),
        "password": password,
        "server": server
    }
    client = MT5Client(config)
    client.connect()
    print("✅ Connected!\n")
    account = client.account
    yield account
    print("\n🔌 Disconnecting from MetaTrader 5...")
    client.disconnect()
    print("👋 Disconnected!")

def test_get_account_info(mt5_account):
    print("\n📋 Testing get_account_info...")
    info = mt5_account.get_account_info()
    print(f"Account info: {info}")
    assert isinstance(info, dict)
    assert "login" in info
    assert "balance" in info
    assert "currency" in info
    print("✅ get_account_info passed!")

def test_get_balance(mt5_account):
    print("\n💰 Testing get_balance...")
    balance = mt5_account.get_balance()
    print(f"Balance: {balance}")
    assert isinstance(balance, (float, int))
    assert balance >= 0
    print("✅ get_balance passed!")

def test_get_equity(mt5_account):
    print("\n⚖️ Testing get_equity...")
    equity = mt5_account.get_equity()
    print(f"Equity: {equity}")
    assert isinstance(equity, (float, int))
    assert equity >= 0
    print("✅ get_equity passed!")

def test_get_margin(mt5_account):
    print("\n📊 Testing get_margin...")
    margin = mt5_account.get_margin()
    print(f"Margin: {margin}")
    assert isinstance(margin, (float, int))
    assert margin >= 0
    print("✅ get_margin passed!")

def test_get_free_margin(mt5_account):
    print("\n🆓 Testing get_free_margin...")
    free_margin = mt5_account.get_free_margin()
    print(f"Free Margin: {free_margin}")
    assert isinstance(free_margin, (float, int))
    assert free_margin >= 0
    print("✅ get_free_margin passed!")

def test_get_margin_level(mt5_account):
    print("\n📈 Testing get_margin_level...")
    margin_level = mt5_account.get_margin_level()
    print(f"Margin Level: {margin_level}")
    assert isinstance(margin_level, (float, int))
    assert margin_level >= 0
    print("✅ get_margin_level passed!")

def test_get_currency(mt5_account):
    print("\n💱 Testing get_currency...")
    currency = mt5_account.get_currency()
    print(f"Currency: {currency}")
    assert isinstance(currency, str)
    assert len(currency) > 0
    print("✅ get_currency passed!")

def test_get_leverage(mt5_account):
    print("\n🔢 Testing get_leverage...")
    leverage = mt5_account.get_leverage()
    print(f"Leverage: {leverage}")
    assert isinstance(leverage, int)
    assert leverage > 0
    print("✅ get_leverage passed!")

def test_get_account_type(mt5_account):
    print("\n🏦 Testing get_account_type...")
    acc_type = mt5_account.get_account_type()
    print(f"Account Type: {acc_type}")
    assert isinstance(acc_type, str)
    assert len(acc_type) > 0
    assert acc_type in ("demo", "contest", "real") or acc_type.startswith("unknown")
    print("✅ get_account_type passed!")

@pytest.mark.parametrize("trade_mode,expected", [
    (0, "demo"),
    (1, "contest"),
    (2, "real"),
])
def test_account_type_mapping(trade_mode, expected):
    """ENUM_ACCOUNT_TRADE_MODE is DEMO=0, CONTEST=1, REAL=2.

    Pinned because these were once mapped one place off, reporting a demo
    account as "real" and a real account as "contest". Callers use this field to
    decide whether live money is at stake, so a silent flip is expensive. No live
    connection needed - the mapping is what is under test.
    """
    import importlib
    from unittest.mock import patch

    mod = importlib.import_module("metatrader_client.account.get_account_type")

    class _Conn:
        def is_connected(self):
            return True

    with patch.object(mod, "get_account_info", return_value={"trade_mode": trade_mode}):
        assert mod.get_account_type(_Conn()) == expected

def test_is_trade_allowed(mt5_account):
    print("\n✅ Testing is_trade_allowed...")
    allowed = mt5_account.is_trade_allowed()
    print(f"Is trade allowed? {allowed}")
    assert isinstance(allowed, bool)
    print("✅ is_trade_allowed passed!")

def test_check_margin_level(mt5_account):
    print("\n🧮 Testing check_margin_level...")
    result = mt5_account.check_margin_level(0)
    print(f"Margin level check (min 0): {result}")
    assert isinstance(result, bool)
    print("✅ check_margin_level passed!")

def test_get_trade_statistics(mt5_account):
    print("\n📊 Testing get_trade_statistics...")
    stats = mt5_account.get_trade_statistics()
    print(f"Trade statistics: {stats}")
    assert isinstance(stats, dict)
    print("✅ get_trade_statistics passed!")
