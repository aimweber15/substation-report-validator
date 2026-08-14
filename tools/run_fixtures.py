#!/usr/bin/env python
"""
Runs all ten fixtures in tests/fixtures/ through V1 (R1-R5), V2 (R6-R10),
and V3 (R11-R17) -- not V4, which needs a G&T figure no fixture here is
about -- and reports which rules actually fired a CHECK against the rule
set the fixture must trip.

R17 is excluded from the checkable/fired comparison -- see
RENDERING_RULES below. It still runs and its outcome is shown separately
(informational), never counted toward PASS/FAIL.

FIXTURES below carries two expectation sets per fixture: first_expected
(the original brief) and corrected_expected. Six of the ten first
expectations were wrong -- not the app -- because they named only the
rule each fixture was built to teach, not the full set the rule TEXT
requires to fire. Each correction is traced to that text, not to what
this script observed when it ran; the reason strings below quote or
closely paraphrase the relevant rule.
"""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from validator.checks_v1 import check_r2, check_v1_for_file  # noqa: E402
from validator.checks_v2 import check_r6_r8, check_v2_for_file  # noqa: E402
from validator.checks_v3 import run_v3_for_file  # noqa: E402
from validator.config import ConfigError, load_config, load_crosswalk  # noqa: E402
from validator.load import LoadError, discover_workbook, find_source_file  # noqa: E402

FIXTURES_DIR = REPO_ROOT / "tests" / "fixtures"

# R17's rule text ("The reconciliation tab shows a grid... In a clean
# month, every cell reads 24") describes an artifact to render, not a
# comparison with a failure condition -- unlike R12 ("Stamps that should
# exist and do not are reported as missing") or R14 ("the number of
# readings must equal 24... a check that only asks whether the date
# appears will miss it"), both of which state what must be true and what
# happens when it isn't. Mechanically, checks_v3.py's R17 "off cell"
# count is a re-scan of the same grid[date][generic_id] != expected_n
# condition R14 already evaluated -- R17 has no comparison logic of its
# own. Counting it as a 21st fail-able rule double-counts every R14
# finding it displays. Tracked and shown, but excluded from PASS/FAIL.
RENDERING_RULES = {"R17"}

# (folder, display, first_expected, corrected_expected, reason_if_changed)
FIXTURES = [
    ("f0_clean_july", "F0  clean July",
     set(), set(), None),
    ("f8_november_clean", "F8  November clean (25hr, 01:00 x2)",
     set(), set(), None),
    ("f5_missing_day_and_duplicated_day", "F5  day removed + day duplicated",
     {"R12", "R15"}, {"R12", "R14", "R15"},
     "R14: 'the number of readings must equal 24... for every day.' A 0-of-N "
     "day and a 2N-of-N day both violate that regardless of the monthly total."),
    ("f4_one_substation_one_date_removed", "F4  one substation, one date removed",
     {"R12", "R14", "R17"}, {"R12", "R14"},
     "R17 dropped: it is a rendering of R14 (see RENDERING_RULES), not an "
     "independently-triggered rule."),
    ("f3_next_month_row", "F3  row at 08/01 00:00",
     {"R7", "R10"}, {"R7", "R9", "R10"},
     "R9: 'excluded from the totals AND reported' -- a mandatory companion to "
     "R7's exclusion, not a separate trigger."),
    ("f1_header_renamed", "F1  header renamed",
     {"R3"}, {"R3", "R4"},
     "Doc's own note on why R3 and R4 both say stop: a rename is simultaneously "
     "'the expected name is gone' (R3) and a foreign name present (R4)."),
    ("f7_substation_absent_all_month", "F7  substation absent all month",
     {"R16"}, {"R12", "R14", "R16"},
     "R12 ('stamps that should exist and do not') and R14 ('for every day') "
     "apply to every stamp/date of a zero-reading substation; R16 names the "
     "same finding at roster grain, it does not replace R12/R14."),
    ("f6_partial_day_20_of_24", "F6  20 of 24 rows one day",
     {"R14"}, {"R12", "R14"},
     "R12's missing-direction applies per substation (R13: never pooled) to "
     "the 4 deleted stamps, independent of R14 flagging the date's total."),
    ("f2_extra_unmapped_column", "F2  extra unmapped column",
     {"R4"}, {"R4"}, None),
    ("f8b_november_25th_hour_missing", "F8b November, 25th hour missing",
     {"R14"}, {"R12", "R14"},
     "The missing 2nd occurrence of the doubled fall-back stamp is itself a "
     "stamp R11's calendar says should exist and doesn't -- R12's own trigger, "
     "independent of R14 flagging the date's total."),
]


