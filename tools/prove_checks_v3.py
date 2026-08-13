#!/usr/bin/env python
"""
Proof script for checks_v3 -- exercises R11-R17's CHECK and PASS paths
with synthetic (report, crosswalk_rows, config) inputs, not full workbook
fixtures (that's Step 6). Uses validator.stamps.expected_stamps() as the
source of truth for building both clean and deliberately-broken reading
sets, so the "clean" baseline can never drift from what the generator
itself considers clean.

Covers, in order: a full missing day, a partial day, a duplicate reading,
an off-grid/unexpected reading, and a zero-reading substation (July 2026,
no DST) -- then the fall-back ambiguity, both tolerated and broken both
directions (November 2026) -- then the spring-forward short day, clean
and broken (March 2026).
"""

import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from validator.checks_v3 import run_v3_for_file
from validator.stamps import expected_stamps, STAMP_FORMAT

ZONE = "America/Chicago"


def crosswalk_row(generic_id):
    return {"generic_id": generic_id}


def fake_report(path_name, readings_by_generic_id):
    return {"path": Path(path_name), "readings_by_generic_id": readings_by_generic_id}


def readings_from_stamps(stamp_strings, value=10.0):
    return [(datetime.strptime(s, STAMP_FORMAT), value) for s in stamp_strings]


def find(rows, rule, result):
    return [r for r in rows if r.rule == rule and r.result == result]


