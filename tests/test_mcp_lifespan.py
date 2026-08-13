"""Tests for the MCP server lifespan.

Startup has two failure modes and both used to end badly: missing credentials
brought the server up with a None client, and an unreachable terminal replaced
the real error with an UnboundLocalError from the cleanup path.
"""

import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir, "src")))

import asyncio
from unittest.mock import MagicMock

import pytest

import metatrader_mcp.server as server


async def enter(lifespan):
    async with lifespan(None) as ctx:
        return ctx


def test_a_working_client_is_yielded_and_disconnected(monkeypatch):
    client = MagicMock()
    monkeypatch.setattr(server, "init", lambda *a, **k: client)

    async def run():
        async with server.app_lifespan(None) as ctx:
            assert ctx.client is client
            client.disconnect.assert_not_called()

    asyncio.run(run())
    client.disconnect.assert_called_once()


def test_missing_credentials_refuse_to_start(monkeypatch):
    monkeypatch.setattr(server, "init", lambda *a, **k: None)

    with pytest.raises(RuntimeError, match="credentials are missing"):
        asyncio.run(enter(server.app_lifespan))


def test_missing_credentials_do_not_crash_the_cleanup(monkeypatch):
    """The old code called disconnect() on None and raised AttributeError."""
    monkeypatch.setattr(server, "init", lambda *a, **k: None)

    with pytest.raises(RuntimeError):
        asyncio.run(enter(server.app_lifespan))


def test_a_failed_connection_keeps_its_own_error(monkeypatch):
    """The original error must survive; the old code masked it with UnboundLocalError."""
    def boom(*args, **kwargs):
        raise ConnectionError("MT5 terminal not running")

    monkeypatch.setattr(server, "init", boom)

    with pytest.raises(ConnectionError, match="MT5 terminal not running"):
        asyncio.run(enter(server.app_lifespan))


def test_the_client_is_disconnected_when_a_tool_raises(monkeypatch):
    client = MagicMock()
    monkeypatch.setattr(server, "init", lambda *a, **k: client)

    async def run():
        async with server.app_lifespan(None):
            raise ValueError("something went wrong mid-session")

    with pytest.raises(ValueError):
        asyncio.run(run())
    client.disconnect.assert_called_once()
