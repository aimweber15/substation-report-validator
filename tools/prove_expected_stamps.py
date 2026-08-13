#!/usr/bin/env python
"""
Proof script for validator.stamps.expected_stamps -- run directly, no
pytest. Asserts the three DST cases called out when the function was
specced, then prints a short report. Exits non-zero on any failed assert.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from validator.stamps import expected_stamps

ZONE = "America/Chicago"


def check(report_month, step_minutes, expected_count, label):
    stamps, per_date_counts = expected_stamps(report_month, step_minutes, ZONE)
    assert len(stamps) == expected_count, (
        f"{label}: expected {expected_count} stamps, got {len(stamps)}"
    )
    assert sum(per_date_counts.values()) == expected_count, (
        f"{label}: per_date_counts sums to {sum(per_date_counts.values())}, "
        f"expected {expected_count}"
    )
    print(f"OK  {label}: {len(stamps)} stamps")
    return stamps, per_date_counts


def main():
    check("2026-07", 60, 744, "July 2026 hourly")
    check("2026-07", 15, 2976, "July 2026 15-min")

    march_hourly, march_hourly_dates = check("2026-03", 60, 743, "March 2026 hourly")
    march_15, march_15_dates = check("2026-03", 15, 2972, "March 2026 15-min")

    assert "03/08/2026 02:00" not in march_hourly, "March 8 02:00 should be ABSENT (hourly)"
    assert "03/08/2026 02:00" not in march_15, "March 8 02:00 should be ABSENT (15-min)"
    assert march_hourly_dates["03/08/2026"] == 23, (
        f"March 8 hourly count should be 23, got {march_hourly_dates['03/08/2026']}"
    )
    assert march_15_dates["03/08/2026"] == 92, (
        f"March 8 15-min count should be 92, got {march_15_dates['03/08/2026']}"
    )
    print("OK  March 8 2026: 02:00 absent, day totals 23 hourly / 92 fifteen-min")

    nov_hourly, nov_hourly_dates = check("2026-11", 60, 721, "November 2026 hourly")
    nov_15, nov_15_dates = check("2026-11", 15, 2884, "November 2026 15-min")

    for label in ("01:00", "01:15", "01:30", "01:45"):
        stamp = f"11/01/2026 {label}"
        count = nov_15.count(stamp)
        assert count == 2, f"11/01/2026 {label} should appear exactly twice, got {count}"
    assert nov_hourly.count("11/01/2026 01:00") == 2
    assert nov_hourly_dates["11/01/2026"] == 25, (
        f"Nov 1 hourly count should be 25, got {nov_hourly_dates['11/01/2026']}"
    )
    assert nov_15_dates["11/01/2026"] == 100, (
        f"Nov 1 15-min count should be 100, got {nov_15_dates['11/01/2026']}"
    )
    print("OK  Nov 1 2026: 01:00/01:15/01:30/01:45 each appear twice, day totals 25 hourly / 100 fifteen-min")

    print()
    print("All asserts passed.")
    print()
    print("Sample around the March 8 spring-forward gap (hourly):")
    window = [s for s in march_hourly if s.startswith("03/08/2026") or s.startswith("03/07/2026 2")]
    for s in window:
        print(f"  {s}")

    print()
    print("Sample around the Nov 1 fall-back repeat (15-min):")
    window = [s for s in nov_15 if s.startswith("11/01/2026 00") or s.startswith("11/01/2026 01") or s.startswith("11/01/2026 02")]
    for s in window:
        print(f"  {s}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
