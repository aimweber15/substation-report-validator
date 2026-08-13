"""
Shared shape for every R1-R20 rule check.

Every check function in checks_v1.py, checks_v2.py, and (later) checks_v3.py
/ checks_v4.py returns a list of CheckResult rows -- rule, result, message,
nothing else -- so the reconciliation tab can be one table built by
appending twenty rules' output, rather than twenty hand-placed ranges.

result is one of PASS, CHECK, or NOT RUN:
  PASS     -- the check ran and found nothing wrong.
  CHECK    -- the check ran and found something a person must look at.
              R0: if any row anywhere is CHECK, the report is not issued.
  NOT RUN  -- the check could not run at all, for lack of required input
              (a blank G&T figure for R19, a blank expected-header field
              in crosswalk.csv for R1). Not a failure of the data; a gap
              in the inputs the check needs. Never rendered as PASS.
"""

from collections import namedtuple

CheckResult = namedtuple("CheckResult", ["rule", "result", "message"])

VALID_RESULTS = {"PASS", "CHECK", "NOT RUN"}


def overall_status(check_rows):
    """R0 -- the governing rule. CHECK if any row is CHECK, else PASS."""
    for row in check_rows:
        if row.result not in VALID_RESULTS:
            raise ValueError(f"{row.rule}: invalid result {row.result!r}")
    if any(row.result == "CHECK" for row in check_rows):
        return "CHECK"
    return "PASS"


def print_check_rows(check_rows):
    rule_width = max((len(r.rule) for r in check_rows), default=4)
    print(f"{'RULE':<{rule_width}}  {'RESULT':<7}  MESSAGE")
    print("-" * 70)
    for row in check_rows:
        print(f"{row.rule:<{rule_width}}  {row.result:<7}  {row.message}")
    print("-" * 70)
    print(f"Overall status (R0): {overall_status(check_rows)}")
