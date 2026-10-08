# Freeze research definitions, split the calendar and calibrate neutral bands

Status: done

## What to build

Before any outcome is inspected, write down every candidate feature, transformation, state rule and reference definition and freeze them. Set shared calendar boundaries for training (about 60%), development (20%) and holdout (20%). Purge observations whose outcome windows cross a boundary. Calibrate each dimension's neutral band from training inputs only.

Source: [Company State Monitor v5](../../../sectors_company_state_monitor_v5.md), "Descriptive state engine", "Chronological protocol" and "Research artifacts". [ADR 0002](../../../docs/adr/0002-protect-holdout-and-limit-historical-claims.md).

## Acceptance criteria

- [x] `research/candidate_signals.yaml` defines the three dimension measures, accounting and availability conventions, band rules, state mappings and the three reference definitions, with freeze status.
- [x] `research/signal_log.csv` records candidate decisions and data-quality findings, including rejected ideas.
- [ ] (Deferred by ADR 0003) Boundaries, date ranges, completed-case counts, distinct quarters and purged windows are recorded.
- [x] Each band's half-width is the 25th percentile of absolute training values, estimated without forward returns. A zero, nonfinite or unusable band blocks that dimension; there is no invented fallback.
- [ ] (Deferred by ADR 0003) No holdout outcome is read by any code path in this ticket, and a test enforces that.
- [x] The freeze is recorded with a date and a content hash, because the project is not yet a git repository.
- [x] Tests, typechecking and code review are complete.

## Blocked by

None under ADR 0003. Ticket 04 for the later historical recalibration.

## Comments

Scope changed 2026-10-06 by the operator (option 2, [ADR 0003](../../../docs/adr/0003-calibrate-bands-on-the-current-snapshot.md)): bands are calibrated on the current LQ45 snapshot, not a chronological training period, until history is funded. The calendar split and holdout criteria are deferred to that later recalibration; the definitions, freeze record and inputs-only calibration still apply now. No longer blocked by ticket 04.

Closed 2026-10-06 under ADR 0003. Definitions are at version 6 in `research/candidate_signals.yaml`, with 19 dated decisions in `research/signal_log.csv`. `scripts/freeze_bands.py` froze fundamentals ±16.62% (23 values), price ±2.96% (21) and flow ±0.27% (23) against the definitions' sha256. The build refuses a freeze made under other definitions, treats unusable stored bands as missing, and publishes no state without a freeze. The calendar split and holdout criteria wait for funded history (ticket 04).
