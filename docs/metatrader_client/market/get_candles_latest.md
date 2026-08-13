# get_candles_latest 🔥

Fetch the latest N candles for one or more symbols and timeframes. Great for live dashboards, quick analyses, or just keeping your finger on the market pulse! 📊

## Parameters
- **connection**: The MetaTrader connection/session object.
- **symbol_name** (`Union[str, Sequence[str]]`): A symbol (e.g., 'EURUSD') or a list of them.
- **timeframe** (`Union[str, Sequence[str]]`): A timeframe (e.g., 'M1', 'H1', 'D1') or a list of them.
- **count** (`int`, default=100): Number of latest candles to fetch **per (symbol, timeframe) pair**.
- **group** (`Optional[str]`, default='none'): Row grouping — `'timeframe'`, `'symbol'` or `'none'`. See below.

## Returns
- **`pd.DataFrame`**: DataFrame with the latest candle data (open, high, low, close, volume, time, etc).
  - `df.attrs['errors']` holds one `{'symbol', 'timeframe', 'error'}` dict per pair that could not be retrieved.

## Columns and ordering

Identifier columns appear only for the dimensions that actually vary, so a single symbol with a single timeframe returns exactly the frame it always did:

| symbols | timeframes | extra columns | `group` |
|---|---|---|---|
| 1 | 1 | none | ignored |
| 1 | N | `timeframe` | ignored |
| N | 1 | `symbol` | ignored |
| N | M | `symbol` + `timeframe` | applied |

With more than one symbol **and** more than one timeframe:

- `group='timeframe'` — leading columns `timeframe,symbol`; rows blocked by timeframe, then symbol, then time descending.
- `group='symbol'` — leading columns `symbol,timeframe`; rows blocked by symbol, then timeframe, then time descending.
- `group='none'` (default) — leading columns `symbol,timeframe`; no blocks, everything merged into one stream ordered by time descending.

Symbols and timeframes are ordered as you passed them, not alphabetically. Duplicates are dropped.

## How It Works
1. Normalizes symbol_name and timeframe into lists. 📋
2. For each (symbol, timeframe) pair: checks the symbol 🔎, validates the timeframe ⏰, fetches candles via the MetaTrader5 API.
3. Failures are collected instead of raised, so one bad symbol does not sink the request.
4. Merges everything into a single DataFrame following `group`.

## Raises
- `SymbolNotFoundError` / `InvalidTimeframeError` / `MarketDataError`: The first pair's error, but **only if every pair failed**. Otherwise failures land in `df.attrs['errors']`.
- `ValueError`: Empty symbol/timeframe list, or an unrecognized `group`.

## Example Usage
```python
# Single pair - unchanged behaviour
candles = get_candles_latest(conn, 'EURUSD', 'M5', 50)

# Several symbols on one timeframe
candles = get_candles_latest(conn, ['EURUSD', 'GBPUSD'], 'H1', 50)

# Full matrix, blocked by timeframe
candles = get_candles_latest(
    conn, ['EURUSD', 'GBPUSD'], ['H1', 'M15'], count=50, group='timeframe'
)
print(candles.head())
print(candles.attrs['errors'])  # pairs that failed, if any
```

Stay up-to-date with the markets! 🚦
