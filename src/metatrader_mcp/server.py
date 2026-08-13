#!/usr/bin/env python3
import os
import argparse
import logging
from dotenv import load_dotenv

from mcp.server.fastmcp import FastMCP, Context
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import List, Optional, Union

from metatrader_client.client import MT5Client
from metatrader_mcp.utils import init, get_client, candles_to_csv, frame_to_csv

# ────────────────────────────────────────────────────────────────────────────────
# 1) Lifespan context definition
# ────────────────────────────────────────────────────────────────────────────────
@dataclass
class AppContext:
	client: MT5Client

@asynccontextmanager
async def app_lifespan(server: FastMCP) -> AsyncIterator[AppContext]:

	client = None
	try:
		client = init(
			os.getenv("login"),
			os.getenv("password"),
			os.getenv("server"),
			os.getenv("MT5_PATH")
		)
		# init returns None when credentials are missing. Starting anyway would
		# leave every tool failing on a None client with an error that says
		# nothing about the cause, so refuse to come up instead.
		if client is None:
			raise RuntimeError(
				"MetaTrader 5 credentials are missing. Set login, password and server "
				"in the environment (or LOGIN/PASSWORD/SERVER), or pass --login, "
				"--password and --server."
			)
		yield AppContext(client=client)
	finally:
		# Guarded: on a failed startup there is nothing to disconnect, and an
		# error here would replace the exception that explains what went wrong.
		if client is not None:
			client.disconnect()

# ────────────────────────────────────────────────────────────────────────────────
# 2) Instantiate FastMCP as `mcp` (must be named `mcp`, `server`, or `app`)
# ────────────────────────────────────────────────────────────────────────────────
mcp = FastMCP(
	"metatrader",
	lifespan=app_lifespan,
	dependencies=[],
)

# ────────────────────────────────────────────────────────────────────────────────
# 3) Register tools with @mcp.tool()
# ────────────────────────────────────────────────────────────────────────────────

@mcp.tool()
def get_account_info(ctx: Context) -> dict:
	"""Get account information (balance, equity, profit, margin level, free margin, account type, leverage, currency)."""
	client = get_client(ctx)
	return client.account.get_trade_statistics()

@mcp.tool()
def get_deals(ctx: Context, from_date: Optional[str] = None, to_date: Optional[str] = None, symbol: Optional[str] = None, limit: int = 500) -> str:
	"""Get historical deals as CSV, newest first, indexed by time.

	Date input in format: 'YYYY-MM-DD'. Defaults to the last 30 days.
	limit caps the rows (default 500), keeping the most recent; dropped rows are
	reported in a trailing '# truncated' block.
	"""
	client = get_client(ctx)
	df = client.history.get_deals_as_dataframe(from_date=from_date, to_date=to_date, group=symbol, limit=limit)
	# The index holds the timestamp here, so it is worth its bytes.
	return frame_to_csv(df, index=True)

@mcp.tool()
def get_orders(ctx: Context, from_date: Optional[str] = None, to_date: Optional[str] = None, symbol: Optional[str] = None, limit: int = 500) -> str:
	"""Get historical orders as CSV, newest first, indexed by setup time.

	Date input in format: 'YYYY-MM-DD'. Defaults to the last 30 days.
	limit caps the rows (default 500), keeping the most recent; dropped rows are
	reported in a trailing '# truncated' block.
	"""
	client = get_client(ctx)
	df = client.history.get_orders_as_dataframe(from_date=from_date, to_date=to_date, group=symbol, limit=limit)
	return frame_to_csv(df, index=True)

@mcp.tool()
def get_candles_by_date(
	ctx: Context,
	symbol_name: Union[str, List[str]],
	timeframe: Union[str, List[str]],
	from_date: Optional[str] = None,
	to_date: Optional[str] = None,
	group: Optional[str] = None,
	limit: int = 100,
) -> str:
	"""Get candle data for one or more symbols and timeframes in a date range, as CSV.

	symbol_name and timeframe each accept a single value or a list.
	Date input in format: ISO 8601 or 'YYYY-MM-DD' or 'YYYY-MM-DD HH:MM'.
	limit caps the candles per (symbol, timeframe) pair, most recent first
	(default 100), so the total row count is limit x symbols x timeframes. Raise
	it deliberately: the payload grows with every pair.
	group ('timeframe', 'symbol' or 'none', default 'none') orders the rows and
	only applies when both symbol_name and timeframe hold more than one value:
	'timeframe' blocks by timeframe then symbol, 'symbol' blocks by symbol then
	timeframe, 'none' merges everything into one stream ordered by time.
	'symbol' and 'timeframe' columns appear only for the dimensions that vary.
	Pairs with more candles available than limit allowed are listed in a trailing
	'# truncated' block, and pairs that fail in a '# errors' block instead of
	failing the whole call.
	"""
	client = get_client(ctx)
	df = client.market.get_candles_by_date(symbol_name=symbol_name, timeframe=timeframe, from_date=from_date, to_date=to_date, group=group, limit=limit)
	return candles_to_csv(df)

