"""
Number-crunching for the Final Report tab (columns A-D and the two
control totals). Pure computation, no openpyxl -- the workbook module
writes these numbers (and the E/F formulas that reference them) to cells.

Column source, settled in Output Specification - Final Report Tab.md:
  C -- Substation Meter KWH -- sum of the HOURLY file, per meter
  D -- MDM Revenue Sub KWH  -- sum of the 15-MINUTE file, per substation
Getting these backwards is silent and total-preserving, which is exactly
how Defect 1 hid: swap C and D calculation and every row still looks
like a plausible number, just the wrong one.

Sums are in-window only (config.report_month's [start, next-month-start)
range), consistent with V2's own filter -- a stray next-month row should
not inflate a monthly total any more than it should pass R7.
"""

from validator.checks_v2 import compute_window
from validator.checks_v3 import _is_blank


def _in_window_sum(readings, window_start, window_end):
    total = 0.0
    for ts, value in readings:
        if _is_blank(value):
            continue
        if not (window_start <= ts < window_end):
            continue
        total += value
    return total


def build_final_report_data(interval_report, hourly_report, config, crosswalk_rows):
    """Returns the numbers the Final Report tab and R19 both need.

    rows -- one dict per roster substation, in crosswalk.csv order:
      generic_id, meter_label (expected_hourly_header), c_hourly_kwh,
      d_interval_kwh.
    total_c / total_d -- grand totals of the 16 rows' C / D.
    control_hourly_total_system / control_interval_total_system --
      each file's OWN Total/System column, summed in-window. These are
      the control rows: an independent total the source system computed
      itself, to set next to our sum-of-16-columns total.
    """
    window_start, window_end = compute_window(config["report_month"])

    rows = []
    for cw_row in crosswalk_rows:
        generic_id = cw_row["generic_id"]
        c_hourly = _in_window_sum(
            hourly_report["readings_by_generic_id"].get(generic_id, []),
            window_start, window_end,
        )
        d_interval = _in_window_sum(
            interval_report["readings_by_generic_id"].get(generic_id, []),
            window_start, window_end,
        )
        rows.append({
            "generic_id": generic_id,
            "meter_label": cw_row["expected_hourly_header"] or "(no expected_hourly_header in crosswalk)",
            "c_hourly_kwh": round(c_hourly, 1),
            "d_interval_kwh": round(d_interval, 1),
        })

    total_c = round(sum(r["c_hourly_kwh"] for r in rows), 1)
    total_d = round(sum(r["d_interval_kwh"] for r in rows), 1)

    control_hourly = round(
        _in_window_sum(hourly_report["total_column_values"], window_start, window_end), 1
    )
    control_interval = round(
        _in_window_sum(interval_report["total_column_values"], window_start, window_end), 1
    )

    return {
        "rows": rows,
        "total_c": total_c,
        "total_d": total_d,
        "control_hourly_total_system": control_hourly,
        "control_interval_total_system": control_interval,
    }
