"""
Naive-UTC time window construction for the history endpoints.

READ THIS BEFORE "SIMPLIFYING" ANYTHING IN HERE. Two constructs below look
redundant and are not; both are load-bearing.

1. ``datetime.now(timezone.utc).replace(tzinfo=None)`` is not a verbose
   ``utcnow()``. The naive result is deliberate. ``mt5.history_deals_get()``,
   ``history_orders_get()``, ``history_deals_total()`` and
   ``history_orders_total()`` interpret a naive datetime as *server time (UTC)*
   and reject tz-aware datetimes. So the value must be naive AND must carry UTC
   wall-clock, which is exactly what this expression produces. Writing
   ``datetime.now()`` instead yields naive *local* time: from UTC-3 against a
   broker server on UTC+2/+3 that silently discards the last 3 to 6 hours of
   activity, which is why a closed position kept showing up as open
   (upstream issue #26).

2. ``_SERVER_OFFSET_SLACK`` is not padding for its own sake. Broker server
   clocks sit anywhere between UTC-12 and UTC+14, and the terminal timestamps
   deals in server time. A window ending exactly at "now" therefore truncates
   whatever the server has already stamped ahead of UTC. Removing the slack
   reintroduces issue #26 for every broker east of UTC.

Both defaults and caller-supplied dates are normalised here. Fixing only the
``is None`` branch is not enough: ``strptime("2026-08-08", "%Y-%m-%d")`` yields
naive midnight, MT5 reads it as UTC, and asking for "today's deals" returns
nothing.
"""

from datetime import date, datetime, timedelta, timezone
from typing import Optional, Tuple, Union

__all__ = ["utc_now_naive", "normalize_window"]

DateLike = Union[str, date, datetime, None]

#: How far back the window reaches when no lower bound is supplied.
DEFAULT_LOOKBACK = timedelta(days=30)

#: Slack applied to the upper bound to cover any broker server UTC offset.
_SERVER_OFFSET_SLACK = timedelta(days=1)

# Date-only formats. A match here means "the caller named a day, not an
# instant", which changes how the bound is snapped (start vs end of day).
_DATE_ONLY_FORMATS = ("%Y-%m-%d", "%Y/%m/%d", "%d/%m/%Y")

# Datetime formats not covered by datetime.fromisoformat (slash separators).
_DATETIME_FORMATS = (
    "%Y/%m/%d %H:%M:%S",
    "%Y/%m/%d %H:%M",
    "%d/%m/%Y %H:%M:%S",
    "%d/%m/%Y %H:%M",
)


def utc_now_naive() -> datetime:
    """Current UTC time as a naive datetime -- the shape MT5 expects."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _to_naive_utc(moment: datetime) -> datetime:
    """Drop the tz after converting to UTC; leave already-naive values alone."""
    if moment.tzinfo is not None:
        return moment.astimezone(timezone.utc).replace(tzinfo=None)
    return moment


def _parse(value: Union[str, date, datetime]) -> Tuple[datetime, bool]:
    """
    Parse one bound.

    Returns:
        tuple: ``(naive_utc_datetime, is_date_only)``.

    Raises:
        ValueError: If the value cannot be interpreted. Never silently
            substitutes a default -- a misread date produces a wrong window,
            which is worse than a loud failure.
    """
    if isinstance(value, datetime):
        return _to_naive_utc(value), False

    # datetime subclasses date, so this check must come second.
    if isinstance(value, date):
        return datetime(value.year, value.month, value.day), True

    if isinstance(value, str):
        text = value.strip()
        if text:
            for fmt in _DATE_ONLY_FORMATS:
                try:
                    return datetime.strptime(text, fmt), True
                except ValueError:
                    pass
            try:
                # Handles ISO 8601 including offsets such as "-03:00".
                return _to_naive_utc(datetime.fromisoformat(text)), False
            except ValueError:
                pass
            for fmt in _DATETIME_FORMATS:
                try:
                    return datetime.strptime(text, fmt), False
                except ValueError:
                    pass

    raise ValueError(
        f"Unrecognised date {value!r}. Expected ISO 8601 (offsets allowed), "
        "'YYYY-MM-DD', 'YYYY-MM-DD HH:MM', 'YYYY/MM/DD', 'DD/MM/YYYY', "
        "or a date/datetime object."
    )


def normalize_window(
    from_date: DateLike = None,
    to_date: DateLike = None,
    *,
    default_lookback: timedelta = DEFAULT_LOOKBACK,
) -> Tuple[datetime, datetime]:
    """
    Build a naive-UTC ``(start, end)`` window for the MT5 history calls.

    Args:
        from_date: Lower bound. ``None`` means ``now - default_lookback``.
        to_date: Upper bound. ``None`` means ``now + 1 day`` of server slack.
        default_lookback: How far back to reach when ``from_date`` is None.

    Returns:
        tuple: ``(start, end)``, both naive datetimes carrying UTC wall-clock.

    Behaviour worth knowing:
        - Aware input is converted to UTC and stripped of its tzinfo.
          Naive input is taken to be UTC already.
        - A date-only bound is snapped to the start (lower) or end (upper) of
          that day, then widened by one day outward, because the broker's
          server offset can put the caller's intended day anywhere in a 26-hour
          band relative to UTC.
        - Inverted bounds are swapped rather than returned as an empty window.

    Raises:
        ValueError: If either bound cannot be parsed.
    """
    now = utc_now_naive()

    if from_date is None:
        start = now - default_lookback
    else:
        start, start_is_date_only = _parse(from_date)
        if start_is_date_only:
            start = start.replace(
                hour=0, minute=0, second=0, microsecond=0
            ) - _SERVER_OFFSET_SLACK

    if to_date is None:
        end = now + _SERVER_OFFSET_SLACK
    else:
        end, end_is_date_only = _parse(to_date)
        if end_is_date_only:
            end = end.replace(
                hour=23, minute=59, second=59, microsecond=999999
            ) + _SERVER_OFFSET_SLACK

    if start > end:
        start, end = end, start

    return start, end
