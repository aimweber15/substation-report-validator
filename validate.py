#!/usr/bin/env python
"""
Substation Report Validator -- command-line entry point.

Step 1: load config.json and crosswalk.csv, open both source workbooks
read-only, and report what is actually in them. No R1-R20 rules run here
and no PASS/CHECK judgement is made -- that starts in Step 2.
"""

import sys

from validator import __version__
from validator.checks import print_check_rows
from validator.checks_v1 import check_r2, check_v1_for_file
from validator.checks_v2 import check_r6_r8, check_v2_for_file
from validator.checks_v3 import run_v3_for_file
from validator.checks_v4 import check_v4
from validator.config import ConfigError, load_config, load_crosswalk, unconfirmed_assumptions, REPO_ROOT
from validator.exceptions import EXCEPTION_FLAG_NOTES, compute_exception_counts, solar_shared_review_note
from validator.final_report import build_final_report_data
from validator.load import LoadError, find_source_file, discover_workbook, print_report
from validator.workbook import build_reconciliation_rows, build_workbook


def main():
    print(f"Substation Report Validator v{__version__}")
    print(f"Reading config from: {REPO_ROOT / 'config.json'}")
    print()

    try:
        config = load_config()
        crosswalk_rows = load_crosswalk(config, repo_root=REPO_ROOT)
    except ConfigError as e:
        print(f"CONFIG ERROR: {e}", file=sys.stderr)
        return 1

    print(f"Report month: {config['report_month']}")
    print(f"Crosswalk: {len(crosswalk_rows)} active location(s) loaded from {config['crosswalk_file']}")
    print()
    print("Assumptions this run is operating under (config.json 'unconfirmed' list):")
    assumptions = unconfirmed_assumptions(config)
    if not assumptions:
        print("  unconfirmed: none")
    else:
        for key, value in assumptions.items():
            print(f"  ASSUMPTION -- {key} = {value!r} (not yet confirmed)")
    print()

    try:
        interval_path = find_source_file(config, "interval_file_pattern", REPO_ROOT)
        hourly_path = find_source_file(config, "hourly_file_pattern", REPO_ROOT)

        interval_report = discover_workbook(
            interval_path, "interval", config, crosswalk_rows, position_field="interval_position"
        )
        hourly_report = discover_workbook(
            hourly_path, "hourly", config, crosswalk_rows, position_field="hourly_position"
        )
    except LoadError as e:
        print(f"LOAD ERROR: {e}", file=sys.stderr)
        return 1

    print_report(interval_report)
    print_report(hourly_report)

    interval_v1_rows = check_v1_for_file(
        interval_report, crosswalk_rows, "interval_position", "expected_interval_header"
    )
    hourly_v1_rows = check_v1_for_file(
        hourly_report, crosswalk_rows, "hourly_position", "expected_hourly_header"
    )

    check_rows = []
    check_rows.extend(check_r2(config))
    check_rows.extend(interval_v1_rows)
    check_rows.extend(hourly_v1_rows)
    check_rows.extend(check_r6_r8(config))
    check_rows.extend(check_v2_for_file(interval_report, config))
    check_rows.extend(check_v2_for_file(hourly_report, config))

    interval_v3_rows, interval_grid = run_v3_for_file(
        interval_report, config, crosswalk_rows, config["expected_interval_minutes"]
    )
    hourly_v3_rows, hourly_grid = run_v3_for_file(
        hourly_report, config, crosswalk_rows, config["hourly_interval_minutes"]
    )
    check_rows.extend(interval_v3_rows)
    check_rows.extend(hourly_v3_rows)

    final_report_data = build_final_report_data(interval_report, hourly_report, config, crosswalk_rows)
    check_rows.extend(check_v4(config, final_report_data["total_c"]))

    print("V1 (R1-R5), V2 (R6-R10), V3 (R11-R17), and V4 (R18-R20) results:")
    print()
    print_check_rows(check_rows)
    print()

    missing_mapped_column_interval = sum(
        1 for r in interval_v1_rows if r.rule == "R3" and r.result == "CHECK"
    )
    missing_mapped_column_hourly = sum(
        1 for r in hourly_v1_rows if r.rule == "R3" and r.result == "CHECK"
    )
    interval_exception_counts = compute_exception_counts(
        interval_report, config, crosswalk_rows, config["expected_interval_minutes"],
        missing_mapped_column_interval,
    )
    hourly_exception_counts = compute_exception_counts(
        hourly_report, config, crosswalk_rows, config["hourly_interval_minutes"],
        missing_mapped_column_hourly,
    )

    exception_notes = dict(EXCEPTION_FLAG_NOTES)
    exception_notes["solar_shared_review"] = solar_shared_review_note(crosswalk_rows)

    out_path = REPO_ROOT / "outputs" / f"substation_report_{config['report_month']}.xlsx"
    build_workbook(
        interval_report, hourly_report, config, crosswalk_rows,
        check_rows, final_report_data, hourly_grid, interval_grid,
        interval_exception_counts, hourly_exception_counts, exception_notes,
        __version__, out_path,
    )
    print(f"Wrote output workbook: {out_path}")
    print()

    status, reconciliation_rows = build_reconciliation_rows(check_rows)
    print("=" * 70)
    print("RECONCILIATION TAB -- status row and rule table")
    print("=" * 70)
    print(f"STATUS: {status}")
    print()
    rule_width = max(len(r) for r, _, _ in reconciliation_rows)
    print(f"{'Rule':<{rule_width}}  {'Result':<7}  Message")
    print("-" * 70)
    for rule, result, message in reconciliation_rows:
        print(f"{rule:<{rule_width}}  {result:<7}  {message}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
