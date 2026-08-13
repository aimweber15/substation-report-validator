"""
V1 -- column identification (R1-R5).

Addresses Defect 1: values keyed into the wrong columns.

R1 says match by header name, never by position -- and the crosswalk maps
generic_id to a column by position, because the two files name the same
location differently and there is no shared name to match on (Build Brief
Addendum, item 2). The accepted mitigation is that position gets the
column, and the header text at that position is verified against
crosswalk.csv's expected_interval_header / expected_hourly_header every
run. Where that expected text hasn't been filled in yet, this code does
not pretend the name was verified -- it reports NOT RUN, by column, so the
gap stays visible instead of quietly passing.
"""

from validator.checks import CheckResult


def _crosswalk_by_position(crosswalk_rows, position_field):
    return {row[position_field]: row for row in crosswalk_rows}


def check_r2(config):
    """R2 -- the expected header list comes from config, not from code."""
    crosswalk_file = config.get("crosswalk_file")
    if not crosswalk_file:
        return [CheckResult(
            "R2", "CHECK",
            "config.json has no crosswalk_file set -- there is no config-driven "
            "source for the expected header list."
        )]
    return [CheckResult(
        "R2", "PASS",
        f"Expected header list loaded from crosswalk_file={crosswalk_file!r} "
        f"in config.json; no header names are hardcoded in the validator."
    )]


def check_v1_for_file(report, crosswalk_rows, position_field, header_field):
    """R1, R3, R4, R5 for one workbook.

    A header mismatch at a known position is not one thing -- it is two,
    and they route to different rules:

      Reorder/swap -- the expected text is missing from its position but
      still exists somewhere else in the file (another location's name).
      Name-based matching survives this without help; position + text
      verification is what catches it. Routes to R1 -- position was used
      to locate the column, and the name proves the mapping no longer
      holds (Defect 1's shape).

      Rename -- the expected text is missing from its position and
      appears nowhere else in the file. Name-based matching cannot
      survive this by construction. Routes to R3 (the name is gone --
      STOP) and, since whatever text replaced it matches no expected
      name either, also to R4 (a foreign header is now present).
    """
    path_name = report["path"].name
    by_position = _crosswalk_by_position(crosswalk_rows, position_field)
    rows = []

    expected_by_text = {}
    for row in crosswalk_rows:
        text = (row[header_field] or "").strip()
        if text:
            expected_by_text[text] = row["generic_id"]

    actual_by_position = {}
    for m in report["column_matches"]:
        cw_row = by_position.get(m["position"])
        if cw_row is None:
            rows.append(CheckResult(
                "R4", "CHECK",
                f"{path_name}: column {m['letter']} (header {m['header']!r}, "
                f"position {m['position']}) has no crosswalk entry -- present "
                f"in the file but not on the expected list."
            ))
            continue
        actual_by_position[m["position"]] = (cw_row["generic_id"], (m["header"] or "").strip())

    actual_texts_present = {text for _, text in actual_by_position.values() if text}

    verified = []
    reordered = []
    renamed_missing = []
    unverifiable = []
    foreign_present = []

    for position, (generic_id, actual_text) in actual_by_position.items():
        expected_text = (by_position[position][header_field] or "").strip()
        if not expected_text:
            unverifiable.append(generic_id)
        elif actual_text == expected_text:
            verified.append(generic_id)
        elif expected_text in actual_texts_present:
            reordered.append((generic_id, expected_text, actual_text))
        else:
            renamed_missing.append((generic_id, expected_text))
            if actual_text not in expected_by_text:
                foreign_present.append((position, actual_text))

    for position, actual_text in foreign_present:
        rows.append(CheckResult(
            "R4", "CHECK",
            f"{path_name}: header {actual_text!r} at position {position} matches "
            f"no expected header -- present in the file but not on the expected list."
        ))

    for generic_id, expected_text, actual_text in reordered:
        rows.append(CheckResult(
            "R1", "CHECK",
            f"{path_name}: {generic_id}'s expected header {expected_text!r} is not "
            f"at its crosswalk position (found {actual_text!r} instead), but "
            f"{expected_text!r} does appear elsewhere in the file -- possible "
            f"column reorder."
        ))
    if verified and not reordered:
        rows.append(CheckResult(
            "R1", "PASS",
            f"{path_name}: {len(verified)} column header(s) verified by exact "
            f"name match against crosswalk.csv: {', '.join(verified)}."
        ))
    if unverifiable:
        rows.append(CheckResult(
            "R1", "NOT RUN",
            f"{path_name}: {len(unverifiable)} column(s) matched by position only -- "
            f"crosswalk.csv has no expected header text yet for {', '.join(unverifiable)}; "
            f"name not verified this run."
        ))

    missing_positions = report["missing_crosswalk_positions"]
    for position in missing_positions:
        cw_row = by_position.get(position)
        generic_id = cw_row["generic_id"] if cw_row else f"position {position}"
        rows.append(CheckResult(
            "R3", "CHECK",
            f"{path_name}: expected column for {generic_id} (crosswalk "
            f"position {position}) not found in the file."
        ))
    for generic_id, expected_text in renamed_missing:
        rows.append(CheckResult(
            "R3", "CHECK",
            f"{path_name}: expected header {expected_text!r} for {generic_id} "
            f"not found anywhere in the file."
        ))
    if not missing_positions and not renamed_missing:
        rows.append(CheckResult(
            "R3", "PASS",
            f"{path_name}: every expected header was found in the file."
        ))

    rows.append(CheckResult(
        "R5", "PASS",
        f"{path_name}: {len(report['headers'])} header(s) recorded from row "
        f"{report['header_row_idx']}: {report['headers']}."
    ))

    return rows
