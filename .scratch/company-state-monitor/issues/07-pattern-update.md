# Show Pattern Update since each state assignment

Status: done

## What to build

For each classified company, compare the snapshot's price and flow measures with their values at the latest state assignment, using the frozen measures and bands. Label the result Contradicting, Stable, Strengthening, Weakening or Mixed, with raw changes and a plain-language explanation.

Source: [Company State Monitor v5](../../../sectors_company_state_monitor_v5.md), "Pattern Update".

## Acceptance criteria

- [x] Normalized support distances follow the v5 formulas for each state's allowed ranges, with inclusive neutral boundaries.
- [x] Labels apply in the v5 order with the 0.25 tolerance.
- [x] Neutral shows raw changes only. Unclassified has no label. Missing inputs give an unavailable update, not Stable.
- [x] A stale company keeps contextual changes but is excluded from the default ranking.
- [x] Ignored Improvement says "price catching up" where that applies.
- [x] Tests cover each label, the boundaries and the unavailable cases. Typechecking, code review and a browser check are complete.

## Blocked by

Ticket 06.

## Comments

Scope note 2026-10-06: Pattern Update compares the latest snapshot measures with those at the estimated availability date of the latest state, using the snapshot-calibrated bands of [ADR 0003](../../../docs/adr/0003-calibrate-bands-on-the-current-snapshot.md).

Done 2026-10-06: a stale company's update stays available, and roster.json records `ranked: false` for it so the Radar (ticket 09) leaves it out of the default ranking. The "price catching up" wording now covers Mixed as well as Weakening, a gap the GPT spec and standards reviews both caught; their follow-up round passed. The browser check confirmed the text renders, but the page loaded without its stylesheet, so the layout was not checked.
