"""
V4 -- external tie-out (R18-R20).

Addresses the accident that caught the Aug 11 error: an external number
(the G&T cooperative's own figure) sitting next to the report and not
agreeing with it. Every other check in R1-R17 is internal -- the report
grading its own homework. V4 is the only one that consults a number from
outside, which makes it the only one that isn't circular, and the only
one that requires a human every month -- so it's also the only one that
can quietly stop happening. That is R20's whole reason to exist: a blank
G&T cell must read NOT RUN, never PASS.

The app REPORTS the variance. Per config.reconciliation's Aug 12 note, it
does not decide pass/fail against tolerance_pct -- that judgment, and the
+/-2% tie-out itself, belong to the G&T cooperative's own report, a
separate step downstream of this app.

ASSUMPTION -- stated here because it is not fully spelled out in config,
config.example.json, or the Output Specification doc: the "report total"
R19 compares against gt_figure is meter_kwh, the hourly-file grand total
named by reconciliation.meter_kwh_source -- i.e. the Final Report tab's
Total row, column C. That field is the only config-named quantity
co-located with gt_figure/tolerance_pct in the same "reconciliation"
block, and it is the meter-READ figure (as opposed to column D's
revenue figure), the natural counterpart to a G&T meter-based bill. This
is a judgment call, not a settled fact -- it is repeated in R19's own
message on the Reconciliation tab so it stays inspectable rather than
silently assumed, and it does not affect this run: gt_figure is null in
the sample config, so R19 reads NOT RUN regardless of which total it
would have used.
"""

from validator.checks import CheckResult


def check_v4(config, meter_kwh_total):
    """R18-R20. meter_kwh_total -- the Final Report tab's grand total for
    column C (Substation Meter KWH, summed from the hourly file), which
    R19 compares against config.reconciliation.gt_figure. See the
    module-level ASSUMPTION note above."""
    reconciliation = config["reconciliation"]
    gt_figure = reconciliation.get("gt_figure")
    tolerance_pct = reconciliation.get("tolerance_pct")

    if gt_figure is None:
        return [
            CheckResult(
                "R18", "NOT RUN",
                "G&T cooperative figure cell is blank -- typed by a person "
                "each month, not computed. No figure entered for this run."
            ),
            CheckResult(
                "R19", "NOT RUN",
                "Variance not computed -- the G&T figure cell (R18) is blank."
            ),
            CheckResult(
                "R20", "PASS",
                "G&T cell is blank, so R19 correctly reads NOT RUN, not PASS."
            ),
        ]

    variance = meter_kwh_total - gt_figure
    pct_text = f"{(variance / gt_figure * 100):+.3f}%" if gt_figure else "n/a (gt_figure is 0)"
    tolerance_text = f"+/-{tolerance_pct}%" if tolerance_pct is not None else "not set"

    return [
        CheckResult(
            "R18", "PASS",
            f"G&T cooperative figure entered: {gt_figure:,.1f} kWh."
        ),
        CheckResult(
            "R19", "PASS",
            f"Variance reported (assumed basis: meter_kwh, the hourly-file "
            f"grand total -- see checks_v4.py module docstring): "
            f"{meter_kwh_total:,.1f} kWh vs G&T figure {gt_figure:,.1f} kWh "
            f"= {variance:+,.1f} kWh ({pct_text}). Tolerance on file: "
            f"{tolerance_text} -- this app does not apply it; the tie-out "
            f"against tolerance is a separate step in the G&T cooperative's "
            f"own report."
        ),
        CheckResult(
            "R20", "PASS",
            "G&T cell is populated, so R19 ran and reported a variance."
        ),
    ]
