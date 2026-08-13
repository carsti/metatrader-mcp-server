import os
from typing import Any, Optional, Union

import pandas as pd

from metatrader_client import client


# Candle timestamps always land on a minute boundary and are always UTC, so the
# seconds and the offset repeat identically on every row.
CANDLE_TIME_FORMAT = "%Y-%m-%dT%H:%M"

# Volume and spread fields that some brokers never populate. A column of nothing
# but zeros carries no information, so it is dropped rather than repeated.
CANDLE_OPTIONAL_COLUMNS = ("real_volume", "spread")


def frame_to_csv(df: Any, index: bool = False) -> str:
	"""Render a DataFrame as CSV for an MCP payload.

	Args:
		df: The DataFrame (anything else is stringified).
		index: Keep the index. Only worth it when the index carries data, as in
			the history frames where it holds the timestamp.

	Returns:
		str: The CSV, with the line terminator pinned so the payload does not
		become CRLF on Windows.
	"""
	if not isinstance(df, pd.DataFrame):
		return str(df)
	return _with_reports(df.to_csv(index=index, lineterminator="\n"), df)


def candles_to_csv(df: Any) -> str:
	"""Render a candle DataFrame as CSV, appending any per-pair reports.

	The candle fetchers return what they could retrieve and record what they
	could not in ``df.attrs``: pairs that failed under 'errors', and pairs with
	more candles available than the limit allowed under 'truncated'. Those are
	appended after the data as separate, clearly marked CSV blocks so a single
	string carries all three.

	Args:
		df: DataFrame returned by a candle operation (anything else is stringified).

	Returns:
		str: The candles as CSV without the index, optionally followed by a
		'# truncated' block and an '# errors' block.
	"""
	if not isinstance(df, pd.DataFrame):
		return str(df)

	compact = _compact(df)
	return _with_reports(compact.to_csv(index=False, lineterminator="\n"), df)


def _compact(df: "pd.DataFrame") -> "pd.DataFrame":
	"""Drop what repeats on every row: the timestamp tail and all-zero columns."""
	if df.empty:
		return df

	view = df
	if "time" in view.columns and pd.api.types.is_datetime64_any_dtype(view["time"]):
		view = view.copy()
		view["time"] = view["time"].dt.strftime(CANDLE_TIME_FORMAT)

	empty = [
		column
		for column in CANDLE_OPTIONAL_COLUMNS
		if column in view.columns and (view[column] == 0).all()
	]
	return view.drop(columns=empty) if empty else view


def _with_reports(csv: str, df: "pd.DataFrame") -> str:
	"""Append the trailing report blocks a frame carries in its attrs.

	Operations return what they could retrieve and record the rest in
	``df.attrs``: rows dropped to a limit under 'truncated', pairs that failed
	under 'errors'. Each becomes its own marked CSV block after a blank line, so
	one string carries the data and everything the caller should know about it.
	"""
	blocks = [csv]
	blocks.extend(_report(df.attrs.get("truncated"), "truncated"))
	blocks.extend(_report(df.attrs.get("errors"), "errors"))
	return "\n".join(blocks)


def _report(rows: Any, name: str) -> list:
	"""Render a trailing '# <name>' CSV block, or nothing when there is no data."""
	if not rows:
		return []
	report_csv = pd.DataFrame(rows).to_csv(index=False, lineterminator="\n")
	return [f"# {name}\n{report_csv}"]


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