# Substation Report Validator

```
python -m venv .venv
.venv\Scripts\activate      # or: source .venv/bin/activate
pip install -r requirements.txt
python validate.py
```

Expect a rule table ending in `Overall status (R0): PASS` against the
clean July sample data included in this repo.

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
