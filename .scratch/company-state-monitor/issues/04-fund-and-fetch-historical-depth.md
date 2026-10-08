# Fund and fetch the historical depth classification needs

Status: waiting-for-credits

## What to build

Classification needs neutral bands calibrated on historical data, then a training, development and holdout split. This ticket costs the history options, gets an operator funding decision, fetches the chosen history within budget, and reports the real coverage. It also completes UNTR, UNVR and WIFI.

Source: [Company State Monitor v5](../../../sectors_company_state_monitor_v5.md), "Probe before bulk fetching", "Data publication gates" and "Chronological protocol".

## Decision needed first

On 2026-10-06 the ledger stood at 450 of 500 credits, with a 50-credit reserve. 92 of those credits are conservative bookings for HTTP 429 responses. Five years of foreign flow alone is about 900 credits. The options are to check real usage on the Sectors dashboard, ask the organizers for credits, spend the reserve, or narrow the history window. A narrower window changes the methodology and must be written up before it is built.

## Acceptance criteria

- [ ] A dry-run plan prices each option per endpoint (prices, foreign flow in 90-day pages, quarterly financials and quarterly dates) before any spend.
- [ ] The operator's funding choice is recorded, with the allocation and reserve it sets.
- [ ] History is fetched incrementally: only missing periods, paced to avoid the rate limit, stopping at the first 429 or any overcharge.
- [ ] Per member and endpoint, the earliest date, the latest date, gaps and missing values are reported. Short history is never padded.
- [ ] Corporate actions are checked. Splits or other price discontinuities in the history are detected and listed. The price series is labelled price return or total return according to the evidence.
- [ ] Quarterly report dates come from the quarterly-dates helper. Availability dates are marked estimated when no disclosure date exists.
- [ ] Tests cover pagination, incremental fetching and coverage reporting. Typechecking, code review and a live run are complete.

## Blocked by

An operator funding decision. Ticket 02.

## Comments

2026-10-06 progress, before the funding decision:

- Credits reconciled with the operator's Sectors dashboard (150 remaining of 500, so 350 used). The 350 equals the ledger's successful requests exactly. HTTP 429 and network-failed requests were not billed. `scripts/reconcile_credits.py` appended a -100 adjustment and 429s now cost 0. Reconciliation only accepts a measurement newer than every ledger entry.
- UNTR, UNVR and WIFI were completed for 19 credits and verified (ticket 03 data). All 45 members are fully captured.
- A 1-credit test confirmed daily prices are capped at 90 days per request, like foreign flow. Each extra year of history costs about 4 credits per endpoint per ticker (prices, flow, and financials at 1 credit per quarter), about 12 per ticker-year, about 540 for one year across the roster.
- Ledger 370 of 500 after the test: 80 spendable plus the 50 reserve. Multi-year calibration and a chronological holdout are not affordable without more credits.

Decision 2026-10-06: the operator will add credits later by rotating in a teammate's API key. Meanwhile option 2 ([ADR 0003](../../../docs/adr/0003-calibrate-bands-on-the-current-snapshot.md)) is built. This ticket resumes for the historical recalibration once credits arrive.
