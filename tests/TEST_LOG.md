# Test Log

## 1. What was run, and when

Date: August 13, 2026.
App version: 0.1.0.
Python: 3.12.10.

Commands, in order, all from the repo root:

```
python validate.py
python tools/prove_expected_stamps.py
python tools/prove_checks_v1_v2.py
python tools/prove_checks_v3.py
python tools/generate_fixtures.py
python tools/run_fixtures.py
```

Every result below is copied from the actual output of those six commands
tonight, not from an earlier run and not from what the code was supposed
to do.

---

## 2. The fixture table

Ten fixtures, `tests/fixtures/`, each a single change from the clean
July sample (or, for F8/F8b, built the same way with November's
timezone-aware timestamps in place of July's). "Rule it was built to
trip" is the name it was given before tonight's run. "Rules that
actually fired" is the unfiltered CHECK output of tonight's run,
including R17. "Result" is PASS/FAIL after excluding R17 from the
comparison (see Section 3) and after correcting six of the ten
expectations (see Section 3) -- it is not a re-statement of the "built
to trip" column.

| Fixture | What it changes | Rule it was built to trip | Rules that actually fired | Result |
|---|---|---|---|---|
| F0 | Clean July, unmodified | nothing | nothing | PASS |
| F8 | November 2026, tz-aware calendar walk, 25-hour Nov 1, `01:00` doubled | nothing | nothing | PASS |
| F5 | Interval file: 07/14/2026 deleted (96 rows), 07/21/2026 duplicated (96 rows appended before the Total row) | R12, R15 | R12, R14, R15, R17 | PASS |
| F4 | Hourly file: Sub D's column blanked for 07/10/2026 (24 cells) | R12, R14, R17 | R12, R14 | PASS |
| F3 | Interval file: one row inserted at 08/01/2026 00:00 | R7, R10 | R7, R9, R10 | PASS |
| F1 | Interval file: Sub C's header renamed to "Sub C RENAMED" | R3 | R3, R4 | PASS |
| F7 | Interval file: Sub G's column blanked for the whole month (2,976 cells) | R16 | R12, R14, R16, R17 | PASS |
| F6 | Hourly file: last 4 rows of 07/10/2026 deleted (20 of 24 remain) | R14 | R12, R14, R17 | PASS |
| F2 | Interval file: one unmapped column inserted before Total/System | R4 | R4 | PASS |
| F8b | November data, one occurrence of the doubled `01:00` hourly stamp removed (720 rows instead of 721) | R14 | R12, R14, R17 | PASS |

All ten passed.

---

## 3. Co-firing

Six of the ten fixtures fired more than the single rule they were named
for. All six are by design -- traced to the rule document's own text,
not discovered by running the fixture and accepting whatever came out.

- **F1** also fires R4. The document's own explanation for why R3 and R4
  both exist: a renamed header is at once "the expected name is gone"
  (R3) and "a name nobody expected is now present" (R4).
- **F3** also fires R9. R9 is not a separate trigger. Its text says
  excluded rows are "excluded from the totals AND reported" -- it is
  R7's reporting half, not a second check.
- **F5** also fires R14. R14's text requires every day's count to be
  right, with no exception for a month whose total still adds up. A
  day with zero rows and a day with double rows are both wrong by that
  rule, regardless of the monthly total.
- **F6, F7, F8b** also fire R12. R12's missing-direction is checked per
  substation, never pooled (R13). A deleted hour, a deleted month, and
  a deleted duplicate-stamp occurrence are each a stamp that should
  exist and does not -- exactly what R12 exists to catch, independent
  of whatever R14 or R16 also report about the same event.

**R17 co-fires with R14 on every fixture where R14 fires, and that is
not a rule reaching too far: R17 draws R14's own per-date,
per-substation result as a grid, so wherever R14 has a finding, the
grid shows it.** R17 was excluded from the pass/fail comparison in
Section 2 for the same reason -- see the design note at the end of this
log.

No co-firing found tonight was a bug. Every extra rule traces to its own
rule text.

---

## 4. The clean cases

F0 and F8 fired nothing.

That matters on its own, separately from the six fixtures above. From
the build brief: "a test that runs all seven and asserts each trips the
rule it should -- and, just as important, that a clean file trips
nothing. A check that fires on everything is as useless as one that
fires on nothing." F0 proves the checker does not cry wolf on ordinary
data.

F8 proves something F0 cannot: July 2026 has no DST transition, so a
clean July run cannot tell a correct timezone-aware calendar walk from
a naive one that assumes every day has 24 hours. November does. F8's
25-hour day and doubled `01:00` are real, and the checker read them as
clean. F8 is the only end-to-end proof in this log that the DST logic
is right -- not a synthetic assertion about a stamp list, an actual
workbook the validator opened and passed.

---

## 5. Coverage, stated honestly

**Three of the four test artifacts never open a workbook.**
`tools/prove_expected_stamps.py`, `tools/prove_checks_v1_v2.py`, and
`tools/prove_checks_v3.py` are synthetic: they call check functions
directly against hand-built Python dicts and lists, not against a real
`.xlsx` file. They are useful for exercising rule logic and edge cases
a real fixture would be slow or awkward to build (a triple-duplicate
stamp, a bogus off-grid reading), but they do not prove the loader, the
file-matching, or the crosswalk wiring work. Only `validate.py` against
the sample data, and the fixture runner against the ten real files in
Section 2, exercise the whole path from an actual `.xlsx` on disk to
the rule table. A reader should not come away thinking there are four
independent end-to-end proofs. There is one end-to-end path, and it was
run eleven times tonight (once directly, ten times through fixtures).

**Determinism is not verified.** The build target is a byte-identical
output workbook across runs, apart from the run timestamp. A two-run
byte comparison was attempted on August 13 and abandoned after repeated
failures caused by a path-format mismatch between Git Bash
(`/c/Users/...`) and the Windows Python interpreter (`C:\Users\...`),
not by a difference in the files themselves. The application is
designed for determinism -- fixed random seeds in the sample generator,
explicit (not auto-stamped) workbook creator/title/company properties,
a single run-timestamp value threaded through the whole output workbook
instead of separate clock reads -- but that design has not been
verified by an actual passing test. This is unproven, not disproven.

**Defect 1 (the column swap) has no fixture.** Every other defect this
project addresses is checked for. This one was not given a check --
the application removed the mechanism that caused it. The original
defect was a hand-typed substation name and meter identifier, retyped
every month, sixty-four cells at a time; a transposition there changes
no total, so nothing in the old process could catch it. `crosswalk.csv`
makes that mapping a stored, version-controlled file instead of
something retyped monthly, so the sixty-four hand-keyed cells this
defect required are now zero. That is a stronger claim than "this rule
detects the defect," which is exactly why it has to be stated here
instead of left as a blank row in the fixture table. One caveat worth
naming precisely: `tools/prove_checks_v1_v2.py` does independently show
that R1's reorder logic would catch a plain two-column swap if one ever
happened despite the crosswalk (a synthetic case, not a fixture) -- that
is a second line of defense, not the reason a fixture was skipped.

---

## 6. Defects found in the validator itself, tonight

Three.

**`overall_status()` returned PASS when no rule was CHECK, even with a
NOT RUN rule present.** R20 requires that a blank G&T figure read NOT
RUN and never PASS at the row level; the roll-up function had no
matching rule for NOT RUN at the summary level, so an all-PASS-or-NOT
RUN run rolled up to a false PASS. Found by writing the R20 requirement
down as a plain sentence while building the output workbook, not by a
test catching it. No fixture in this log would have caught it either --
every fixture here trips a CHECK, and the bug only showed on a run
where nothing did. Fixed in `validator/checks.py`.

**`solar_shared_review` flagged 11,904 interval rows.** That is every
reading from the four Solar/Shared substations for the month --
4 x 31 x 96. A flag that fires on 100% of a category identifies
nothing; it is a census wearing a flag's name. Found by noticing the
number was suspiciously round relative to the roster, not by a test.
Changed to report the four substations by name once each, with a
one-line reason to read their variance carefully, instead of a per-
reading count.

**`openpyxl`'s `ws.cell(row, column, value=None)` is a silent no-op.**
`value=None` is indistinguishable from omitting the argument, so it
does not clear a cell -- it does nothing. F4 and F7's fixtures both
depend on blanking cells, and both were generated byte-identical to the
clean sample; the generator printed "blanked ... (24 cells)" and
"blanked ... entirely (2,976 cells)" and believed it. Found by running
the fixtures and seeing F4 and F7 fire nothing at all, when nothing
firing was only supposed to happen for F0 and F8. Fixed by assigning
`.value = None` directly instead of passing it as a keyword argument,
in both places. Verified tonight by reading the saved cells back
directly: F4 has exactly 24 blank cells, all in Sub D's column, all
dated 07/10; F7 has exactly 2,976 blank cells, all in Sub G's column,
covering every data row.

One correction to how this was described earlier tonight: it was said
that "a second, separate bug then hit the same two fixtures" after the
`value=None` fix. That is not accurate. What actually followed was that
F7's *expected rule set* was wrong -- corrected in Section 3, from R16
alone to R16 plus R12 and R14 -- which is a specification error in the
fixture brief, not a second code defect in the generator or the
checker. Verified directly against both saved files tonight (read back
above): once the `value=None` fix was applied, F4 and F7's underlying
data was correct on the first regeneration. Only the expectation this
log compares it against needed a second look, not the code that
produced it.

---

## 7. Environment assumptions

Three found in two days. All the same shape: a tool that silently did
nothing instead of failing loudly.

- **`tzdata` / `zoneinfo` on a clean Windows install.** `zoneinfo` has
  no system timezone database to fall back to on Windows, unlike most
  Linux and macOS installs. Without the `tzdata` package, `ZoneInfo`
  raises `ZoneInfoNotFoundError` -- but nothing in this codebase
  imports `tzdata` by name, so it reads as unused and is exactly the
  kind of dependency someone deletes during cleanup. Pinned explicitly
  in `requirements.txt` with a comment saying why.
- **Git Bash `/c/Users/...` versus Windows Python `C:\Users\...`.** A
  file copied by a Git Bash command is invisible to a Windows Python
  process given the same nominal path, because the two tools resolve
  paths in different namespaces. This is what stopped the determinism
  check in Section 5 -- not a bug in the app.
- **`openpyxl`'s `ws.cell(..., value=None)` no-op.** Covered in Section
  6. Included here too because it is the same shape as the other two:
  a call that looks like it did something, produced no error, and did
  nothing.

---

### Design note: R17 is a rendering, not a check

R12's and R14's rule text each state a comparison and what happens when
it fails. R17's text only says the grid must be shown: "The
reconciliation tab shows a grid... In a clean month, every cell reads
24." No failure clause. Mechanically, R17's "off cell" count in
`checks_v3.py` is computed by re-checking the same
`grid[date][substation] != expected` condition R14 already evaluated --
it has no comparison logic of its own. Counting it as an independently
fail-able rule double-counts every R14 finding it displays, which is
why Section 2's Result column and the fixture runner both exclude it
from the fired-rule comparison while still recording when it renders.
The Reconciliation tab should carry the same distinction: rules that
can independently fail, and sections that always render regardless of
what they show.
