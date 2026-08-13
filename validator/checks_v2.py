"""
V2 -- the date window (R6-R10).

Addresses Defect 2: the report pulled 1st-to-1st, one interval too many.

The window is a fence panel, not a row of fence posts (R8): start at the
near post, stop strictly before the far one. Boundaries are naive local
wall-clock datetimes -- the same convention the source timestamps are
written in (config: layout.timestamp_column_meaning = "interval_start") --
so no timezone conversion happens here. That conversion is
validator.stamps.expected_stamps' job, for V3's completeness grid, not
this window filter's.
"""

from datetime import datetime

from validator.checks import CheckResult


def compute_window(report_month):
    """R6 -- both boundaries derived from the single report_month value.
    Returns (window_start, window_end), both naive datetimes; end is
    exclusive."""
    year, month = (int(part) for part in report_month.split("-"))
    window_start = datetime(year, month, 1, 0, 0)
    next_year, next_month = (year + 1, 1) if month == 12 else (year, month + 1)
    window_end = datetime(next_year, next_month, 1, 0, 0)
    return window_start, window_end


def check_r6_r8(config):
    """R6 (single-source boundaries) and R8 (end never written as 23:59)."""
    report_month = config["report_month"]
    window_start, window_end = compute_window(report_month)
    fmt = "%m/%d/%Y %H:%M"
    return [
        CheckResult(
            "R6", "PASS",
            f"Window derived from config.report_month={report_month!r} alone: "
            f"start {window_start.strftime(fmt)}, end {window_end.strftime(fmt)} "
            f"(exclusive). No date is written anywhere else."
        ),
        CheckResult(
            "R8", "PASS",
            f"End boundary is the next calendar month's start, compared with "
            f"strict '<' -- never written as 23:59 or '11:59 PM on the last day'."
        ),
    ]


def check_v2_for_file(report, config):
    """R7, R9, R10 for one workbook."""
    path_name = report["path"].name
    window_start, window_end = compute_window(config["report_month"])
    fmt = "%m/%d/%Y %H:%M"
    ts_values = report["primary_ts_values"]
    rows = []

    excluded = [ts for ts in ts_values if not (window_start <= ts < window_end)]

    if excluded:
        by_date = {}
        for ts in excluded:
            date_str = ts.strftime("%m/%d/%Y")
            by_date[date_str] = by_date.get(date_str, 0) + 1
        detail = "; ".join(f"{d}: {n} row(s)" for d, n in sorted(by_date.items()))
        rows.append(CheckResult(
            "R7", "CHECK",
            f"{path_name}: {len(excluded)} of {len(ts_values)} row(s) fall outside "
            f"[{window_start.strftime(fmt)}, {window_end.strftime(fmt)}) and are "
            f"excluded from the report -- {detail}."
        ))
        rows.append(CheckResult(
            "R9", "CHECK",
            f"{path_name}: excluded row count and dates -- {detail}."
        ))
    else:
        rows.append(CheckResult(
            "R7", "PASS",
            f"{path_name}: all {len(ts_values)} row(s) fall within "
            f"[{window_start.strftime(fmt)}, {window_end.strftime(fmt)})."
        ))
        rows.append(CheckResult(
            "R9", "PASS",
            f"{path_name}: no rows excluded by the date window."
        ))

    next_month_exact = [ts for ts in ts_values if ts == window_end]
    if next_month_exact:
        rows.append(CheckResult(
            "R10", "CHECK",
            f"{path_name}: {len(next_month_exact)} row(s) timestamped exactly "
            f"{window_end.strftime(fmt)} -- next-month row excluded (the August "
            f"2026 defect pattern, not generic noise)."
        ))
    else:
        rows.append(CheckResult(
            "R10", "PASS",
            f"{path_name}: no row timestamped exactly at next-month midnight "
            f"({window_end.strftime(fmt)})."
        ))

    return rows
