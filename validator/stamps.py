"""
Expected wall-clock stamp generation for the report month (V3 support).

Pure function, no file I/O. Used by V3 (R11-R17) to build the "what should
be there" side of the completeness comparison, instead of a hardcoded 24
rows/day that breaks on the two DST transition days.
"""

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

STAMP_FORMAT = "%m/%d/%Y %H:%M"
DATE_FORMAT = "%m/%d/%Y"


def expected_stamps(report_month, step_minutes, zone):
    """Return (stamps, per_date_counts) for one calendar month.

    stamps -- ordered list of local wall-clock strings, one per interval
        boundary from the local start of report_month up to (but not
        including) the local start of the next month.
    per_date_counts -- {"%m/%d/%Y": count} of stamps landing on each date,
        in date order, for V3's rows-per-day comparison.

    report_month is "YYYY-MM". step_minutes is the interval length (15 or
    60). zone is an IANA name such as "America/Chicago".

    Walks in UTC and converts each step back to local time, rather than
    multiplying days by 24 or by (1440 / step_minutes): a spring-forward
    day is short an hour and a fall-back day repeats one, and only a
    UTC-driven walk produces that automatically. On the fall-back day the
    repeated local hour appears twice in `stamps`, once per UTC instant --
    the source export cannot tell the two apart either, so this generator
    doesn't pretend to.
    """
    tz = ZoneInfo(zone)
    year, month = (int(part) for part in report_month.split("-"))
    local_start = datetime(year, month, 1, 0, 0, tzinfo=tz)
    next_year, next_month = (year + 1, 1) if month == 12 else (year, month + 1)
    local_end = datetime(next_year, next_month, 1, 0, 0, tzinfo=tz)

    utc_cursor = local_start.astimezone(timezone.utc)
    utc_end = local_end.astimezone(timezone.utc)
    step = timedelta(minutes=step_minutes)

    stamps = []
    per_date_counts = {}
    while utc_cursor < utc_end:
        local_stamp = utc_cursor.astimezone(tz)
        date_str = local_stamp.strftime(DATE_FORMAT)
        stamps.append(local_stamp.strftime(STAMP_FORMAT))
        per_date_counts[date_str] = per_date_counts.get(date_str, 0) + 1
        utc_cursor += step

    return stamps, per_date_counts
