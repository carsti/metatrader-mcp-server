"""Unit tests for date-argument parsing in history.get_deals.

These are pure tests: they exercise ``_parse_date_arg`` only and do NOT open a
MetaTrader 5 connection (MetaTrader5 must merely be importable).
"""
from datetime import datetime

from metatrader_client.history.get_deals import _parse_date_arg


def test_date_only_to_date_is_inclusive_end_of_day():
    # Regression: a bare 'YYYY-MM-DD' to_date previously resolved to midnight
    # (00:00:00), which EXCLUDED the named day from history_deals_get. It must
    # now cover the whole day so to_date='YYYY-MM-DD' includes day D.
    assert _parse_date_arg("2026-06-23", end_of_day=True) == datetime(2026, 6, 23, 23, 59, 59)


def test_date_only_from_date_is_start_of_day():
    assert _parse_date_arg("2026-06-23", end_of_day=False) == datetime(2026, 6, 23, 0, 0, 0)


def test_accepts_iso_datetime_with_T_separator():
    assert _parse_date_arg("2026-06-23T14:30:00") == datetime(2026, 6, 23, 14, 30, 0)


def test_accepts_iso_datetime_with_space_separator():
    assert _parse_date_arg("2026-06-23 14:30:00") == datetime(2026, 6, 23, 14, 30, 0)


def test_explicit_time_is_not_overridden_by_end_of_day():
    # An explicit time is authoritative; the end_of_day flag must not clobber it.
    assert _parse_date_arg("2026-06-23T14:30:00", end_of_day=True) == datetime(2026, 6, 23, 14, 30, 0)


def test_datetime_object_passes_through_unchanged():
    dt = datetime(2026, 6, 23, 8, 15, 0)
    assert _parse_date_arg(dt, end_of_day=True) is dt