@mcp.tool()
def get_candles_latest(
	ctx: Context,
	symbol_name: Union[str, List[str]],
	timeframe: Union[str, List[str]],
	count: int = 100,
	group: Optional[str] = None,
) -> str:
	"""Get the latest N candles for one or more symbols and timeframes, as CSV.

	symbol_name and timeframe each accept a single value or a list; count applies
	per (symbol, timeframe) pair.
	group ('timeframe', 'symbol' or 'none', default 'none') orders the rows and
	only applies when both symbol_name and timeframe hold more than one value:
	'timeframe' blocks by timeframe then symbol, 'symbol' blocks by symbol then
	timeframe, 'none' merges everything into one stream ordered by time.
	'symbol' and 'timeframe' columns appear only for the dimensions that vary.
	Pairs that fail are listed in a trailing '# errors' block instead of failing
	the whole call.
	"""
	client = get_client(ctx)
	df = client.market.get_candles_latest(symbol_name=symbol_name, timeframe=timeframe, count=count, group=group)
	return candles_to_csv(df)

@mcp.tool()
def get_symbol_price(ctx: Context, symbol_name: str) -> dict:
	"""Get the latest price info for a symbol as a dictionary."""
	client = get_client(ctx)
	return client.market.get_symbol_price(symbol_name=symbol_name)

@mcp.tool()
def get_symbol_info(ctx: Context, symbol_name: str, full: bool = False) -> dict:
	"""Get the trading specification of a symbol: digits, point, spread, volume_min,
	volume_max, volume_step, contract size, tick size and value, swaps and trade mode.

	Check this before sizing an order - volume_min, volume_max and volume_step
	decide whether a volume is even accepted, and digits decides price rounding.
	Set full=True for every field the broker exposes; the payload is several
	times larger and mostly session and margin bookkeeping.
	"""
	client = get_client(ctx)
	return client.market.get_symbol_info(symbol_name=symbol_name, full=full)

@mcp.tool()
def get_all_symbols(ctx: Context) -> List[str]:
	"""Get a list of all available market symbols. Brokers commonly expose
	thousands, so prefer get_symbols with a group pattern when you can."""
	client = get_client(ctx)
	return client.market.get_symbols()

@mcp.tool()
def get_symbols(ctx: Context, group: Optional[str] = None) -> List[str]:
	"""
	Get a list of available market symbols. Filter symbols by group pattern (e.g., '*USD*').
	"""
	client = get_client(ctx)
	return client.market.get_symbols(group=group)

# ────────────────────────────────────────────────────────────────────────────────
# Order module tools
# ────────────────────────────────────────────────────────────────────────────────

@mcp.tool()
def get_all_positions(ctx: Context) -> str:
	"""Get all open positions as CSV."""
	client = get_client(ctx)
	df = client.order.get_all_positions()
	return frame_to_csv(df)

@mcp.tool()
def get_positions_by_symbol(ctx: Context, symbol: str) -> str:
	"""Get open positions for a specific symbol as CSV."""
	client = get_client(ctx)
	df = client.order.get_positions_by_symbol(symbol=symbol)
	return frame_to_csv(df)

@mcp.tool()
def get_positions_by_currency(ctx: Context, currency: str) -> str:
	"""Get open positions whose symbol involves a currency (e.g., 'USD') as CSV."""
	client = get_client(ctx)
	df = client.order.get_positions_by_currency(currency=currency)
	return frame_to_csv(df)

@mcp.tool()
def get_positions_by_id(ctx: Context, id: Union[int, str]) -> str:
	"""Get open positions by ID as CSV."""
	client = get_client(ctx)
	df = client.order.get_positions_by_id(id=id)
	return frame_to_csv(df)

@mcp.tool()
def get_all_pending_orders(ctx: Context) -> str:
	"""Get all pending orders as CSV."""
	client = get_client(ctx)
	df = client.order.get_all_pending_orders()
	return frame_to_csv(df)

