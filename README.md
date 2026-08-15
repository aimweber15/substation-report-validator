# Substation Report Validator

```
python -m venv .venv
.venv\Scripts\activate      # or: source .venv/bin/activate
pip install -r requirements.txt
python validate.py
```

Expect a rule table ending in `Overall status (R0): NOT VERIFIED - the
outside tie-out has not been run` against the clean July sample data
included in this repo -- not `PASS`, and that's deliberate.

Every internal check (R1-R17) passes. What doesn't run is R19, the one
check that isn't internal: comparing the report's own total against a
figure from the G&T cooperative, typed in by a person each month
(`reconciliation.gt_figure` in `config.json`). Nobody has typed one in
here, so R19 can't run -- and R20 exists specifically so a missing
external check reads as "not verified," never as a clean pass. A
validator that quietly showed PASS when the one check requiring a human
never happened would be worse than not having R20 at all. This is R20
working, not an error -- it's a governance feature, which is why it's on
this front page instead of buried in the rule table.

## What you get

Four tabs in the output workbook (`outputs/substation_report_<month>.xlsx`):

- **Reconciliation** -- open this one first. Status row in words, then
  every rule R0-R20 as Rule / Result / Message.
- **Final Report** -- the co-op's existing six-column report, reproduced
  exactly (including the "Differance" spelling), with E and F written as
  live Excel formulas, not values.
- **Completeness** -- the grid: dates down, substations across, reading
  counts in the cells. A missing day is blank, not zero.
- **Data Quality** -- the eleven exception flags, counted per source file.

## If you're not going to run this

Two finished workbooks are committed under `examples/`:

- `clean_july_EXAMPLE.xlsx` -- a clean run against `config.demo.json`
  (same as `config.example.json`, but with a fabricated G&T figure filled
  in, so R19 actually runs). Status reads PASS.
- `fixture5_missing_and_duplicated_day_EXAMPLE.xlsx` -- a caught error:
  one day's rows were deleted and a different day's rows were duplicated,
  so the month's row count still adds up but the data underneath it is
  wrong. Status reads CHECK, naming both dates.

## What it does

Runs completeness and consistency checks on a rural electric
cooperative's monthly substation meter report, comparing a 15-minute
interval export against an hourly export for the same month.

## Requirements

Python 3.9+ (developed and tested on 3.12). `tzdata` is pinned in
`requirements.txt` deliberately: `zoneinfo` needs it to resolve time
zones on platforms with no system tz database (Windows among them), and
nothing in this codebase imports it by name -- do not remove it as
unused.

## Sample data

Everything in `data/` is generated from a spec by
`tools/generate_sample_data.py`, with fixed random seeds, so reruns are
reproducible. This repository has never contained real utility data.
`crosswalk.csv` is positions-only, keyed to generic identifiers -- no
real substation names or meter numbers.

## Rules

Validation rules R0-R20 are specified in the accompanying written
document.

## Proof scripts

`tools/prove_*.py` exercise individual rule functions against synthetic,
hand-built scenarios (a swapped header, a missing day, a DST fall-back,
etc.) -- they don't touch real workbooks. `validate.py` against the
sample data is the only end-to-end path.
