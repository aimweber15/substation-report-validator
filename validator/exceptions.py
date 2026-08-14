"""
Data Quality exception flags (config.exception_flags) -- eleven named
counts per source file, for the Data Quality tab.

Distinct from R1-R20: these are quality counters, not PASS/CHECK/NOT RUN
judgements, and they feed only the Data Quality tab. Where a flag maps
directly onto something an R-rule already determined (missing_mapped_column
onto R3, unmapped_source_column onto R4's raw data), the count is derived
from that same source rather than re-implemented, so the two tabs cannot
quietly disagree with each other.
"""

from collections import Counter

from validator.checks_v2 import compute_window
from validator.checks_v3 import _is_blank, _in_window_stamp_counter
from validator.stamps import expected_stamps

SOLAR_SHARED_TYPES = {"Solar", "Shared"}


def compute_exception_counts(report, config, crosswalk_rows, step_minutes, missing_mapped_column_count):
    """Returns {flag_name: count} for one workbook (interval or hourly).

    missing_mapped_column_count is supplied by the caller, counted from
    that file's R3 CHECK rows (already computed for the Reconciliation
    tab) -- R3's own logic distinguishes an absent column from a renamed
    one, and re-deriving that here risked drifting from what R3 actually
    found.
    """
    window_start, window_end = compute_window(config["report_month"])
    zone = config["timezone"]["zone"]
    report_month = config["report_month"]

    zero_interval = 0
    negative_interval = 0
    blank_numeric = 0
    text_in_numeric = 0

    for generic_id, readings in report["readings_by_generic_id"].items():
        for ts, value in readings:
            if not (window_start <= ts < window_end):
                continue
            if _is_blank(value):
                blank_numeric += 1
                continue
            if isinstance(value, str):
                text_in_numeric += 1
                continue
            if value == 0:
                zero_interval += 1
            elif value < 0:
                negative_interval += 1

    # solar_shared_review is a roster fact, not a per-reading tally -- every
    # reading from a Solar/Shared substation would trip it, which is a
    # census (11,904 rows on the interval file) rather than a flag. Report
    # the substations themselves instead; see solar_shared_review_note().
    solar_shared_review = sum(
        1 for row in crosswalk_rows if row["location_type"] in SOLAR_SHARED_TYPES
    )

    date_range_mismatch = sum(
        1 for ts in report["primary_ts_values"] if not (window_start <= ts < window_end)
    )

    unmapped_source_column = sum(1 for m in report["column_matches"] if "generic_id" not in m)

    stamps, _ = expected_stamps(report_month, step_minutes, zone)
    expected_counter = Counter(stamps)
    duplicate_timestamp = 0
    for generic_id, readings in report["readings_by_generic_id"].items():
        actual_counter, _ = _in_window_stamp_counter(readings, window_start, window_end)
        for stamp, actual_n in actual_counter.items():
            allowed_n = expected_counter.get(stamp, 0)
            if allowed_n and actual_n > allowed_n:
                duplicate_timestamp += actual_n - allowed_n

    roster_ids = list(report["readings_by_generic_id"].keys())
    total_control_mismatch = 0
    for i, (ts, total_value) in enumerate(report["total_column_values"]):
        if not (window_start <= ts < window_end):
            continue
        computed = sum(
            0.0 if _is_blank(report["readings_by_generic_id"][gid][i][1])
            else report["readings_by_generic_id"][gid][i][1]
            for gid in roster_ids
        )
        actual = 0.0 if _is_blank(total_value) else total_value
        if abs(computed - actual) > 0.05:
            total_control_mismatch += 1

    return {
        "missing_timestamp": 0,
        "duplicate_timestamp": duplicate_timestamp,
        "zero_interval": zero_interval,
        "negative_interval": negative_interval,
        "blank_numeric": blank_numeric,
        "text_in_numeric": text_in_numeric,
        "date_range_mismatch": date_range_mismatch,
        "unmapped_source_column": unmapped_source_column,
        "missing_mapped_column": missing_mapped_column_count,
        "total_control_mismatch": total_control_mismatch,
        "solar_shared_review": solar_shared_review,
    }


def solar_shared_review_note(crosswalk_rows):
    """Four lines, one per Solar/Shared substation, naming it once with a
    plain-language reason to read its variance carefully. Same information
    as a per-reading count, without the census."""
    lines = [
        f"{row['generic_id']} ({row['location_type']}): net metering can "
        f"invert midday load -- read this substation's variance with that "
        f"in mind."
        for row in crosswalk_rows
        if row["location_type"] in SOLAR_SHARED_TYPES
    ]
    return "\n".join(lines)


EXCEPTION_FLAG_NOTES = {
    "missing_timestamp": (
        "Always 0 by construction: validator/load.py fails loudly "
        "(LoadError) on a missing or malformed timestamp before this tab "
        "is ever built. A row that violated this never reaches Step 4."
    ),
}
