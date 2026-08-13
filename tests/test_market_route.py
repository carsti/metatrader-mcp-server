import sys, os
# Add src to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir, "src")))

import pytest
from fastapi.testclient import TestClient
from datetime import datetime
import pandas as pd
from unittest.mock import MagicMock

from metatrader_openapi.main import app
from metatrader_client.exceptions import ConnectionError as MT5ConnectionError


@pytest.fixture
def market_client(monkeypatch):
    """Replace the MT5 client the lifespan builds with a mock.

    The app stores its client on ``app.state.client`` inside the lifespan, so the
    seam to patch is the ``init`` call the lifespan makes - not the router.
    """
    client = MagicMock()
    monkeypatch.setattr("metatrader_openapi.main.init", lambda *args, **kwargs: client)
    return client


def candles_frame(records, errors=None, truncated=None):
    df = pd.DataFrame(records)
    df.attrs["errors"] = errors or []
    df.attrs["truncated"] = truncated or []
    return df


# --- /candles/latest --------------------------------------------------------

def test_candles_latest_single_pair(market_client):
    market_client.market.get_candles_latest.return_value = candles_frame([
        {"time": datetime(2026, 8, 13, 14, 0), "open": 1.16412, "close": 1.16471},
    ])

    with TestClient(app) as api_client:
        response = api_client.get(
            "/api/v1/market/candles/latest?symbol_name=EURUSD&timeframe=H1&count=2"
        )

    assert response.status_code == 200, response.text
    assert response.json() == {
        "data": [{"time": "2026-08-13T14:00:00", "open": 1.16412, "close": 1.16471}],
        "errors": [],
        "truncated": [],
    }
    market_client.market.get_candles_latest.assert_called_once_with(
        symbol_name=["EURUSD"], timeframe=["H1"], count=2, group=None
    )


def test_candles_latest_accepts_repeated_params_and_group(market_client):
    market_client.market.get_candles_latest.return_value = candles_frame([
        {"timeframe": "H1", "symbol": "EURUSD", "close": 1.16471},
        {"timeframe": "H1", "symbol": "GBPUSD", "close": 1.34277},
    ])

    with TestClient(app) as api_client:
        response = api_client.get(
            "/api/v1/market/candles/latest"
            "?symbol_name=EURUSD&symbol_name=GBPUSD"
            "&timeframe=H1&timeframe=M15&group=timeframe"
        )

    assert response.status_code == 200, response.text
    assert len(response.json()["data"]) == 2
    market_client.market.get_candles_latest.assert_called_once_with(
        symbol_name=["EURUSD", "GBPUSD"],
        timeframe=["H1", "M15"],
        count=100,
        group="timeframe",
    )


def test_candles_latest_connection_error(market_client):
    market_client.market.get_candles_latest.side_effect = MT5ConnectionError("Test connection error")

    with TestClient(app) as api_client:
        response = api_client.get("/api/v1/market/candles/latest?symbol_name=EURUSD&timeframe=H1")

    assert response.status_code == 503, response.text
    assert "Test connection error" in response.json()["detail"]


# --- /candles/date ----------------------------------------------------------

def test_candles_by_date_single_pair(market_client):
    market_client.market.get_candles_by_date.return_value = candles_frame([
        {"time": datetime(2023, 1, 1, 0, 0), "open": 1.1, "close": 1.102},
        {"time": datetime(2023, 1, 1, 1, 0), "open": 1.102, "close": 1.107},
    ])

    with TestClient(app) as api_client:
        response = api_client.get(
            "/api/v1/market/candles/date?symbol_name=EURUSD&timeframe=H1"
            "&date_from=2023-01-01T00:00:00&date_to=2023-01-01T05:00:00"
        )

    assert response.status_code == 200, response.text
    assert response.json() == {
        "data": [
            {"time": "2023-01-01T00:00:00", "open": 1.1, "close": 1.102},
            {"time": "2023-01-01T01:00:00", "open": 1.102, "close": 1.107},
        ],
        "errors": [],
        "truncated": [],
    }
    market_client.market.get_candles_by_date.assert_called_once_with(
        symbol_name=["EURUSD"],
        timeframe=["H1"],
        from_date=datetime.fromisoformat("2023-01-01T00:00:00"),
        to_date=datetime.fromisoformat("2023-01-01T05:00:00"),
        group=None,
        limit=100,
    )


