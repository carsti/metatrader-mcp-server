from ._bulk import apply_to_each
from .get_all_positions import get_all_positions
from .close_position import close_position

def close_all_positions(connection, dry_run: bool = False):
    """
    Close all open positions.

    Args:
        connection: The connection object to the MetaTrader platform.
        dry_run: List what would be closed without closing anything (default: False).

    Returns:
        A dictionary with an error flag, a message, and the affected positions.
    """
    return apply_to_each(
        connection,
        get_all_positions(connection),
        close_position,
        verb="Close",
        subject="positions",
        dry_run=dry_run,
    )
