from ._bulk import apply_to_each
from .get_all_pending_orders import get_all_pending_orders
from .cancel_pending_order import cancel_pending_order

def cancel_all_pending_orders(connection, dry_run: bool = False):
    """
    Cancels all pending orders.

    Args:
        connection: MetaTrader 5 connection object.
        dry_run: List what would be cancelled without cancelling anything (default: False).

    Returns:
        A dictionary with an error flag, a message, and the affected orders.
    """
    return apply_to_each(
        connection,
        get_all_pending_orders(connection),
        cancel_pending_order,
        verb="Cancel",
        subject="pending orders",
        dry_run=dry_run,
    )