def test_candles_by_date_surfaces_partial_errors(market_client):
    market_client.market.get_candles_by_date.return_value = candles_frame(
        [{"symbol": "EURUSD", "timeframe": "H1", "close": 1.16471}],
        errors=[{"symbol": "XAUUSDX", "timeframe": "H1", "error": "Symbol 'XAUUSDX' not found"}],
    )

    with TestClient(app) as api_client:
        response = api_client.get(
            "/api/v1/market/candles/date"
            "?symbol_name=EURUSD&symbol_name=XAUUSDX&timeframe=H1&timeframe=M15"
            "&date_from=2023-01-01T00:00:00&date_to=2023-01-02T00:00:00&group=symbol"
        )

    assert response.status_code == 200, response.text
    assert response.json()["errors"] == [
        {"symbol": "XAUUSDX", "timeframe": "H1", "error": "Symbol 'XAUUSDX' not found"}
    ]
    market_client.market.get_candles_by_date.assert_called_once_with(
        symbol_name=["EURUSD", "XAUUSDX"],
        timeframe=["H1", "M15"],
        from_date=datetime.fromisoformat("2023-01-01T00:00:00"),
        to_date=datetime.fromisoformat("2023-01-02T00:00:00"),
        group="symbol",
        limit=100,
    )


def test_candles_by_date_no_data(market_client):
    market_client.market.get_candles_by_date.return_value = pd.DataFrame()

    with TestClient(app) as api_client:
        response = api_client.get(
            "/api/v1/market/candles/date?symbol_name=EURUSD&timeframe=M5"
            "&date_from=2023-02-01T00:00:00&date_to=2023-02-01T01:00:00"
        )

    assert response.status_code == 200, response.text
    assert response.json() == {"data": [], "errors": [], "truncated": []}


def test_candles_by_date_value_error(market_client):
    market_client.market.get_candles_by_date.side_effect = ValueError("Invalid group: 'ticker'")

    with TestClient(app) as api_client:
        response = api_client.get(
            "/api/v1/market/candles/date?symbol_name=EURUSD&timeframe=H1"
            "&date_from=2023-01-01T00:00:00&date_to=2023-01-02T00:00:00&group=ticker"
        )

    assert response.status_code == 400, response.text
    assert "Invalid group: 'ticker'" in response.json()["detail"]


def test_candles_by_date_connection_error(market_client):
    market_client.market.get_candles_by_date.side_effect = MT5ConnectionError("Test connection error for candles")

    with TestClient(app) as api_client:
        response = api_client.get(
            "/api/v1/market/candles/date?symbol_name=EURUSD&timeframe=H1"
            "&date_from=2023-01-01T00:00:00&date_to=2023-01-02T00:00:00"
        )

    assert response.status_code == 503, response.text
    assert "Test connection error for candles" in response.json()["detail"]


# --- /symbol/info -----------------------------------------------------------

def test_get_symbol_info_success(market_client):
    sample_symbol_info = {
        "name": "EURUSD",
        "description": "Euro vs US Dollar",
        "digits": 5,
        "spread": 10,
        "visible": True,
    }
    market_client.market.get_symbol_info.return_value = sample_symbol_info

    with TestClient(app) as api_client:
        response = api_client.get("/api/v1/market/symbol/info/EURUSD")

    assert response.status_code == 200, response.text
    assert response.json() == sample_symbol_info
    market_client.market.get_symbol_info.assert_called_once_with(symbol_name="EURUSD", full=False)


def test_get_symbol_info_not_found(market_client):
    market_client.market.get_symbol_info.return_value = None

    with TestClient(app) as api_client:
        response = api_client.get("/api/v1/market/symbol/info/UNKNOWN_SYMBOL")

    assert response.status_code == 404, response.text
    assert response.json() == {
        "detail": "Symbol UNKNOWN_SYMBOL not found or no info available."
    }


def test_get_symbol_info_connection_error(market_client):
    market_client.market.get_symbol_info.side_effect = MT5ConnectionError("Test connection error")

    with TestClient(app) as api_client:
        response = api_client.get("/api/v1/market/symbol/info/EURUSD")

    assert response.status_code == 503, response.text
    assert "Test connection error" in response.json()["detail"]
