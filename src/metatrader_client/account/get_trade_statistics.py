from typing import Dict, Any
from ..exceptions import AccountInfoError, ConnectionError
from .get_account_info import get_account_info
from .get_account_type import classify_trade_mode

def get_trade_statistics(connection) -> Dict[str, Any]:
    """
    Get basic trade statistics for the account.
    Returns:
        Dict[str, Any]: Dictionary with trade statistics:
            - balance: Current balance
            - equity: Current equity
            - profit: Current floating profit/loss
            - margin_level: Current margin level
            - free_margin: Available margin for trading
            - account_type: Account type (real, demo, contest)
            - leverage: Account leverage
            - currency: Account currency
    Raises:
        AccountInfoError: If statistics cannot be retrieved.
        ConnectionError: If not connected to terminal.
    """
    account_info = get_account_info(connection)
    # Classify from the dict already in hand. Calling get_account_type() or
    # classify_account() here would re-read the account from the terminal, and
    # this feeds the most-used MCP tool (get_account_info).
    account_type, _ = classify_trade_mode(account_info["trade_mode"])
    stats = {
        "balance": account_info["balance"],
        "equity": account_info["equity"],
        "profit": account_info["profit"],
        "margin_level": account_info["margin_level"],
        "free_margin": account_info["margin_free"],
        "account_type": account_type,
        "leverage": account_info["leverage"],
        "currency": account_info["currency"],
    }
    return stats
