# get_deals_as_dataframe 🧾➡️📊

**Signature:**
```python
def get_deals_as_dataframe(
    connection,
    from_date: Optional[datetime] = None,
    to_date: Optional[datetime] = None,
    group: Optional[str] = None,
    full: bool = False
) -> pd.DataFrame
```

## What does it do?
Fetches historical deals and returns them as a pandas DataFrame for easy data analysis and manipulation. Super handy for quants and data nerds! 🤓

## Parameters
- **connection**: Your MetaTrader 5 connection object (must be connected!)
- **from_date**: Start date for history (default: 30 days ago)
- **to_date**: End date for history (default: now)
- **group**: (Optional) Filter by group
- **full**: Return every field mt5 provides instead of the working subset (default: False)

## Returns
- **pd.DataFrame**: Deals as a DataFrame, indexed by time if available.

## Columns

mt5 returns 18 fields per deal. The default keeps the 11 that inform a decision — roughly 30% smaller as CSV, with nothing actionable lost:

`ticket`, `symbol`, `type`, `entry`, `position_id`, `volume`, `price`, `commission`, `swap`, `profit`, `comment` — plus `time` as the index.

Left out: `order` (redundant with `position_id`), `time_msc` (redundant with the index), `magic` and `fee` (constant for manual trading), `reason` and `external_id` (broker-internal). The list lives in `DEAL_COLUMNS`; pass `full=True` to get everything.

## Raises
- `DealsHistoryError` if DataFrame creation fails

## Example Usage
```python
from metatrader_client.history import get_deals_as_dataframe

df = get_deals_as_dataframe(conn)
```

---

✨ _No deals? You’ll get an empty DataFrame, not a frown!_
