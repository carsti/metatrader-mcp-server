# get_account_type 🏷️

## What does it do?
Returns the account type: `"demo"`, `"contest"`, or `"real"`.

The label comes straight from `ENUM_ACCOUNT_TRADE_MODE` (MQL5), where
**0 = demo, 1 = contest, 2 = real**. A trade mode outside that enum is reported
as `"unknown (<value>)"` rather than guessed at.

> Until August 2026 this function mapped `0` to `"real"` — rotated by one
> position — so every demo account was reported as real (upstream issue #24).
> The wrong label also reached MCP clients through `get_trade_statistics()`.

## Parameters
- `connection`: The MetaTrader connection object (must be connected!).

## Returns
- `str`: Account type (`"demo"`, `"contest"`, `"real"`, or `"unknown (<value>)"`).

## Raises
- `AccountInfoError`: If account type can't be retrieved.
- `ConnectionError`: If not connected to the terminal.

## Example
```python
acc_type = get_account_type(connection)
print(f"Account type: {acc_type} 🏷️")
```

## Related

### `blocks_live_trading(connection) -> bool`
Fail-closed guard. Returns `False` **only** for trade modes 0 (demo) and 1
(contest); every other value — including one this library does not recognise —
returns `True`.

The name is deliberately negative. Under fail-closed semantics a positively
named `is_real_account()` would make `if is_real_account(): log("real account")`
emit a *false statement* whenever the trade mode is unknown. `blocks_live_trading`
has exactly one reading: `True` means block.

```python
if blocks_live_trading(connection):
    raise RuntimeError("simulation-only build refuses to touch this account")
```

### `classify_account(connection) -> tuple[str, bool]`
Returns `(label, blocks_live)` from a **single** read of the account info — use
it instead of calling `get_account_type()` and `blocks_live_trading()` back to
back, which costs two round-trips to the terminal.

### `classify_trade_mode(trade_mode) -> tuple[str, bool]`
The same classification as a pure function, for callers that already hold an
`account_info` dict and must not pay for a second read. `get_trade_statistics()`
uses it for exactly that reason.

---

> **Heads up:** Know your account type before you trade for real! 🧐
