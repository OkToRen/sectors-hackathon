# Show the LQ45 roster with peer coverage and comparable-quarter earnings

Status: done

## What to build

Extend the one-company slice to the current LQ45 roster. Capture the roster and current sector mapping, then run the existing probe for every member within the remaining confirmed allocation. Normalize quarterly earnings into standalone comparable quarters where the accounting basis allows it. The Company view for each member then shows peer counts and comparable-quarter earnings, or a specific reason it cannot. Classification stays Unclassified, because the neutral-band calibration needs historical depth that this ticket deliberately does not fetch.

Source: [Company State Monitor v5](../../../sectors_company_state_monitor_v5.md), sections "Universe and data contract", "Data publication gates" and "Delivery and cut order".

## Budget context

The confirmed allocation is 500 credits, and the ledger counted 16 by 2026-10-06. The current window costs about 8 documented credits per ticker, so the roster costs about 360. Historical depth does not fit. Foreign flow allows at most 90 days per request, so five years is about 20 requests per ticker. That depth is a separate ticket, decided after this one measures real costs.

## Acceptance criteria

- [x] The roster lookup records the capture date, the sector mapping date and every member. A member that cannot be probed stays visible with its reason.
- [x] A dry-run plan prints the planned requests, the documented cost and the remaining allocation before any spend, and makes no network call.
- [x] Roster probing reuses existing captures, honours the per-run cap and the allocation, and stops on any overcharge evidence, as in ticket 1.
- [x] Each sector shows its count of eligible current-sector peers. A sector with fewer than 5 other eligible peers keeps the Peers blocker.
- [x] Standalone-quarter earnings come straight from the data, or are derived from cumulative reports only when the basis is verified to match. Otherwise the Accounting blocker stays, with its reason.
- [x] Comparable-quarter growth is computed only when both quarters have positive earnings. Loss-to-profit, profit-to-loss, persistent losses and zero boundaries each get their own label and stay Unclassified.
- [x] Missing inputs stay unavailable, never zero. No state, band or outcome is invented.
- [x] A Company view is generated for each member offline from cache, with a roster index linking them.
- [x] Tests cover the roster, planning, normalization and generation seams. Typechecking and code review are complete.
- [x] A live roster probe and a browser check of the generated views confirm the real end-to-end path before the ticket closes.

## Blocked by

Ticket 01 (one company from cached Sectors data).

## Comments

Closed 2026-10-06.

- Roster: GET /v2/companies/?where=indices in ['LQ45']&limit=200 cost 1 credit and returned 45 members (symbol and name only); sectors come from each member's company overview.
- Live probe: the first run hit HTTP 429 RATE_LIMIT_EXCEEDED on 54 requests after about 134 rapid ones, and the ledger booked 92 conservative credits for them because the docs do not state a 429 cost except for foreign flow. The probe now stops a run at the first 429. A second run fetched the rest within the allocation. The ledger stands at 450 of 500 with the 50-credit reserve untouched. UNTR, UNVR and WIFI are incomplete and stay listed with reasons.
- Earnings basis: the Sectors docs do not state standalone versus cumulative. BBCA's Q1 and Q2 2026 sum to IDR 29.56 tn against BCA's published consolidated H1 2026 net profit of IDR 29.5 tn, and Q2 2025 (IDR 14.88 tn) is half of the published H1 2025 (IDR 29.0 tn). Only these exact values are verified; every other company shows "Basis unverified" and keeps an Accounting blocker.
- Output: 45 Company views and a roster index; 27 members have at least 5 peers with aligned positive closes; Financials has only 5 members, so banks keep the Peers blocker.
- Verification: 61 unittest tests and mypy pass; offline rebuild; secret scan clean; browser check over HTTP. Independent GPT review: one initial round (both lanes) produced T1 to T7, fixed by root cause; follow-ups added T8 and two T1 residuals; both lanes pass the final follow-up.
