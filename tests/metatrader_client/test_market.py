import os
import pytest
from dotenv import load_dotenv
from metatrader_client import MT5Client
from metatrader_client.client_market import MT5Market
import platform
import pandas as pd

def print_header():
    if platform.system() == "Windows":
        os.system('cls')
    else:
        os.system('clear')
    print("\n🧪 MetaTrader 5 MCP Market System Full Test Suite 🧪\n")

@pytest.fixture(scope="module")
def mt5_market():
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
    market = client.market
    yield market
    print("\n🔌 Disconnecting from MetaTrader 5...")
    client.disconnect()
    print("👋 Disconnected!")

# --- Test Data ---
TEST_SYMBOL = os.getenv("TEST_SYMBOL", "EURUSD")
TEST_TIMEFRAME = os.getenv("TEST_TIMEFRAME", "M1")

# --- Tests ---
def test_get_symbols(mt5_market):
    print("\n📋 Testing get_symbols...")
    symbols = mt5_market.get_symbols()
    print(f"Symbols: {symbols[:5]} ... (total: {len(symbols)}) 📝")
    assert isinstance(symbols, list)
    assert TEST_SYMBOL in symbols
    print("✅ get_symbols passed!")

def test_get_symbols_group(mt5_market):
    print("\n📋 Testing get_symbols with group...")
    group = "forex"
    symbols = mt5_market.get_symbols(group)
    print(f"Forex group symbols: {symbols[:5]} ...")
    assert isinstance(symbols, list)
    print("✅ get_symbols_group passed!")

def test_get_symbol_info(mt5_market):
    print("\n🔎 Testing get_symbol_info...")
    info = mt5_market.get_symbol_info(TEST_SYMBOL)
    print(f"Symbol info for {TEST_SYMBOL}: {info}")
    assert isinstance(info, dict)
    assert "name" in info
    assert info["name"] == TEST_SYMBOL
    print("✅ get_symbol_info passed!")

def test_get_symbol_info_invalid(mt5_market):
    print("\n❌ Testing get_symbol_info with invalid symbol...")
    with pytest.raises(Exception):
        mt5_market.get_symbol_info("INVALID_SYMBOL")
    print("✅ get_symbol_info_invalid passed!")

def test_get_symbol_price(mt5_market):
    price = mt5_market.get_symbol_price(TEST_SYMBOL)
    print(f"Price for {TEST_SYMBOL}: {price}")
    assert isinstance(price, dict)
    assert "bid" in price and "ask" in price
    assert price["bid"] > 0 and price["ask"] > 0

def test_get_symbol_price_invalid(mt5_market):
    with pytest.raises(Exception):
        mt5_market.get_symbol_price("INVALID_SYMBOL")

def test_get_candles_latest(mt5_market):
    candles = mt5_market.get_candles_latest(TEST_SYMBOL, TEST_TIMEFRAME, count=10)
    print(f"Latest candles for {TEST_SYMBOL} ({TEST_TIMEFRAME}):\n{candles}")
    assert isinstance(candles, pd.DataFrame)
    assert not candles.empty
    assert len(candles) == 10

def test_get_candles_by_date(mt5_market):
    # Use a recent date range (last 2 days)
    from datetime import datetime, timedelta
    to_date = datetime.now().strftime("%Y-%m-%d")
    from_date = (datetime.now() - timedelta(days=2)).strftime("%Y-%m-%d")
    candles = mt5_market.get_candles_by_date(TEST_SYMBOL, TEST_TIMEFRAME, from_date, to_date)
    print(f"Candles from {from_date} to {to_date} for {TEST_SYMBOL}:\n{candles}")
    assert isinstance(candles, pd.DataFrame)
    assert not candles.empty

def test_get_candles_invalid_symbol(mt5_market):
    with pytest.raises(Exception):
        mt5_market.get_candles_latest("INVALID_SYMBOL", TEST_TIMEFRAME, count=5)

def test_get_candles_invalid_timeframe(mt5_market):
    with pytest.raises(Exception):
        mt5_market.get_candles_latest(TEST_SYMBOL, "INVALID_TF", count=5)

# --- Multi-symbol / multi-timeframe ---
TEST_SYMBOL_2 = os.getenv("TEST_SYMBOL_2", "GBPUSD")
TEST_TIMEFRAME_2 = os.getenv("TEST_TIMEFRAME_2", "M15")

def test_get_candles_single_pair_has_no_identifier_columns(mt5_market):
    """A single symbol and timeframe must keep the pre-existing shape."""
    candles = mt5_market.get_candles_latest([TEST_SYMBOL], [TEST_TIMEFRAME], count=5)
    assert "symbol" not in candles.columns
    assert "timeframe" not in candles.columns
    assert len(candles) == 5

def test_get_candles_many_timeframes_adds_timeframe_column(mt5_market):
    candles = mt5_market.get_candles_latest(
        TEST_SYMBOL, [TEST_TIMEFRAME, TEST_TIMEFRAME_2], count=5
    )
    assert list(candles.columns)[0] == "timeframe"
    assert "symbol" not in candles.columns
    assert list(candles["timeframe"].unique()) == [TEST_TIMEFRAME, TEST_TIMEFRAME_2]
    assert len(candles) == 10

def test_get_candles_many_symbols_adds_symbol_column(mt5_market):
    candles = mt5_market.get_candles_latest(
        [TEST_SYMBOL, TEST_SYMBOL_2], TEST_TIMEFRAME, count=5
    )
    assert list(candles.columns)[0] == "symbol"
    assert "timeframe" not in candles.columns
    assert list(candles["symbol"].unique()) == [TEST_SYMBOL, TEST_SYMBOL_2]

