from ._bulk import apply_to_each
from .get_all_positions import get_all_positions
from .close_position import close_position

def close_all_losing_positions(connection, dry_run: bool = False):
    """
    Close all losing positions.

    Close all positions that have a negative profit.

    Args:
        connection: The connection object to the MetaTrader platform.
        dry_run: List what would be closed without closing anything (default: False).

    Returns:
        A dictionary with an error flag, a message, and the affected positions.
    """
    positions = get_all_positions(connection)
    losing = positions[positions["profit"] < 0] if not positions.empty else positions
    return apply_to_each(
        connection,
        losing,
        close_position,
        verb="Close",
        subject="losing positions",
        dry_run=dry_run,
    )
