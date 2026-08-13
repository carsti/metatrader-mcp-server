from ._bulk import apply_to_each
from .get_pending_orders_by_symbol import get_pending_orders_by_symbol
from .cancel_pending_order import cancel_pending_order

def cancel_pending_orders_by_symbol(connection, symbol: str, dry_run: bool = False):
    """
    Cancel all pending orders with the given symbol name.

    Args:
        connection: The connection object to the MetaTrader platform.
        symbol: The symbol name of the orders to be canceled.
        dry_run: List what would be cancelled without cancelling anything (default: False).

    Returns:
        A dictionary with an error flag, a message, and the affected orders.
    """
    return apply_to_each(
        connection,
        get_pending_orders_by_symbol(connection, symbol),
        cancel_pending_order,
        verb="Cancel",
        subject=f"{symbol} pending orders",
        dry_run=dry_run,
    )
