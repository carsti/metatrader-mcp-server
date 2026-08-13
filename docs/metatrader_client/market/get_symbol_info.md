# get_symbol_info 🏷️

Retrieve the trading specification of a symbol. Check this before sizing an order — it is what tells you the minimum volume, the volume step and the price precision. 🕵️‍♂️

## Parameters
- **connection**: The MetaTrader connection/session object.
- **symbol_name** (`str`): The symbol (e.g., 'EURUSD') you want info for.
- **full** (`bool`, default=False): Return every attribute of the SDK struct instead of the trading subset.

## Returns
- **`Dict[str, Any]`**: The symbol's fields. Fields the broker does not expose are omitted rather than returned as `None`.

## Default fields

MT5's `SymbolInfo` carries dozens of attributes, most of which say nothing about how to trade the instrument. The default result keeps what sizing, precision, limits and cost decisions need — the list lives in `SYMBOL_INFO_FIELDS`:

| Group | Fields |
|---|---|
| Identity | `name`, `description`, `path`, `visible` |
| Currencies | `currency_base`, `currency_profit`, `currency_margin` |
| Precision | `digits`, `point`, `trade_tick_size`, `trade_tick_value` |
| Sizing | `volume_min`, `volume_max`, `volume_step`, `trade_contract_size` |
| Cost & rules | `spread`, `swap_long`, `swap_short`, `trade_mode`, `trade_stops_level` |

Pass `full=True` for the whole struct — several times larger, and mostly session and margin bookkeeping.

## How It Works
1. Queries MetaTrader5 for the symbol. 📡
2. Picks the fields the broker actually exposes.
3. Returns them in a Python dictionary for easy access.

## Raises
- `SymbolNotFoundError`: If the symbol doesn't exist.

## Example Usage
```python
info = get_symbol_info(conn, 'EURUSD')
print(info['spread'], info['trade_mode'])

# Round a volume to something the broker will accept
step = info['volume_step']
volume = max(info['volume_min'], round(desired / step) * step)

everything = get_symbol_info(conn, 'EURUSD', full=True)
```

Uncover all the secrets of your favorite symbols! 🕵️‍♀️✨
