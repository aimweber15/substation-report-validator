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
from validator.config import ConfigError, load_config, load_crosswalk, unconfirmed_assumptions, REPO_ROOT
from validator.load import LoadError, find_source_file, discover_workbook, print_report


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

    check_rows = []
    check_rows.extend(check_r2(config))
    check_rows.extend(check_v1_for_file(
        interval_report, crosswalk_rows, "interval_position", "expected_interval_header"
    ))
    check_rows.extend(check_v1_for_file(
        hourly_report, crosswalk_rows, "hourly_position", "expected_hourly_header"
    ))
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

    print("V1 (R1-R5), V2 (R6-R10), and V3 (R11-R17) results:")
    print()
    print_check_rows(check_rows)

    return 0


if __name__ == "__main__":
    sys.exit(main())
