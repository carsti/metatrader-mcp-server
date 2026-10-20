import io
import json
import os
import sys
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError, URLError
import traceback

sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir, "src"))
)
sys.modules.setdefault("MetaTrader5", MagicMock())

import pytest

from metatrader_mcp import server


class FakeOpener:
    def __init__(self, result):
        self.result = result
        self.requests = []

    def open(self, request, timeout=None):
        self.requests.append(request)
        if isinstance(self.result, Exception):
            raise self.result
        return io.BytesIO(json.dumps(self.result).encode("utf-8"))


def test_fxmacrodata_redirects_are_not_followed(monkeypatch):
    monkeypatch.setenv("FXMACRODATA_API_KEY", "test-key")
    assert (
        server._NoRedirect().redirect_request(
            None, None, 302, "Found", {}, "https://example.com/"
        )
        is None
    )
    redirect = HTTPError(
        "https://api.fxmacrodata.com/v1/calendar/usd", 302, "Found", {}, None
    )
    opener = FakeOpener(redirect)
    with patch.object(server, "_FXMACRODATA_OPENER", opener):
        with pytest.raises(RuntimeError, match="HTTP 302"):
            server.get_fxmacrodata_release_calendar("usd")
    assert opener.requests[0].get_header("X-api-key") == "test-key"


def test_fxmacrodata_key_is_never_echoed_in_errors(monkeypatch):
    monkeypatch.setenv("FXMACRODATA_API_KEY", "test\nkey")
    opener = FakeOpener({"data": []})
    with patch.object(server, "_FXMACRODATA_OPENER", opener):
        with pytest.raises(ValueError) as excinfo:
            server.get_fxmacrodata_release_calendar("usd")
    assert "test" not in str(excinfo.value)
    assert opener.requests == []


@pytest.mark.parametrize(
    "payload", [{"detail": "Invalid API key"}, [1, 2], {"data": "oops"}]
)
def test_fxmacrodata_malformed_response_raises_clean_error(monkeypatch, payload):
    monkeypatch.delenv("FXMACRODATA_API_KEY", raising=False)
    with patch.object(server, "_FXMACRODATA_OPENER", FakeOpener(payload)):
        with pytest.raises(RuntimeError, match="unexpected response"):
            server.get_fxmacrodata_release_calendar("usd")


def test_error_details_are_not_exposed():
    with patch.object(
        server, "_FXMACRODATA_OPENER", FakeOpener({"detail": "sensitive upstream text"})
    ):
        with pytest.raises(RuntimeError) as caught:
            server.get_fxmacrodata_release_calendar()
    assert "sensitive upstream text" not in str(caught.value)


def test_transport_traceback_is_sanitized():
    with patch.object(
        server, "_FXMACRODATA_OPENER", FakeOpener(URLError("sensitive upstream text"))
    ):
        with pytest.raises(RuntimeError) as caught:
            server.get_fxmacrodata_release_calendar()
    assert "sensitive upstream text" not in "".join(
        traceback.format_exception(caught.value)
    )


def test_invalid_json_is_sanitized():
    opener = MagicMock()
    opener.open.return_value = io.BytesIO(b"invalid")
    with patch.object(server, "_FXMACRODATA_OPENER", opener):
        with pytest.raises(RuntimeError) as caught:
            server.get_fxmacrodata_release_calendar()
    assert caught.value.__suppress_context__


def test_error_envelope_with_data_is_rejected():
    with patch.object(
        server, "_FXMACRODATA_OPENER", FakeOpener({"error": "failed", "data": []})
    ):
        with pytest.raises(RuntimeError):
            server.get_fxmacrodata_release_calendar()


def test_invalid_rows_are_not_silently_discarded():
    with patch.object(
        server,
        "_FXMACRODATA_OPENER",
        FakeOpener({"data": [{"market_tier": 1}, "invalid"]}),
    ):
        with pytest.raises(RuntimeError):
            server.get_fxmacrodata_release_calendar()


def test_malformed_tier_is_excluded():
    with patch.object(
        server,
        "_FXMACRODATA_OPENER",
        FakeOpener({"data": [{"market_tier": "unknown"}]}),
    ):
        assert server.get_fxmacrodata_release_calendar()["events"] == []


def test_boolean_tier_is_not_tier_one():
    with patch.object(
        server, "_FXMACRODATA_OPENER", FakeOpener({"data": [{"market_tier": True}]})
    ):
        assert server.get_fxmacrodata_release_calendar()["events"] == []


def test_valid_tier_filter_preserves_metadata():
    body = {
        "currency": "USD",
        "timezone": "UTC",
        "data": [{"market_tier": 1}, {"market_tier": 2}],
    }
    with patch.object(server, "_FXMACRODATA_OPENER", FakeOpener(body)):
        result = server.get_fxmacrodata_release_calendar()
    assert result["events"] == [{"market_tier": 1}]
    assert result["timezone"] == "UTC"


def test_invalid_threshold_is_rejected_before_request():
    opener = FakeOpener({"data": []})
    with patch.object(server, "_FXMACRODATA_OPENER", opener):
        with pytest.raises(ValueError):
            server.get_fxmacrodata_release_calendar(min_tier=True)
    assert opener.requests == []


def test_unfiltered_rows_obey_limit():
    with patch.object(
        server,
        "_FXMACRODATA_OPENER",
        FakeOpener({"data": [{"release": "cpi"}, {"release": "gdp"}]}),
    ):
        assert server.get_fxmacrodata_release_calendar(limit=1, min_tier=None)[
            "events"
        ] == [{"release": "cpi"}]
