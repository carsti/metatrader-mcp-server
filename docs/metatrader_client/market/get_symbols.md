# get_symbols 🗂️

Get a list of all available market symbols, optionally filtered by group. Great for discovering what's tradable! 🧭

## Parameters
- **connection**: The MetaTrader connection/session object.
- **group** (`Optional[str]`): Filter symbols by group (e.g., '*USD*' for all USD pairs).
- **use_cache** (`bool`, default=True): Serve from the session cache when a fresh entry exists.

## Returns
- **`List[str]`**: List of symbol names matching the filter. The list is a copy, so mutating it does not disturb the cache.

## How It Works
1. Queries MetaTrader5 for all symbols, or those matching the group. 🔍
2. Returns a list of symbol names.

## Caching ⚡

`mt5.symbols_get` marshals a full `SymbolInfo` struct per symbol across the IPC boundary, and this function only reads the names off them. Brokers commonly expose thousands of symbols, and the list does not change within a session, so results are cached per group for `CACHE_TTL_SECONDS` (60s).

The cache is cleared automatically on connect and disconnect, so a reconnect to a different account never serves the previous account's symbols. Call `clear_symbols_cache()` to drop it by hand, or pass `use_cache=False` to force a fresh read.

This matters most for candle fetching, where every symbol is validated before its candles are pulled.

## Example Usage
```python
symbols = get_symbols(conn, '*JPY*')
print(symbols)

from metatrader_client.market.get_symbols import clear_symbols_cache
clear_symbols_cache()  # force the next call to hit the terminal
```

Explore the world of tradable assets! 🌎✨
