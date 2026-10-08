# Show one real company from cached Sectors data

Status: done

## What to build

Open a dated Company view showing one real company's available Sectors v2 inputs, source coverage, and explicit reasons classification is unavailable. Probe the required endpoints within the confirmed credit allocation, cache captures for reuse, and preserve retrieval provenance. Show Unclassified rather than fabricating a state or historical outcome.

Source: [Company State Monitor v5](../../../sectors_company_state_monitor_v5.md).

## Acceptance criteria

- [x] A one-ticker probe captures company overview, a quarterly financial record, daily prices, and foreign flow, or reports endpoint-specific unavailability honestly.
- [x] Requests are limited by a confirmed credit allocation and per-run cap; documented cost estimates are distinct from measured provider charges.
- [x] Reusing a capture avoids an identical paid request; an offline regeneration makes no network calls.
- [x] API keys are read locally, excluded from version control, and absent from logs, caches, and generated public output.
- [x] The generated Company view displays a snapshot timestamp, raw available inputs, returned-date coverage, and retrieval provenance.
- [x] Missing inputs remain unavailable, not zero; accounting comparability, adjustment, peer, and calibration requirements are visible classification blockers.
- [x] Unclassified and Insufficient historical evidence remain separate; no state or outcome estimate is invented.
- [x] Public fetch/cache and snapshot-generation commands are tested at agreed seams; typechecking and code review are completed.
- [x] A live-data probe and browser inspection confirm the real end-to-end path before closing the ticket.

## Blocked by

None - can start immediately.

## Comments

Implementation requested directly by the user. Only ticket 1 is published here; the remaining proposed breakdown is not yet published.

Closed 2026-10-06. Live BBCA probe on 2026-10-06 returned all four endpoints. 39 unittest tests pass and mypy is clean. Offline rebuild makes no network calls, and a secret scan of cache/, dist/ and app/ found no key. The page was inspected in a browser over HTTP. Independent GPT review ran spec and standards lanes over 10 rounds, recorded as findings F1 to F11 (redirect key leak, refresh, response shape at the boundary including legacy captures, truncation, provider overcharge, error redaction, exact raw values, text fields, numeric plausibility bound, empty financials, credit reserve). Both lanes pass on the final follow-up. The allocation of 500 credits was confirmed by the user; probes keep a 10% reserve.
