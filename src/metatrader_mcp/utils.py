import os
from typing import Any, Optional, Union

import pandas as pd

from metatrader_client import client


def candles_to_csv(df: Any) -> str:
	"""Render a candle DataFrame as CSV, appending any partial-failure report.

	The candle fetchers return what they could retrieve and record the pairs
	they could not in ``df.attrs['errors']``. Those are appended after the data
	as a second, clearly marked CSV block so a single string carries both.

	Args:
		df: DataFrame returned by a candle operation (anything else is stringified).

	Returns:
		str: The candles as CSV without the index, optionally followed by a
		blank line, a '# errors' marker and one row per failed pair.
	"""
	if not isinstance(df, pd.DataFrame):
		return str(df)

	# lineterminator is pinned so the payload does not become CRLF on Windows.
	csv = df.to_csv(index=False, lineterminator="\n")
	errors = df.attrs.get("errors") or []
	if not errors:
		return csv

	report = pd.DataFrame(errors, columns=["symbol", "timeframe", "error"])
	report_csv = report.to_csv(index=False, lineterminator="\n")
	return f"{csv}\n# errors\n{report_csv}"


def resolve_transport_config(transport=None, host=None, port=None):
	"""Resolve transport config: CLI flag > env var > default."""
	transport = transport or os.getenv("MCP_TRANSPORT", "sse")
	host = host or os.getenv("MCP_HOST", "0.0.0.0")
	port = port if port is not None else int(os.getenv("MCP_PORT", "8080"))
	return transport, host, port


def run_mcp(mcp, transport, host, port):
	"""Run the MCP server with the resolved transport config."""
	if transport == "stdio":
		mcp.run(transport="stdio")
	else:
		mcp.settings.host = host
		mcp.settings.port = port
		# Disable DNS rebinding protection when binding to all interfaces,
		# since the server is intended to be accessed remotely.
		if host == "0.0.0.0":
			mcp.settings.transport_security.enable_dns_rebinding_protection = False
		mcp.run(transport=transport)

def init(
	login: Optional[Union[str, int]],
	password: Optional[str],
	server: Optional[str],
	path: Optional[str] = None,
) -> Optional[client.MT5Client]:
	"""
	Initialize MT5Client

	Args:
		login (Optional[Union[str, int]]): Login ID
		password (Optional[str]): Password
		server (Optional[str]): Server name
		path (Optional[str]): Path to MT5 terminal executable (default: None for auto-detect)

	Returns:
		Optional[client.MT5Client]: MT5Client instance if all parameters are provided, None otherwise
	"""

	if login and password and server:
		config = {
			"login": int(login),
			"password": password,
			"server": server,
		}

		# Add path to config if provided
		if path:
			config["path"] = path

		mt5_client = client.MT5Client(config=config)
		mt5_client.connect()
		return mt5_client

	return None
	
def get_client(ctx: Any) -> Optional[client.MT5Client]:
	return ctx.request_context.lifespan_context.client