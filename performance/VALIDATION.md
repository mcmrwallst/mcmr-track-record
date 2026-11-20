# Validation report

Generated from commit `231c4fa` with methodology v1.2. All checks passed; the build stops instead of publishing if any check fails.

Checks run: required fields, event order, file and line references, R and % arithmetic, every fill inside that day's range, no stop traded before its exit, a month-end mark for every open position, marks equal to the daily closes.

## Warnings (do not stop the build)

- E0005: date-only fill (2026-08-05); checked against that day's range
- E0007: date-only fill (2026-09-10); checked against that day's range
- E0010: date-only fill (2026-09-03); checked against that day's range
- E0013: date-only fill (2026-09-21); checked against that day's range
- E0015: result_pct 9.30 vs R x risk 9.24 (explained in note)
