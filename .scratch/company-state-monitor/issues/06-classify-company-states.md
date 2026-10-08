# Classify current and historical Company States

Status: done

## What to build

Compute the three dimensions at each company-quarter's information-availability date: comparable earnings growth, 60-day sector-relative price return and foreign flow over market cap. Apply the frozen bands and the exact state mapping. The Company view then shows the current and previous dated state, or Unclassified with its reasons, plus a separate freshness flag.

Source: [Company State Monitor v5](../../../sectors_company_state_monitor_v5.md), "Domain boundaries", "Information availability and freshness", "Descriptive state engine", "Missing flow" and "Company". [ADR 0001](../../../docs/adr/0001-separate-descriptive-states-from-historical-evidence.md).

## Acceptance criteria

- [x] Classification uses only inputs dated on or before the availability date, which is either verified or explicitly estimated with the three-month proxy.
- [x] The state mapping is exhaustive and mutually exclusive. Neutral covers complete combinations that match no named state. Any missing dimension gives Unclassified, with the usable dimensions still shown.
- [x] A state changes only on a new quarterly observation, never on a later price or flow update.
- [x] Stale keeps the dated previous state. It applies once the next expected report's deadline passes, and an estimated schedule is labelled estimated.
- [x] The Company view shows the dimension labels and raw values, up to three "what changed" bullets, and supporting and contradicting metrics where available.
- [x] There is no confidence score, prediction score or buy/sell language.
- [x] Tests cover every mapping row, boundaries, missing inputs and staleness. Typechecking, code review, a rebuild and a browser check are complete.

## Blocked by

Ticket 05. Ticket 03 decides how many members have usable fundamentals.

## Comments

Scope note 2026-10-06 ([ADR 0003](../../../docs/adr/0003-calibrate-bands-on-the-current-snapshot.md)): states use snapshot-calibrated bands. Only the latest quarter can be classified, because no earlier price or flow history is cached; the previous state is shown as unavailable rather than invented. The price and flow windows ending at the estimated availability date need one extra 90-day window, fetched within the remaining allocation.

Closed 2026-10-06. An earlier price and flow window (68 credits, ledger 438 of 500) lets 60-day windows reach the estimated 2026-09-30 availability date. Windows follow the official IDX 2026 trading calendar (239 days). The unadjusted price series is accepted only when the implied share count stays constant across the window, which blocks ADRO, SCMA and PGEO. States are recorded once per company and period with their bands (`research/state_assignments.json`). A newer report that cannot be classified keeps the dated state, marked stale when overdue. Live result: PTBA Confirmed Strength, INDF Early Deterioration, 8 Neutral, 35 Unclassified with specific reasons (22 lack verified fundamentals, 17 lack five aligned sector peers, 5 have Q1-latest reports before the cached window). Verification: 114 unittest tests, mypy, byte-identical rebuilds, secret scan, browser check. Independent GPT review: an initial round produced ten findings; residuals of S1, W1, R1, A1 plus N1 and T2 were fixed over three follow-ups, the last two by changing the rule rather than patching (verification by constant share count; the exchange holiday calendar). Both lanes pass.
