from ..exceptions import AccountInfoError, ConnectionError
from .get_account_info import get_account_info

def get_account_type(connection) -> str:
    """
    Get account type (real, demo, or contest).
    Returns:
        str: Account type ("real", "demo", or "contest").
    Raises:
        AccountInfoError: If account type cannot be retrieved.
        ConnectionError: If not connected to terminal.
    """
    account_info = get_account_info(connection)
    trade_mode = account_info["trade_mode"]
    # ENUM_ACCOUNT_TRADE_MODE: DEMO=0, CONTEST=1, REAL=2. These were previously
    # mapped one place off, which reported a demo account as "real" and a real
    # account as "contest" - the wrong direction to be wrong in for a field that
    # callers use to decide whether live money is at stake.
    if trade_mode == 0:
        return "demo"
    elif trade_mode == 1:
        return "contest"
    elif trade_mode == 2:
        return "real"
    else:
        return f"unknown ({trade_mode})"