@mcp.tool()
def get_pending_orders_by_symbol(ctx: Context, symbol: str) -> str:
	"""Get pending orders for a specific symbol as CSV."""
	client = get_client(ctx)
	df = client.order.get_pending_orders_by_symbol(symbol=symbol)
	return frame_to_csv(df)

@mcp.tool()
def get_pending_orders_by_currency(ctx: Context, currency: str) -> str:
	"""Get pending orders whose symbol involves a currency (e.g., 'USD') as CSV."""
	client = get_client(ctx)
	df = client.order.get_pending_orders_by_currency(currency=currency)
	return frame_to_csv(df)

@mcp.tool()
def get_pending_orders_by_id(ctx: Context, id: Union[int, str]) -> str:
	"""Get pending orders by id as CSV."""
	client = get_client(ctx)
	df = client.order.get_pending_orders_by_id(id=id)
	return frame_to_csv(df)

# ────────────────────────────────────────────────────────────────────────────────
# Pre-trade calculators
# ────────────────────────────────────────────────────────────────────────────────

@mcp.tool()
def calculate_margin(ctx: Context, order_type: str, symbol: str, volume: float, price: float) -> Optional[float]:
	"""Margin required to open a position, without placing it. Compare against
	free_margin from get_account_info to size a trade you can actually afford.

	order_type: 'BUY' or 'SELL'. price: the entry price to assume.
	"""
	client = get_client(ctx)
	return client.order.calculate_margin(order_type=order_type, symbol=symbol, volume=volume, price=price)

@mcp.tool()
def calculate_profit(ctx: Context, order_type: str, symbol: str, volume: float, price_open: float, price_close: float) -> Optional[float]:
	"""Profit a position would make moving from price_open to price_close, in the
	account currency. Use it to check a take profit or stop loss is worth its risk.

	order_type: 'BUY' or 'SELL'.
	"""
	client = get_client(ctx)
	return client.order.calculate_profit(order_type=order_type, symbol=symbol, volume=volume, price_open=price_open, price_close=price_close)

@mcp.tool()
def calculate_price_target(ctx: Context, order_type: str, symbol: str, volume: float, entry_price: float, target: float) -> Optional[float]:
	"""The price at which a position reaches a given profit or loss target, in the
	account currency. Use it to place a stop loss at a chosen risk amount.

	order_type: 'BUY' or 'SELL'. target: positive for profit, negative for loss.
	"""
	client = get_client(ctx)
	return client.order.calculate_price_target(order_type=order_type, symbol=symbol, volume=volume, entry_price=entry_price, target=target)

@mcp.tool()
def place_market_order(ctx: Context, symbol: str, volume: float, type: str, stop_loss: Optional[float] = 0.0, take_profit: Optional[float] = 0.0) -> dict:
	"""
	Place a market order. Parameters:
		symbol: Symbol name (e.g., 'EURUSD')
		volume: Lot size. (e.g. 1.5)
		type: Order type ('BUY' or 'SELL')
		stop_loss (optional): Stop loss price. 0.0 leaves the position unprotected.
		take_profit (optional): Take profit price. 0.0 for none.

	Set stop_loss here rather than calling modify_position afterwards: between the
	two calls the position carries unbounded risk. Check get_symbol_info first -
	volume_min, volume_max and volume_step decide whether the volume is accepted,
	and digits decides price rounding.
	"""
	client = get_client(ctx)
	return client.order.place_market_order(symbol=symbol, volume=volume, type=type, stop_loss=stop_loss, take_profit=take_profit)

@mcp.tool()
def place_pending_order(ctx: Context, symbol: str, volume: float, type: str, price: float, stop_loss: Optional[Union[int, float]] = 0.0, take_profit: Optional[Union[int, float]] = 0.0) -> dict:
	"""
	Place a pending order. Parameters:
		symbol: Symbol name (e.g., 'EURUSD')
		volume: Lot size. (e.g. 1.5)
		type: Order type ('BUY', 'SELL').
		price: Pending order price.
		stop_loss (optional): Stop loss price.
		take_profit (optional): Take profit price.
	"""
	client = get_client(ctx)
	return client.order.place_pending_order(symbol=symbol, volume=volume, type=type, price=price, stop_loss=stop_loss, take_profit=take_profit)

@mcp.tool()
def modify_position(ctx: Context, id: Union[int, str], stop_loss: Optional[Union[int, float]] = None, take_profit: Optional[Union[int, float]] = None) -> dict:
	"""Modify an open position by ID."""
	client = get_client(ctx)
	return client.order.modify_position(id=id, stop_loss=stop_loss, take_profit=take_profit)
