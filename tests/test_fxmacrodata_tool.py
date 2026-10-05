import io
import json
import os
import sys
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir, "src")))
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
	assert server._NoRedirect().redirect_request(None, None, 302, "Found", {}, "https://example.com/") is None
	redirect = HTTPError("https://api.fxmacrodata.com/v1/calendar/usd", 302, "Found", {}, None)
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


@pytest.mark.parametrize("payload", [{"detail": "Invalid API key"}, [1, 2], {"data": "oops"}])
def test_fxmacrodata_malformed_response_raises_clean_error(monkeypatch, payload):
	monkeypatch.delenv("FXMACRODATA_API_KEY", raising=False)
	with patch.object(server, "_FXMACRODATA_OPENER", FakeOpener(payload)):
		with pytest.raises(RuntimeError, match="unexpected response"):
			server.get_fxmacrodata_release_calendar("usd")
