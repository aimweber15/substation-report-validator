"""
V3 -- calendar completeness (R11-R17).

Addresses Defect 3: a full day silently missing from the download. The
rows were absent, not zero -- nothing in the file was wrong, the file was
simply short -- so no amount of looking at values finds it. Only a check
that builds the list of what should be there and compares finds this.

R11 and R14 are AMENDED (2026-08-12): the Meter Tech confirmed the
metering software stores LOCAL time (America/Chicago), not standard time
year-round. The expected stamp list, and the expected count per day, come
from validator.stamps.expected_stamps()'s timezone-aware calendar walk --
never from a hardcoded 24, and never from days * 24 or days * 96.

Everything here operates on IN-WINDOW readings only (V2's [window_start,
window_end) filter, reapplied). Out-of-window rows are V2's business
(R7/R9/R10 already report them); re-flagging them here as "unexpected"
would just be R7 wearing a V3 costume.

A non-blank cell is a reading. A blank cell in an existing row is "no
reading" for that substation at that stamp -- the wide layout means one
row serves all sixteen substations, so a day can go missing for one
substation without the row itself disappearing (fixture 6's shape).
"""

from collections import Counter

from validator.checks import CheckResult
from validator.checks_v2 import compute_window
from validator.stamps import expected_stamps, STAMP_FORMAT, DATE_FORMAT


def _is_blank(value):
    return value is None or (isinstance(value, str) and not value.strip())


def _in_window_stamp_counter(readings, window_start, window_end):
    """Ordered non-blank reading stamps, in-window only, as a Counter."""
    counter = Counter()
    by_date = Counter()
    for ts, value in readings:
        if _is_blank(value):
            continue
        if not (window_start <= ts < window_end):
            continue
        stamp = ts.strftime(STAMP_FORMAT)
        counter[stamp] += 1
        by_date[ts.strftime(DATE_FORMAT)] += 1
    return counter, by_date


def _fmt_counts(by_key):
    return "; ".join(f"{k}: {v}" for k, v in sorted(by_key.items()))


