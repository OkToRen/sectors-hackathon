# Verify the earnings basis for every roster member

Status: done

## What to build

Check each LQ45 member's Sectors quarterly earnings against that company's own published results, the way BBCA was checked in ticket 02. Every verified member gets exact period-to-value entries in `VERIFIED_BASIS`, with evidence, and starts showing comparable-quarter growth. A member whose figures do not match a published report stays "Basis unverified" with the reason. This ticket needs no Sectors credits.

Source: [Company State Monitor v5](../../../sectors_company_state_monitor_v5.md), "Data publication gates". Method: ticket 02 comments and `VERIFIED_BASIS` in `sectors/snapshot.py`.

## Acceptance criteria

- [x] Every member with captured quarters is checked for the latest quarter and the same quarter a year earlier.
- [x] Each verified entry records exact values and evidence: the published figure, its period, and its source.
- [x] A mismatch keeps the Accounting blocker and records why, for example cumulative figures, restatement or a different consolidation.
- [x] No source is invented. A member whose report cannot be found stays unverified, and the reason is recorded.
- [x] The rebuilt roster index and Company views show growth only for verified members.
- [x] Tests, typechecking and code review are complete. A browser check confirms the rebuilt views.

## Blocked by

Ticket 02. It can start now and runs in parallel with ticket 04.

## Comments

Closed 2026-10-06.

- Method: published half-year profits and their sources are entered in `research/published_earnings.csv`. `scripts/verify_earnings_basis.py` applies the rule offline to cached quarters and writes `research/earnings_basis.json`, which the build reads. Rule: Q1 + Q2 2026 must be within 1% of the published H1 2026 profit, and neither Q2 2026 nor Q2 2025 may be within 25% of its half-year total (that would suggest cumulative figures). Totals are validated after conversion to rupiah. Stored verified entries need a source and plausible values or they are not trusted.
- Outcome across the 42 members with captured quarters: 22 verified, 17 report in US dollars (Sectors converts them to rupiah, so rupiah growth would mix in exchange-rate moves), and 3 mismatches. BBRI is 1.03% off because its Sectors earnings include minority interests; earnings less minorities equals the published 31.18 tn exactly. BMRI is 8.03% off and ANTM 7.55% off. UNTR, UNVR and WIFI have no captured quarters.
- Effect: comparable-quarter growth now shows for 20 members, up from 1. Cross-check: CPIN's computed Q2 2026 growth of +211% matches a trade-press headline.
- Verification: 71 unittest tests and mypy pass; offline rebuild; secret scan clean; browser check of ICBP over HTTP. Independent GPT review: an initial round found B1 to B5 in both lanes; one follow-up found residuals of B1 and B3, fixed by validating both evidence entry points; both lanes pass the second follow-up.
