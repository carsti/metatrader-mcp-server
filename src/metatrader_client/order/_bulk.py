"""Shared machinery for the bulk close/cancel operations.

Every one of them does the same thing: pick a set of positions or orders, then
act on each. Keeping that here means they all report honestly (an item that
failed is not counted as closed) and all support the same dry run.
"""

from typing import Any, Callable, Dict, List, Optional

import pandas as pd

# What a caller needs to recognise a target in a dry run. Anything else on the
# frame is bookkeeping and only makes the preview harder to read.
PREVIEW_COLUMNS = ("id", "time", "symbol", "type", "volume", "open", "profit")


def apply_to_each(
    connection,
    targets: Optional[pd.DataFrame],
    action: Callable[[Any, Any], Dict[str, Any]],
    *,
    verb: str,
    subject: str,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """Run a per-item action over a frame of targets, or preview it.

    Args:
        connection: MT5 connection object
        targets: The rows to act on. Must carry an 'id' column.
        action: Callable(connection, id) returning the usual
            {"error": bool, "message": str, "data": Any} result.
        verb: What the operation does, e.g. 'Close' or 'Cancel'.
        subject: What it acts on, e.g. 'positions' or 'pending orders'.
        dry_run: Report what would happen without sending anything.

    Returns:
        dict: {"error": bool, "message": str, "data": Any}. On a dry run, data
        holds 'dry_run' and 'targets'. Otherwise it holds 'succeeded' and
        'failed', the latter carrying each item's 'reason'.
    """
    preview = _preview(targets)

    if dry_run:
        return {
            "error": False,
            "message": (
                f"Dry run: would {verb.lower()} {len(preview)} {subject}. "
                "Nothing was sent to the terminal."
            ),
            "data": {"dry_run": True, "targets": preview},
        }

    succeeded: List[Dict[str, Any]] = []
    failed: List[Dict[str, Any]] = []
    for target in preview:
        result = action(connection, target["id"])
        if isinstance(result, dict) and result.get("error"):
            failed.append({**target, "reason": result.get("message")})
        else:
            succeeded.append(target)

    if failed:
        return {
            "error": True,
            "message": (
                f"{verb} {len(succeeded)} of {len(preview)} {subject}; {len(failed)} failed."
            ),
            "data": {"succeeded": succeeded, "failed": failed},
        }
    return {
        "error": False,
        "message": f"{verb} {len(succeeded)} {subject} success",
        "data": {"succeeded": succeeded, "failed": []},
    }


def _preview(targets: Optional[pd.DataFrame]) -> List[Dict[str, Any]]:
    """Reduce a target frame to the columns worth showing, as plain records."""
    if targets is None or targets.empty:
        return []
    columns = [column for column in PREVIEW_COLUMNS if column in targets.columns]
    return targets[columns].to_dict(orient="records")
