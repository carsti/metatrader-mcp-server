# get_candles_by_date 🕰️

Fetch historical candle data for one or more symbols and timeframes between two dates. Perfect for backtesting, charting, or just time traveling through the markets! 🚀

## Parameters
- **connection**: The MetaTrader connection/session object.
- **symbol_name** (`Union[str, Sequence[str]]`): A symbol (e.g., 'EURUSD') or a list of them.
- **timeframe** (`Union[str, Sequence[str]]`): A timeframe (e.g., 'M1', 'H1', 'D1') or a list of them.
- **from_date** (`Optional[Union[str, datetime]]`): Start date as 'YYYY-MM-DD', 'YYYY-MM-DD HH:MM' or a datetime.
- **to_date** (`Optional[Union[str, datetime]]`): End date, same formats as from_date.
- **group** (`Optional[str]`, default='none'): Row grouping — `'timeframe'`, `'symbol'` or `'none'`. See below.
- **limit** (`int`, default=100): Maximum candles **per (symbol, timeframe) pair**, most recent first.

## Returns
- **`pd.DataFrame`**: DataFrame with candle data (open, high, low, close, volume, time, etc).
  - `df.attrs['errors']` holds one `{'symbol', 'timeframe', 'error'}` dict per pair that could not be retrieved.
  - `df.attrs['truncated']` holds one `{'symbol', 'timeframe', 'returned', 'available'}` dict per pair that had more candles than `limit` allowed.

## The row limit ⚠️

The total row count is `limit x symbols x timeframes`. Without a cap, a date range has no natural size and the open-ended fallbacks used to fetch 1000 candles per pair — nine pairs of that is roughly 180k tokens through an MCP client.

`limit` applies per pair, always keeping the **most recent** candles:

- With both dates, the range is fetched whole and trimmed.
- With only `from_date`, or with neither, `limit` is the fetch size itself.

Whenever trimming happens, the pair is recorded in `df.attrs['truncated']` so the caller knows there was more data rather than silently seeing a short answer. Raise `limit` deliberately: the payload grows with every pair.

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
2. Parses the dates once and puts them in order — a bad date fails the whole call before any fetching. 📅
3. Validates every symbol ❓ and timeframe ⏲️ **once**, not once per pair. A symbol check is an IPC round-trip, so doing it per pair cost 50% more round-trips than necessary.
4. Fetches each pair via the MetaTrader5 API, trimming to `limit`.
5. Failures are collected instead of raised, so one bad symbol does not sink the request.
6. Merges everything into a single DataFrame following `group`.

## Raises
- `ValueError`: Unparseable date, empty symbol/timeframe list, unrecognized `group`, or non-positive `limit`.
- `SymbolNotFoundError` / `InvalidTimeframeError` / `MarketDataError`: The first pair's error, but **only if every pair failed**. Otherwise failures land in `df.attrs['errors']`.

## Example Usage
```python
# Single pair - unchanged behaviour
candles = get_candles_by_date(conn, 'EURUSD', 'H1', '2024-01-01', '2024-01-31')

# Full matrix, blocked by symbol, 200 candles per pair
candles = get_candles_by_date(
    conn,
    ['EURUSD', 'GBPUSD'],
    ['H1', 'M15'],
    '2024-01-01',
    '2024-01-31',
    group='symbol',
    limit=200,
)
print(candles.head())
print(candles.attrs['errors'])     # pairs that failed, if any
print(candles.attrs['truncated'])  # pairs with more data than limit allowed
```

Enjoy your market time machine! ⏳✨
