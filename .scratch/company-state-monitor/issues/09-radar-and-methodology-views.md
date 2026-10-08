# Build the Radar and Methodology views

Status: done

## What to build

Radar leads with recent quarterly state transitions, using Pattern Update as a secondary cue and a deterministic ticker tie-break. It excludes Stale and Unclassified companies from the default ranking while showing their counts and reasons. Methodology explains sources, limitations, conventions, bands, mappings, the split and freeze, outcomes, references, composition and uncertainty.

Source: [Company State Monitor v5](../../../sectors_company_state_monitor_v5.md), "Three product views".

## Acceptance criteria

- [x] Radar shows the snapshot date and coverage, orders transitions by observation date, and links each company to its Company view.
- [x] The full roster stays reachable. Excluded companies are counted with reasons.
- [x] Methodology covers every topic v5 lists, including the retrospective-research limitation.
- [x] Statistical terms appear only on Methodology. No attractiveness or recommendation language appears anywhere.
- [x] Every number shown comes from generated output, with no hard-coded examples.
- [x] Tests, typechecking, code review and a browser check at phone and desktop widths are complete.

## Blocked by

Tickets 06 and 07 for Radar. Ticket 08 for the historical parts of Methodology.

Done 2026-10-06: the Radar is now the home page, with the full roster table below it. Methodology is `methodology.html`. Its historical sections say plainly that no holdout, completed outcome or reference comparison exists yet (ticket 08 is deferred, ADR 0003), so they need revisiting when ticket 08 lands. "Statistical terms" was read as inference vocabulary (percentile, quantile, significance, confidence, p-value, standard deviation). A build test enforces it, and the price measure's "sector median" stays on Company pages. The GPT spec and standards reviews raised seven findings: estimated dates were unlabelled, an unavailable update was shown as raw changes, Methodology skipped band validation, two prose mismatches, a truncated signal-log finding, and wrong empty-table spans. All were fixed and the follow-up round passed.