def test_get_candles_group_timeframe(mt5_market):
    candles = mt5_market.get_candles_latest(
        [TEST_SYMBOL, TEST_SYMBOL_2],
        [TEST_TIMEFRAME, TEST_TIMEFRAME_2],
        count=5,
        group="timeframe",
    )
    assert list(candles.columns)[:2] == ["timeframe", "symbol"]
    blocks = candles[["timeframe", "symbol"]].drop_duplicates().values.tolist()
    assert blocks == [
        [TEST_TIMEFRAME, TEST_SYMBOL],
        [TEST_TIMEFRAME, TEST_SYMBOL_2],
        [TEST_TIMEFRAME_2, TEST_SYMBOL],
        [TEST_TIMEFRAME_2, TEST_SYMBOL_2],
    ]

def test_get_candles_group_symbol(mt5_market):
    candles = mt5_market.get_candles_latest(
        [TEST_SYMBOL, TEST_SYMBOL_2],
        [TEST_TIMEFRAME, TEST_TIMEFRAME_2],
        count=5,
        group="symbol",
    )
    assert list(candles.columns)[:2] == ["symbol", "timeframe"]
    blocks = candles[["symbol", "timeframe"]].drop_duplicates().values.tolist()
    assert blocks == [
        [TEST_SYMBOL, TEST_TIMEFRAME],
        [TEST_SYMBOL, TEST_TIMEFRAME_2],
        [TEST_SYMBOL_2, TEST_TIMEFRAME],
        [TEST_SYMBOL_2, TEST_TIMEFRAME_2],
    ]

def test_get_candles_group_none_is_chronological(mt5_market):
    candles = mt5_market.get_candles_latest(
        [TEST_SYMBOL, TEST_SYMBOL_2],
        [TEST_TIMEFRAME, TEST_TIMEFRAME_2],
        count=5,
        group="none",
    )
    assert list(candles.columns)[:2] == ["symbol", "timeframe"]
    assert candles["time"].is_monotonic_decreasing

def test_get_candles_invalid_group(mt5_market):
    with pytest.raises(ValueError):
        mt5_market.get_candles_latest(TEST_SYMBOL, TEST_TIMEFRAME, count=5, group="ticker")

def test_get_candles_partial_failure_is_reported_not_raised(mt5_market):
    candles = mt5_market.get_candles_latest(
        [TEST_SYMBOL, "INVALID_SYMBOL"], TEST_TIMEFRAME, count=5
    )
    assert list(candles["symbol"].unique()) == [TEST_SYMBOL]
    assert [e["symbol"] for e in candles.attrs["errors"]] == ["INVALID_SYMBOL"]

def test_get_candles_all_pairs_failing_still_raises(mt5_market):
    with pytest.raises(Exception):
        mt5_market.get_candles_latest(["INVALID_A", "INVALID_B"], TEST_TIMEFRAME, count=5)

def test_get_candles_by_date_respects_the_limit(mt5_market):
    from datetime import datetime, timedelta
    to_date = datetime.now().strftime("%Y-%m-%d")
    from_date = (datetime.now() - timedelta(days=5)).strftime("%Y-%m-%d")
    candles = mt5_market.get_candles_by_date(TEST_SYMBOL, "M1", from_date, to_date, limit=10)
    assert len(candles) == 10
    # Five days of M1 candles is far more than ten, so this must be reported.
    assert candles.attrs["truncated"][0]["returned"] == 10
    assert candles.attrs["truncated"][0]["available"] > 10

def test_get_candles_by_date_limit_applies_per_pair(mt5_market):
    from datetime import datetime, timedelta
    to_date = datetime.now().strftime("%Y-%m-%d")
    from_date = (datetime.now() - timedelta(days=5)).strftime("%Y-%m-%d")
    candles = mt5_market.get_candles_by_date(
        [TEST_SYMBOL, TEST_SYMBOL_2], ["M1", "M5"], from_date, to_date, limit=10
    )
    assert len(candles) == 40

def test_get_candles_by_date_rejects_a_bad_limit(mt5_market):
    with pytest.raises(ValueError):
        mt5_market.get_candles_by_date(TEST_SYMBOL, TEST_TIMEFRAME, limit=0)

def test_get_symbol_info_is_lean_by_default(mt5_market):
    from metatrader_client.market.get_symbol_info import SYMBOL_INFO_FIELDS
    lean = mt5_market.get_symbol_info(TEST_SYMBOL)
    full = mt5_market.get_symbol_info(TEST_SYMBOL, full=True)
    assert set(lean).issubset(set(SYMBOL_INFO_FIELDS))
    assert len(full) > len(lean)
    assert lean["name"] == TEST_SYMBOL

def test_get_candles_by_date_many_symbols(mt5_market):
    from datetime import datetime, timedelta
    to_date = datetime.now().strftime("%Y-%m-%d")
    from_date = (datetime.now() - timedelta(days=2)).strftime("%Y-%m-%d")
    candles = mt5_market.get_candles_by_date(
        [TEST_SYMBOL, TEST_SYMBOL_2],
        [TEST_TIMEFRAME, TEST_TIMEFRAME_2],
        from_date,
        to_date,
        group="symbol",
    )
    assert isinstance(candles, pd.DataFrame)
    assert not candles.empty
    assert list(candles.columns)[:2] == ["symbol", "timeframe"]
