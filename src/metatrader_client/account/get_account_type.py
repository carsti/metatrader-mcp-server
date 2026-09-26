from ..exceptions import AccountInfoError, ConnectionError
from .get_account_info import get_account_info

def get_account_type(connection) -> str:
    """
    Get account type (demo, contest, or real).
    Returns:
        str: Account type ("demo", "contest", or "real").
    Raises:
        AccountInfoError: If account type cannot be retrieved.
        ConnectionError: If not connected to terminal.
    """
    account_info = get_account_info(connection)
    trade_mode = account_info["trade_mode"]
    if trade_mode == 0:
        return "demo"
    elif trade_mode == 1:
        return "contest"
    elif trade_mode == 2:
        return "real"
    else:
        return f"unknown ({trade_mode})"
