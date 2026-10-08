# Evaluate the holdout once and compare the three references

Status: deferred

## What to build

After the freeze, evaluate the untouched holdout once. Match completed cases by Company State only, apply the evidence labels, and report all three reference comparisons alongside the state results. The Company view gains historical cases and outcome summaries where the evidence allows it.

Source: [Company State Monitor v5](../../../sectors_company_state_monitor_v5.md), "Historical evaluation" and "Research artifacts". [ADR 0002](../../../docs/adr/0002-protect-holdout-and-limit-historical-claims.md).

## Acceptance criteria

- [ ] The outcome is the 60-trading-day sector-relative forward return over exactly the same dates as the peer median. Only completed outcomes count.
- [ ] Fewer than 15 completed holdout cases gives Insufficient, with no percentages. At least 15 gives Weak: case count, distinct quarters, outperformance rate, median excess return and concentration. Moderate and Strong are disabled.
- [ ] All three references are reported (momentum, earnings growth and the equal-weight composite), using training-frozen third cutoffs. Unavailable comparisons say why.
- [ ] Overlapping windows, dependence and the optimism of any Wilson interval are disclosed.
- [ ] The evaluation runs once, and the run is logged. Later ideas go to the signal log, not into changes.
- [ ] `research/validation_report.md` records probes, exclusions, boundaries, comparisons, composition and limitations.
- [ ] Tests, typechecking and code review are complete.

## Blocked by

Tickets 05 and 06.

## Comments

Deferred 2026-10-06 by the operator's choice of option 2 ([ADR 0003](../../../docs/adr/0003-calibrate-bands-on-the-current-snapshot.md)): without funded history there is no holdout, so every evidence label stays Insufficient and the three reference comparisons are recorded as unavailable with that reason. Resume when history is funded.
