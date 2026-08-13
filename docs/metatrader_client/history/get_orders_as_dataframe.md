# get_orders_as_dataframe 📜➡️📊

**Signature:**
```python
def get_orders_as_dataframe(
    connection,
    from_date: Optional[datetime] = None,
    to_date: Optional[datetime] = None,
    group: Optional[str] = None,
    full: bool = False
) -> pd.DataFrame
```

## What does it do?
Fetches historical orders and returns them as a pandas DataFrame for easy data crunching. Perfect for analysis and reporting! 📈

## Parameters
- **connection**: Your MetaTrader 5 connection object (must be connected!)
- **from_date**: Start date for history (default: 30 days ago)
- **to_date**: End date for history (default: now)
- **group**: (Optional) Filter by group
- **full**: Return every field mt5 provides instead of the working subset (default: False)

## Returns
- **pd.DataFrame**: Orders as a DataFrame, indexed by setup time if available.

## Columns

mt5 returns 24 fields per historical order. The default keeps the 11 that inform a decision:

`ticket`, `time_done`, `symbol`, `type`, `state`, `volume_initial`, `price_open`, `sl`, `tp`, `position_id`, `comment` — plus `time_setup` as the index.

Left out: the `_msc` twins of timestamps already present, fields that are zero once an order completes (`volume_current`, `price_stoplimit`, `time_expiration`), `magic` (constant for manual trading), and broker-internal fields. The list lives in `ORDER_COLUMNS`; pass `full=True` to get everything.

## Raises
- `OrdersHistoryError` if DataFrame creation fails

## Example Usage
```python
from metatrader_client.history import get_orders_as_dataframe

df = get_orders_as_dataframe(conn)
```

---

✨ _No orders? You’ll get an empty DataFrame, not an error!_