def run_one_fixture(folder_name):
    config_path = FIXTURES_DIR / folder_name / "config.json"
    config = load_config(config_path)
    crosswalk_rows = load_crosswalk(config, repo_root=REPO_ROOT)

    interval_path = find_source_file(config, "interval_file_pattern", REPO_ROOT)
    hourly_path = find_source_file(config, "hourly_file_pattern", REPO_ROOT)
    interval_report = discover_workbook(interval_path, "interval", config, crosswalk_rows, "interval_position")
    hourly_report = discover_workbook(hourly_path, "hourly", config, crosswalk_rows, "hourly_position")

    check_rows = []
    check_rows.extend(check_r2(config))
    check_rows.extend(check_v1_for_file(interval_report, crosswalk_rows, "interval_position", "expected_interval_header"))
    check_rows.extend(check_v1_for_file(hourly_report, crosswalk_rows, "hourly_position", "expected_hourly_header"))
    check_rows.extend(check_r6_r8(config))
    check_rows.extend(check_v2_for_file(interval_report, config))
    check_rows.extend(check_v2_for_file(hourly_report, config))
    v3_interval_rows, _ = run_v3_for_file(interval_report, config, crosswalk_rows, config["expected_interval_minutes"])
    v3_hourly_rows, _ = run_v3_for_file(hourly_report, config, crosswalk_rows, config["hourly_interval_minutes"])
    check_rows.extend(v3_interval_rows)
    check_rows.extend(v3_hourly_rows)

    return check_rows


def main():
    results = []
    for folder_name, display_name, first_expected, corrected_expected, reason in FIXTURES:
        try:
            check_rows = run_one_fixture(folder_name)
        except (ConfigError, LoadError) as e:
            results.append((display_name, first_expected, corrected_expected, reason, None, None, f"ERROR: {e}"))
            continue

        fired_all = {r.rule for r in check_rows if r.result == "CHECK"}
        fired = fired_all - RENDERING_RULES
        rendered = fired_all & RENDERING_RULES

        extra = fired - corrected_expected
        missing = corrected_expected - fired
        ok = not extra and not missing
        results.append((display_name, first_expected, corrected_expected, reason, fired, rendered, ok, extra, missing))

    name_w = max(len(r[0]) for r in results)
    exp_w = 12
    print(f"{'Fixture':<{name_w}}  {'1st expect':<{exp_w}}  {'Corrected':<{exp_w}}  {'Fired':<14}  {'Rendered':<9}  Result")
    print("-" * (name_w + 2 * exp_w + 60))

    all_ok = True
    special_alert = []
    changed_reasons = []
    for row in results:
        display_name = row[0]
        if len(row) == 7 and isinstance(row[-1], str) and row[-1].startswith("ERROR"):
            print(f"{display_name:<{name_w}}  ERROR: {row[-1]}")
            all_ok = False
            continue

        _, first_expected, corrected_expected, reason, fired, rendered, ok, extra, missing = row
        first_str = ",".join(sorted(first_expected)) or "(none)"
        corrected_str = ",".join(sorted(corrected_expected)) or "(none)"
        fired_str = ",".join(sorted(fired)) or "(none)"
        rendered_str = ",".join(sorted(rendered)) or "-"
        status = "PASS" if ok else "FAIL"
        if not ok:
            all_ok = False
        print(f"{display_name:<{name_w}}  {first_str:<{exp_w}}  {corrected_str:<{exp_w}}  "
              f"{fired_str:<14}  {rendered_str:<9}  {status}")
        if not corrected_expected and (fired or rendered):
            special_alert.append((display_name, fired, rendered))
        if extra:
            print(f"{'':<{name_w}}  {'':<{exp_w}}  {'':<{exp_w}}  extra fired: {sorted(extra)}")
        if missing:
            print(f"{'':<{name_w}}  {'':<{exp_w}}  {'':<{exp_w}}  did NOT fire (expected): {sorted(missing)}")
        if reason:
            changed_reasons.append((display_name, first_str, corrected_str, reason))

    print()
    if changed_reasons:
        print("Corrections to the original expectation, traced to rule text (not to this run):")
        for display_name, first_str, corrected_str, reason in changed_reasons:
            print(f"  {display_name}: {first_str} -> {corrected_str}")
            print(f"    {reason}")
    print()

    if special_alert:
        print("!! FALSE ALARM: a fixture expected to trip NOTHING fired or rendered a rule:")
        for name, fired, rendered in special_alert:
            print(f"   {name}: fired={sorted(fired)} rendered={sorted(rendered)}")
        print("   This is a checker bug, not a fixture-construction artifact. Stop here.")
    else:
        print("F0 and F8 both fired and rendered nothing -- no false alarm.")

    print()
    print("Overall:", "ALL MATCH" if all_ok else "SOME MISMATCHES (see FAIL rows and 'extra fired' above)")
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
