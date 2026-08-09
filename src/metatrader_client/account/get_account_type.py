from ..exceptions import AccountInfoError, ConnectionError
from .get_account_info import get_account_info

# ENUM_ACCOUNT_TRADE_MODE (MQL5):
#   0 = ACCOUNT_TRADE_MODE_DEMO
#   1 = ACCOUNT_TRADE_MODE_CONTEST
#   2 = ACCOUNT_TRADE_MODE_REAL
# https://www.mql5.com/en/docs/constants/environment_state/accountinformation
#
# This table used to read {0: "real", 1: "demo", 2: "contest"} -- rotated by one
# position, so every demo account was reported as real (upstream issue #24).
# The order below is the enum's, not a stylistic choice: do not "tidy" it.
_TRADE_MODE = {0: "demo", 1: "contest", 2: "real"}

# Trade modes provably free of real money. Anything not listed here blocks.
# Membership -- not absence -- is what grants permission; see blocks_live_trading.
_SIMULATED_MODES = frozenset({0, 1})


def classify_trade_mode(trade_mode) -> tuple:
    """
    Classify a raw ENUM_ACCOUNT_TRADE_MODE value. Pure: touches no terminal.

    Returns:
        tuple: ``(label, blocks_live)``. ``label`` is "demo", "contest", "real"
        or ``"unknown (<value>)"``. ``blocks_live`` is the fail-closed guard
        documented in :func:`blocks_live_trading`.

    Split out from :func:`classify_account` so a caller that already holds an
    ``account_info`` dict can classify without paying for a second read.
    """
    try:
        simulated = trade_mode in _SIMULATED_MODES
        label = _TRADE_MODE.get(trade_mode, f"unknown ({trade_mode})")
    except TypeError:
        # Unhashable trade_mode. MT5 never returns one, but a malformed or
        # mocked account_info can, and both the set test and the dict lookup
        # raise on it. Unclassifiable means blocked -- the guard must survive
        # inputs the enum does not describe, otherwise it is not fail-closed.
        simulated = False
        label = f"unknown ({trade_mode!r})"
    return label, not simulated


def classify_account(connection) -> tuple:
    """
    Read the account trade mode once and derive both facts callers need.

    Returns:
        tuple: ``(label, blocks_live)``, as described in
        :func:`classify_trade_mode`.

    This function exists so that a caller needing both facts pays a single
    round-trip to the terminal instead of two.

    Raises:
        AccountInfoError: If account information cannot be retrieved.
        ConnectionError: If not connected to terminal.
    """
    return classify_trade_mode(get_account_info(connection)["trade_mode"])


def get_account_type(connection) -> str:
    """
    Get account type ("demo", "contest" or "real").

    Returns:
        str: Account type, or ``"unknown (<value>)"`` for a trade mode outside
        ENUM_ACCOUNT_TRADE_MODE.

    Raises:
        AccountInfoError: If account type cannot be retrieved.
        ConnectionError: If not connected to terminal.
    """
    label, _ = classify_account(connection)
    return label


def blocks_live_trading(connection) -> bool:
    """
    Fail-closed guard: True unless the account is provably simulated.

    Only ENUM_ACCOUNT_TRADE_MODE values 0 (demo) and 1 (contest) return False.
    Every other value -- including one this library does not recognise -- returns
    True, so an unexpected trade mode blocks rather than silently permits.

    The name is deliberately negative and must stay that way. Under fail-closed
    semantics a positively-named ``is_real_account()`` would make
    ``if is_real_account(): log("real account")`` emit a *false statement*
    whenever the trade mode is unknown. ``blocks_live_trading`` has exactly one
    reading: True means block.

    Returns:
        bool: True if live trading must be blocked.

    Raises:
        AccountInfoError: If account information cannot be retrieved.
        ConnectionError: If not connected to terminal.
    """
    _, blocks_live = classify_account(connection)
    return blocks_live