def run_v3_for_file(report, config, crosswalk_rows, step_minutes):
    """R11-R17 for one workbook. Returns (check_rows, grid).

    grid -- {date_str: {generic_id: actual_count}}, for the R17
    completeness tab (Step 4's job to render; this just builds the data).
    """
    path_name = report["path"].name
    report_month = config["report_month"]
    zone = config["timezone"]["zone"]
    roster = [row["generic_id"] for row in crosswalk_rows]

    stamps, per_date_counts = expected_stamps(report_month, step_minutes, zone)
    expected_counter = Counter(stamps)
    window_start, window_end = compute_window(report_month)

    rows = []

    rows.append(CheckResult(
        "R11", "PASS",
        f"{path_name}: generated {len(stamps)} expected stamp(s) for {report_month} "
        f"at {step_minutes}-minute resolution via a tz-aware calendar walk ({zone}), "
        f"crossed with {len(roster)} substation(s) on the roster. Short/long DST days "
        f"are correct by construction, never assumed 24."
    ))

    rows.append(CheckResult(
        "R13", "PASS",
        f"{path_name}: completeness checked independently for each of {len(roster)} "
        f"substation(s), never on pooled data -- a gap in one substation cannot be "
        f"masked by the other {len(roster) - 1}."
    ))

    grid = {date_str: {} for date_str in per_date_counts}

    missing_found = False
    unexpected_found = False
    duplicate_found = False
    day_count_found = False
    zero_reading_subs = []

    for generic_id in roster:
        readings = report["readings_by_generic_id"].get(generic_id, [])
        actual_counter, actual_by_date = _in_window_stamp_counter(readings, window_start, window_end)

        total_readings = sum(actual_counter.values())
        if total_readings == 0:
            zero_reading_subs.append(generic_id)

        for date_str in per_date_counts:
            grid[date_str][generic_id] = actual_by_date.get(date_str, 0)

        # R12 -- both directions, grouped by date (not a flat stamp list)
        missing_by_date = {}
        for stamp, expected_n in expected_counter.items():
            actual_n = actual_counter.get(stamp, 0)
            if actual_n < expected_n:
                date_str = stamp.split(" ")[0]
                missing_by_date[date_str] = missing_by_date.get(date_str, 0) + (expected_n - actual_n)
        if missing_by_date:
            missing_found = True
            rows.append(CheckResult(
                "R12", "CHECK",
                f"{path_name}: {generic_id} missing {sum(missing_by_date.values())} "
                f"expected reading(s) -- {_fmt_counts(missing_by_date)}."
            ))

        unexpected_by_date = {}
        for stamp, actual_n in actual_counter.items():
            if stamp not in expected_counter:
                date_str = stamp.split(" ")[0]
                unexpected_by_date[date_str] = unexpected_by_date.get(date_str, 0) + actual_n
        if unexpected_by_date:
            unexpected_found = True
            rows.append(CheckResult(
                "R12", "CHECK",
                f"{path_name}: {generic_id} has {sum(unexpected_by_date.values())} reading(s) "
                f"at stamp(s) not on the expected calendar -- {_fmt_counts(unexpected_by_date)}."
            ))

        # R14 -- reading count per day must equal that day's expected count
        day_mismatches = {}
        for date_str, expected_n in per_date_counts.items():
            actual_n = actual_by_date.get(date_str, 0)
            if actual_n != expected_n:
                day_mismatches[date_str] = (actual_n, expected_n)
        if day_mismatches:
            day_count_found = True
            detail = "; ".join(
                f"{d}: {a} of {e}" for d, (a, e) in sorted(day_mismatches.items())
            )
            rows.append(CheckResult(
                "R14", "CHECK",
                f"{path_name}: {generic_id} has a day where the reading count doesn't "
                f"match that day's expected count -- {detail}."
            ))

        # R15 / R15a -- duplicates, with the fall-back hour's legitimate
        # doubled stamps (expected_counter[stamp] == 2) tolerated at exactly
        # that count and flagged only outside it.
        excess_by_stamp = {}
        for stamp, actual_n in actual_counter.items():
            allowed_n = expected_counter.get(stamp, 0)
            if allowed_n and actual_n > allowed_n:
                excess_by_stamp[stamp] = (actual_n, allowed_n)
        if excess_by_stamp:
            duplicate_found = True
            detail = "; ".join(
                f"{s}: seen {a}x (expected {e}x)" for s, (a, e) in sorted(excess_by_stamp.items())
            )
            rows.append(CheckResult(
                "R15", "CHECK",
                f"{path_name}: {generic_id} has stamp(s) appearing more often than "
                f"expected -- {detail}."
            ))

    ambiguous_stamps = sorted(s for s, n in expected_counter.items() if n == 2)
    if ambiguous_stamps:
        rows.append(CheckResult(
            "R15a", "PASS",
            f"{path_name}: the fall-back date repeats {', '.join(ambiguous_stamps)} -- "
            f"the source cannot tell the two occurrences apart and neither can this "
            f"validator. Exactly two of each is expected and tolerated, not resolved; "
            f"only a count other than two is flagged."
        ))

    if not missing_found:
        rows.append(CheckResult(
            "R12", "PASS",
            f"{path_name}: no substation is missing an expected reading."
        ))
    if not unexpected_found:
        rows.append(CheckResult(
            "R12", "PASS",
            f"{path_name}: no substation has a reading outside the expected calendar."
        ))
    if not day_count_found:
        rows.append(CheckResult(
            "R14", "PASS",
            f"{path_name}: every substation's daily reading count matches that day's "
            f"expected count for all {len(per_date_counts)} date(s)."
        ))
    if not duplicate_found:
        rows.append(CheckResult(
            "R15", "PASS",
            f"{path_name}: no substation has a stamp appearing more often than expected."
        ))

    if zero_reading_subs:
        for generic_id in zero_reading_subs:
            rows.append(CheckResult(
                "R16", "CHECK",
                f"{path_name}: {generic_id} has ZERO readings this month -- "
                f"fully missing, not silently omitted."
            ))
    else:
        rows.append(CheckResult(
            "R16", "PASS",
            f"{path_name}: every one of {len(roster)} roster substation(s) has "
            f"at least one reading."
        ))

    off_cells = sum(
        1
        for date_str, expected_n in per_date_counts.items()
        for generic_id in roster
        if grid[date_str][generic_id] != expected_n
    )
    total_cells = len(per_date_counts) * len(roster)
    if off_cells:
        rows.append(CheckResult(
            "R17", "CHECK",
            f"{path_name}: completeness grid built ({len(per_date_counts)} date(s) x "
            f"{len(roster)} substation(s) = {total_cells} cell(s)); {off_cells} cell(s) "
            f"do not read the expected count for their date."
        ))
    else:
        rows.append(CheckResult(
            "R17", "PASS",
            f"{path_name}: completeness grid built ({len(per_date_counts)} date(s) x "
            f"{len(roster)} substation(s) = {total_cells} cell(s)); every cell reads "
            f"its date's expected count."
        ))

    return rows, grid
