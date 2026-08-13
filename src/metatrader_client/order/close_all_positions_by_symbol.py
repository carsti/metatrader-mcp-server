from ._bulk import apply_to_each
from .get_all_positions import get_all_positions
from .close_position import close_position

def close_all_positions_by_symbol(connection, symbol: str, dry_run: bool = False):
    """
    Close all open positions for a given symbol.

    Args:
        connection: The connection object to the MetaTrader platform.
        symbol: The symbol of the positions to close.
        dry_run: List what would be closed without closing anything (default: False).

    Returns:
        A dictionary with an error flag, a message, and the affected positions.
    """
    positions = get_all_positions(connection)
    matching = positions[positions["symbol"] == symbol] if not positions.empty else positions
    return apply_to_each(
        connection,
        matching,
        close_position,
        verb="Close",
        subject=f"{symbol} positions",
        dry_run=dry_run,
    )
