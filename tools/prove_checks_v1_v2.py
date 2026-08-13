#!/usr/bin/env python
"""
Proof script for checks_v1 / checks_v2 -- exercises the CHECK branches that
the clean sample data never triggers. Not a full fixture (that's Step 6);
just enough synthetic input, shaped like validator.load.discover_workbook's
return dict, to prove R1/R3/R4 and R7/R9/R10 fire when something is wrong.
"""

import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from validator.checks_v1 import check_v1_for_file
from validator.checks_v2 import check_v2_for_file, compute_window

CROSSWALK_ROWS = [
    {"generic_id": "Sub A", "interval_position": 1, "expected_interval_header": "Sub A"},
    {"generic_id": "Sub B", "interval_position": 2, "expected_interval_header": "Sub B"},
    {"generic_id": "Sub C", "interval_position": 3, "expected_interval_header": "Sub C"},
]


def fake_report(path_name, column_matches, missing_positions, headers):
    return {
        "path": Path(path_name),
        "column_matches": column_matches,
        "missing_crosswalk_positions": missing_positions,
        "headers": headers,
        "header_row_idx": 1,
    }


def find(rows, rule, result):
    return [r for r in rows if r.rule == rule and r.result == result]


def main():
    # --- R1: header text present but swapped (the classic Defect 1 shape) ---
    swapped = fake_report(
        "swapped_SAMPLE.xlsx",
        column_matches=[
            {"column": 3, "letter": "C", "header": "Sub B", "position": 1},
            {"column": 4, "letter": "D", "header": "Sub A", "position": 2},
        ],
        missing_positions=[],
        headers=["Interval Start", "Interval End", "Sub B", "Sub A"],
    )
    rows = check_v1_for_file(swapped, CROSSWALK_ROWS[:2], "interval_position", "expected_interval_header")
    r1_check = find(rows, "R1", "CHECK")
    r3_check = find(rows, "R3", "CHECK")
    r4_check = find(rows, "R4", "CHECK")
    assert len(r1_check) == 2, f"expected 2 R1 CHECK rows for the swap, got {len(r1_check)}"
    assert not r3_check and not r4_check, "a pure swap should not trip R3 or R4 -- both names still exist in the file"
    assert "found 'Sub B' instead" in r1_check[0].message and "possible column reorder" in r1_check[0].message
    print("OK  R1 CHECK fires on swapped headers (Defect 1 shape), R3/R4 stay quiet:")
    for r in r1_check:
        print(f"      {r.message}")

    # --- R3 + R4: a plain rename -- the old name is gone, a foreign one replaces it ---
    renamed = fake_report(
        "renamed_SAMPLE.xlsx",
        column_matches=[
            {"column": 3, "letter": "C", "header": "Sub A", "position": 1},
            {"column": 4, "letter": "D", "header": "Sub B RENAMED", "position": 2},
        ],
        missing_positions=[],
        headers=["Interval Start", "Interval End", "Sub A", "Sub B RENAMED"],
    )
    rows = check_v1_for_file(renamed, CROSSWALK_ROWS[:2], "interval_position", "expected_interval_header")
    r3_check = find(rows, "R3", "CHECK")
    r4_check = find(rows, "R4", "CHECK")
    r1_check = find(rows, "R1", "CHECK")
    assert len(r3_check) == 1 and "Sub B" in r3_check[0].message, "rename should report the missing expected name via R3"
    assert len(r4_check) == 1 and "Sub B RENAMED" in r4_check[0].message, "rename should report the foreign header via R4"
    assert not r1_check, "a plain rename is not a reorder -- R1 should stay quiet"
    print("OK  R3 + R4 CHECK fire on a plain rename (name-based matching cannot survive it):")
    print(f"      {r3_check[0].message}")
    print(f"      {r4_check[0].message}")

    # --- R3: an expected column is entirely absent from the file ---
    short = fake_report(
        "short_SAMPLE.xlsx",
        column_matches=[
            {"column": 3, "letter": "C", "header": "Sub A", "position": 1},
        ],
        missing_positions=[2, 3],
        headers=["Interval Start", "Interval End", "Sub A"],
    )
    rows = check_v1_for_file(short, CROSSWALK_ROWS, "interval_position", "expected_interval_header")
    r3_check = find(rows, "R3", "CHECK")
    assert len(r3_check) == 2, f"expected 2 R3 CHECK rows, got {len(r3_check)}"
    assert any("Sub B" in r.message for r in r3_check)
    assert any("Sub C" in r.message for r in r3_check)
    print("OK  R3 CHECK fires and names each missing column by generic_id:")
    for r in r3_check:
        print(f"      {r.message}")

    # --- R4: a column present with no crosswalk entry at that position ---
    extra = fake_report(
        "extra_column_SAMPLE.xlsx",
        column_matches=[
            {"column": 3, "letter": "C", "header": "Sub A", "position": 1},
            {"column": 4, "letter": "D", "header": "Sub Z (new)", "position": 4},
        ],
        missing_positions=[2, 3],
        headers=["Interval Start", "Interval End", "Sub A", "Sub Z (new)"],
    )
    rows = check_v1_for_file(extra, CROSSWALK_ROWS, "interval_position", "expected_interval_header")
    r4_check = find(rows, "R4", "CHECK")
    assert len(r4_check) == 1, f"expected 1 R4 CHECK row, got {len(r4_check)}"
    assert "Sub Z (new)" in r4_check[0].message
    print(f"OK  R4 CHECK fires and names the unexpected column: {r4_check[0].message}")

    # --- R7/R9/R10: rows outside the window, including the exact-midnight one ---
    window_start, window_end = compute_window("2026-07")
    ts_values = [
        datetime(2026, 6, 30, 23, 45),   # before window -- previous-month leak
        datetime(2026, 7, 1, 0, 0),      # in window, first moment
        datetime(2026, 7, 31, 23, 45),   # in window, last moment
        datetime(2026, 8, 1, 0, 0),      # exactly next-month midnight -- R10
    ]
    bad_window = fake_report("leaky_window_SAMPLE.xlsx", [], [], [])
    bad_window["primary_ts_values"] = ts_values
    rows = check_v2_for_file(bad_window, {"report_month": "2026-07"})
    r7_check = find(rows, "R7", "CHECK")
    r9_check = find(rows, "R9", "CHECK")
    r10_check = find(rows, "R10", "CHECK")
    assert len(r7_check) == 1 and "2 of 4" in r7_check[0].message
    assert len(r9_check) == 1
    assert len(r10_check) == 1 and "08/01/2026 00:00" in r10_check[0].message
    print("OK  R7/R9/R10 CHECK fire on a leaky window:")
    print(f"      {r7_check[0].message}")
    print(f"      {r10_check[0].message}")

    print()
    print("All asserts passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