@mcp.tool()
def modify_pending_order(ctx: Context, id: Union[int, str], price: Optional[Union[int, float]] = None, stop_loss: Optional[Union[int, float]] = None, take_profit: Optional[Union[int, float]] = None) -> dict:
	"""Modify a pending order by ID."""
	client = get_client(ctx)
	return client.order.modify_pending_order(id=id, price=price, stop_loss=stop_loss, take_profit=take_profit)
@mcp.tool()
def close_position(ctx: Context, id: Union[int, str]) -> dict:
	"""Close an open position by ID."""
	client = get_client(ctx)
	return client.order.close_position(id=id)

@mcp.tool()
def cancel_pending_order(ctx: Context, id: Union[int, str]) -> dict:
	"""Cancel a pending order by ID."""
	client = get_client(ctx)
	return client.order.cancel_pending_order(id=id)

# Every bulk operation below takes dry_run. Call it with dry_run=True first when
# the scope is not obvious: the result lists exactly what would be affected, with
# symbol, volume and profit, and nothing is sent to the terminal.

@mcp.tool()
def close_all_positions(ctx: Context, dry_run: bool = False) -> dict:
	"""Close all open positions. Set dry_run=True to list what would be closed instead."""
	client = get_client(ctx)
	return client.order.close_all_positions(dry_run=dry_run)

@mcp.tool()
def close_all_positions_by_symbol(ctx: Context, symbol: str, dry_run: bool = False) -> dict:
	"""Close all open positions for a specific symbol. Set dry_run=True to list what would be closed instead."""
	client = get_client(ctx)
	return client.order.close_all_positions_by_symbol(symbol=symbol, dry_run=dry_run)

@mcp.tool()
def close_all_profitable_positions(ctx: Context, dry_run: bool = False) -> dict:
	"""Close all profitable positions. Set dry_run=True to list what would be closed instead."""
	client = get_client(ctx)
	return client.order.close_all_profitable_positions(dry_run=dry_run)

@mcp.tool()
def close_all_losing_positions(ctx: Context, dry_run: bool = False) -> dict:
	"""Close all losing positions. Set dry_run=True to list what would be closed instead."""
	client = get_client(ctx)
	return client.order.close_all_losing_positions(dry_run=dry_run)

@mcp.tool()
def cancel_all_pending_orders(ctx: Context, dry_run: bool = False) -> dict:
	"""Cancel all pending orders. Set dry_run=True to list what would be cancelled instead."""
	client = get_client(ctx)
	return client.order.cancel_all_pending_orders(dry_run=dry_run)

@mcp.tool()
def cancel_pending_orders_by_symbol(ctx: Context, symbol: str, dry_run: bool = False) -> dict:
	"""Cancel all pending orders for a specific symbol. Set dry_run=True to list what would be cancelled instead."""
	client = get_client(ctx)
	return client.order.cancel_pending_orders_by_symbol(symbol=symbol, dry_run=dry_run)

if __name__ == "__main__":
	load_dotenv()
	from metatrader_mcp.utils import resolve_transport_config, run_mcp

	parser = argparse.ArgumentParser(description="MetaTrader MCP Server")
	parser.add_argument("--login",    type=str, help="MT5 login")
	parser.add_argument("--password", type=str, help="MT5 password")
	parser.add_argument("--server",   type=str, help="MT5 server name")
	parser.add_argument("--path",     type=str, help="Path to MT5 terminal executable (optional)")
	parser.add_argument("--transport", type=str, choices=["sse", "stdio", "streamable-http"], default=None, help="MCP transport type (default: sse, env: MCP_TRANSPORT)")
	parser.add_argument("--host",     type=str, default=None, help="Host to bind for SSE/HTTP transport (default: 0.0.0.0, env: MCP_HOST)")
	parser.add_argument("--port",     type=int, default=None, help="Port to bind for SSE/HTTP transport (default: 8080, env: MCP_PORT)")

	args = parser.parse_args()

	# inject into lifespan via env vars
	if args.login:    os.environ["login"]    = args.login
	if args.password: os.environ["password"] = args.password
	if args.server:   os.environ["server"]   = args.server
	if args.path:     os.environ["MT5_PATH"] = args.path

	transport, host, port = resolve_transport_config(args.transport, args.host, args.port)

	# run the MCP server (must call mcp.run)
	run_mcp(mcp, transport, host, port)
