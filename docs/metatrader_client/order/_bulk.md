# Bulk operations 🧹

The close-all and cancel-all operations share one helper, `order/_bulk.py`, so
they all behave the same way.

Covered: `close_all_positions`, `close_all_positions_by_symbol`,
`close_all_profitable_positions`, `close_all_losing_positions`,
`cancel_all_pending_orders`, `cancel_pending_orders_by_symbol`.

## Dry run 🔍

Every one of them takes `dry_run: bool = False`. With `dry_run=True` nothing is
sent to the terminal and the result lists exactly what would be affected:

```python
result = client.order.close_all_losing_positions(dry_run=True)

result["message"]
# 'Dry run: would close 3 losing positions. Nothing was sent to the terminal.'

result["data"]["targets"]
# [{'id': 2, 'time': ..., 'symbol': 'EURUSD', 'type': 'BUY',
#   'volume': 0.1, 'open': 1.16412, 'profit': -5.0}, ...]
```

The preview carries `id`, `time`, `symbol`, `type`, `volume`, `open` and
`profit` — enough to recognise a position without the bookkeeping columns.

## Honest reporting ✅

These operations used to count attempts rather than successes: a run where
every close failed still reported `Close 5 positions success`. Now each item's
result is checked.

```python
result = client.order.close_all_positions()

# All succeeded
{'error': False,
 'message': 'Close 3 positions success',
 'data': {'succeeded': [...], 'failed': []}}

# Some failed
{'error': True,
 'message': 'Close 2 of 3 positions; 1 failed.',
 'data': {'succeeded': [...],
          'failed': [{'id': 2, ..., 'reason': "Invalid position ID '2'"}]}}
```

A failure does not stop the run — the remaining items are still attempted, and
every one of them is accounted for in `succeeded` or `failed`.

## Returns

- **`dict`**: `{"error": bool, "message": str, "data": Any}`
  - dry run: `data` holds `dry_run` and `targets`
  - otherwise: `data` holds `succeeded` and `failed`, each failure with its `reason`

Nothing to close is not an error: you get `Close 0 positions success`.