def main():
    # ================= July 2026: no DST, exercise the everyday breaks =================
    stamps, _ = expected_stamps("2026-07", 60, ZONE)

    sub_a_readings = readings_from_stamps(stamps)
    sub_a_readings.append((datetime.strptime("07/06/2026 08:30", STAMP_FORMAT), 10.0))  # off-grid

    sub_b = [s for s in stamps if not s.startswith("07/14/2026")]  # full day missing
    sub_b = [s for s in sub_b if not s.startswith("07/20/2026")] + \
        [s for s in stamps if s.startswith("07/20/2026")][:20]  # 07/20 cut to 20 of 24
    sub_b_readings = readings_from_stamps(sub_b)
    sub_b_readings.append((datetime.strptime("07/05/2026 08:00", STAMP_FORMAT), 10.0))  # duplicate

    report = fake_report("july_SAMPLE.xlsx", {
        "Sub A": sub_a_readings,
        "Sub B": sub_b_readings,
        "Sub C": [],  # zero readings all month
    })
    config = {"report_month": "2026-07", "timezone": {"zone": ZONE}}
    crosswalk_rows = [crosswalk_row("Sub A"), crosswalk_row("Sub B"), crosswalk_row("Sub C")]

    rows, grid = run_v3_for_file(report, config, crosswalk_rows, 60)

    r12_missing = [r for r in find(rows, "R12", "CHECK") if "missing" in r.message]
    r12_unexpected = [r for r in find(rows, "R12", "CHECK") if "not on the expected calendar" in r.message]
    r14_check = find(rows, "R14", "CHECK")
    r15_check = find(rows, "R15", "CHECK")
    r16_check = find(rows, "R16", "CHECK")

    assert any("Sub B" in r.message and "07/14/2026: 24" in r.message for r in r12_missing)
    assert any("Sub B" in r.message and "07/20/2026" in r.message for r in r12_missing)
    assert any("Sub A" in r.message for r in r12_unexpected)
    assert any("Sub B" in r.message and "07/14/2026: 0 of 24" in r.message for r in r14_check)
    assert any("Sub B" in r.message and "07/20/2026: 20 of 24" in r.message for r in r14_check)
    assert any("Sub B" in r.message for r in r15_check)
    assert len(r16_check) == 1 and "Sub C" in r16_check[0].message
    print("OK  July 2026 synthetic breaks -- R12 (missing full/partial day + unexpected),")
    print("    R14 (day counts), R15 (duplicate), R16 (zero-reading sub) all fire:")
    for r in r12_missing + r12_unexpected + r14_check + r15_check + r16_check:
        print(f"      {r.rule:<4} {r.message}")

    # ================= November 2026: the fall-back ambiguity =================
    nov_stamps, _ = expected_stamps("2026-11", 60, ZONE)
    config_nov = {"report_month": "2026-11", "timezone": {"zone": ZONE}}

    report = fake_report("nov_clean_SAMPLE.xlsx", {"Sub A": readings_from_stamps(nov_stamps)})
    rows, _ = run_v3_for_file(report, config_nov, [crosswalk_row("Sub A")], 60)
    assert not find(rows, "R15", "CHECK"), "clean Nov data (legit 2x on the fall-back hour) should not trip R15"
    r15a = find(rows, "R15a", "PASS")
    assert len(r15a) == 1 and "11/01/2026 01:00" in r15a[0].message
    print()
    print("OK  Nov 2026 clean (fall-back hour naturally doubled) -- R15 quiet, R15a explains why:")
    print(f"      {r15a[0].message}")

    over = readings_from_stamps(nov_stamps) + [(datetime(2026, 11, 1, 1, 0), 10.0)]
    report = fake_report("nov_triple_SAMPLE.xlsx", {"Sub A": over})
    rows, _ = run_v3_for_file(report, config_nov, [crosswalk_row("Sub A")], 60)
    r15_check = find(rows, "R15", "CHECK")
    assert len(r15_check) == 1 and "seen 3x (expected 2x)" in r15_check[0].message
    print(f"OK  Nov 2026, a THIRD copy of 01:00 -- R15 CHECK fires: {r15_check[0].message}")

    stamps_minus_one = list(nov_stamps)
    stamps_minus_one.remove("11/01/2026 01:00")  # list.remove drops only one of the two
    report = fake_report("nov_short_SAMPLE.xlsx", {"Sub A": readings_from_stamps(stamps_minus_one)})
    rows, _ = run_v3_for_file(report, config_nov, [crosswalk_row("Sub A")], 60)
    r12_missing = [r for r in find(rows, "R12", "CHECK") if "missing" in r.message]
    r14_check = find(rows, "R14", "CHECK")
    assert any("11/01/2026: 1" in r.message for r in r12_missing)
    assert any("11/01/2026: 24 of 25" in r.message for r in r14_check)
    print("OK  Nov 2026, only ONE copy of 01:00 -- a real shortfall, not tolerated by R15a:")
    for r in r12_missing + r14_check:
        print(f"      {r.rule:<4} {r.message}")

    # ================= March 2026: spring-forward, 23-hour day =================
    mar_stamps, _ = expected_stamps("2026-03", 60, ZONE)
    config_mar = {"report_month": "2026-03", "timezone": {"zone": ZONE}}

    report = fake_report("mar_clean_SAMPLE.xlsx", {"Sub A": readings_from_stamps(mar_stamps)})
    rows, _ = run_v3_for_file(report, config_mar, [crosswalk_row("Sub A")], 60)
    assert not find(rows, "R12", "CHECK") and not find(rows, "R14", "CHECK")
    print()
    print("OK  March 2026 clean (23-hour spring-forward day, no 02:00) -- R12/R14 quiet, 23 not hardcoded 24.")

    bogus = readings_from_stamps(mar_stamps) + [(datetime(2026, 3, 8, 2, 0), 10.0)]
    report = fake_report("mar_bogus_SAMPLE.xlsx", {"Sub A": bogus})
    rows, _ = run_v3_for_file(report, config_mar, [crosswalk_row("Sub A")], 60)
    r12_unexpected = [r for r in find(rows, "R12", "CHECK") if "not on the expected calendar" in r.message]
    r14_check = find(rows, "R14", "CHECK")
    assert any("03/08/2026: 1" in r.message for r in r12_unexpected)
    assert any("03/08/2026: 24 of 23" in r.message for r in r14_check)
    print("OK  March 2026, a bogus reading at the nonexistent 02:00 -- R12 unexpected + R14 24-of-23:")
    for r in r12_unexpected + r14_check:
        print(f"      {r.rule:<4} {r.message}")

    print()
    print("All asserts passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
