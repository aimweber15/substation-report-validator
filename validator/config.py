"""
Config and crosswalk loading.

Everything the validator needs to know about column names, file layout,
the report month, and tolerances lives in config.json and crosswalk.csv --
never in code (constraint 5). This module only loads and structurally
sanity-checks those two files; it does not run any of the named R1-R20
rules against workbook data.
"""

import csv
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG_PATH = REPO_ROOT / "config.json"

REQUIRED_CONFIG_KEYS = [
    "report_month",
    "source_folder",
    "interval_file_pattern",
    "hourly_file_pattern",
    "layout",
    "columns",
    "crosswalk_file",
    "units",
    "expected_interval_minutes",
    "hourly_interval_minutes",
    "timezone",
    "reconciliation",
]

REQUIRED_LAYOUT_KEYS = [
    "header_row",
    "unit_description_row",
    "first_data_row",
    "last_row_is_total",
    "leading_timestamp_columns",
    "timestamp_column_index",
    "timestamp_column_meaning",
    "interval_timestamps_are_text",
    "interval_timestamp_format",
    "hourly_timestamps_are_datetime",
]

REQUIRED_TIMEZONE_KEYS = [
    "mode",
    "zone",
    "expected_rows_per_day",
]

REQUIRED_CROSSWALK_COLUMNS = {
    "generic_id",
    "interval_position",
    "hourly_position",
    "location_type",
    "expected_interval_header",
    "expected_hourly_header",
}


class ConfigError(Exception):
    """Raised when config.json or crosswalk.csv can't be trusted as-is.

    This is structural sanity-checking (missing keys, unreadable files),
    not one of the R1-R20 business rules -- those are validated later,
    against workbook data, not against the config files themselves.
    """


def load_config(path=None):
    """Load and structurally validate config.json. Fails loudly and names
    exactly what's missing rather than defaulting silently."""
    path = Path(path) if path else DEFAULT_CONFIG_PATH
    if not path.exists():
        raise ConfigError(f"Config file not found: {path}")

    with open(path, "r", encoding="utf-8") as f:
        try:
            config = json.load(f)
        except json.JSONDecodeError as e:
            raise ConfigError(f"Config file is not valid JSON: {path} ({e})") from e

    missing = [k for k in REQUIRED_CONFIG_KEYS if k not in config]
    if missing:
        raise ConfigError(f"config.json is missing required key(s): {', '.join(missing)}")

    missing_layout = [k for k in REQUIRED_LAYOUT_KEYS if k not in config["layout"]]
    if missing_layout:
        raise ConfigError(f"config.json 'layout' is missing key(s): {', '.join(missing_layout)}")

    missing_timezone = [k for k in REQUIRED_TIMEZONE_KEYS if k not in config["timezone"]]
    if missing_timezone:
        raise ConfigError(f"config.json 'timezone' is missing key(s): {', '.join(missing_timezone)}")

    config["_path"] = str(path)
    return config


def unconfirmed_assumptions(config):
    """Return {config_path: value} for every key config.json flags as
    still-unconfirmed via the top-level 'unconfirmed' list. Printed loudly
    on every run per constraint 5 -- an assumption the software announces
    is a finding, one it hides is a defect."""
    result = {}
    for dotted_key in config.get("unconfirmed", []):
        node = config
        for part in dotted_key.split("."):
            node = node[part]
        result[dotted_key] = node
    return result


def load_crosswalk(config, repo_root=None):
    """Load crosswalk.csv. Returns active rows only, in file order."""
    repo_root = Path(repo_root) if repo_root else REPO_ROOT
    crosswalk_path = repo_root / config["crosswalk_file"]
    if not crosswalk_path.exists():
        raise ConfigError(f"Crosswalk file not found: {crosswalk_path}")

    rows = []
    with open(crosswalk_path, "r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        missing_cols = REQUIRED_CROSSWALK_COLUMNS - set(reader.fieldnames or [])
        if missing_cols:
            raise ConfigError(
                f"crosswalk.csv is missing column(s): {', '.join(sorted(missing_cols))}"
            )
        for line_num, row in enumerate(reader, start=2):
            if (row.get("is_active") or "TRUE").strip().upper() == "FALSE":
                continue
            try:
                interval_position = int(row["interval_position"])
                hourly_position = int(row["hourly_position"])
            except ValueError as e:
                raise ConfigError(
                    f"crosswalk.csv row {line_num}: interval_position/hourly_position "
                    f"must be integers ({e})"
                ) from e
            rows.append(
                {
                    "generic_id": row["generic_id"].strip(),
                    "interval_position": interval_position,
                    "hourly_position": hourly_position,
                    "location_type": row["location_type"].strip(),
                    "expected_interval_header": (row.get("expected_interval_header") or "").strip(),
                    "expected_hourly_header": (row.get("expected_hourly_header") or "").strip(),
                }
            )
    return rows
