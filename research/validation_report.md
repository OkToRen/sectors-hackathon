# Validation report

The v5 completion criteria, checked against the snapshot built on 2026-10-06 and rebuilt on 2026-10-08 with three page-copy fixes. Evidence is a test, a file or the generated output. Three criteria depend on the chronological holdout. That holdout was not funded ([ADR 0003](../docs/adr/0003-calibrate-bands-on-the-current-snapshot.md), ticket 08 deferred), so those criteria are met only in their "say nothing" form and are marked as cut.

| # | Criterion | Status | Evidence |
| ---: | --- | --- | --- |
| 1 | A real cached-data pipeline generates the dated app and can be regenerated manually | Met | `scripts/build_snapshot.py` builds from `cache/`. `scripts/check_reproduction.py` rebuilt 94 files in a clean copy with sockets blocked and no `SECTORS_*` variables, with 0 differences from `dist/` beyond the timestamp. |
| 2 | Universe, sector mapping, coverage, exclusions, dates and credit usage are documented | Met | README sections Snapshot and Credit usage. `dist/roster.json` records capture dates. The Radar counts each exclusion with its reason. |
| 3 | Required accounting, peer, adjustment and availability checks pass for every published calculation | Met | Every check blocks its calculation instead of approximating it. Tests: `test_growth_needs_both_periods_verified`, `test_verification_binds_the_values_not_just_the_periods`, `test_price_needs_61_closes_and_five_aligned_peers`, `test_a_corporate_action_in_the_window_blocks_price`, `test_a_report_is_not_classified_before_its_estimated_availability`, `test_missing_values_stay_unavailable_not_zero`. |
| 4 | State mappings are exhaustive via Neutral and Unclassified, and mutually exclusive | Met | `test_every_combination_maps_to_exactly_one_state`. A missing dimension is Unclassified (`test_a_missing_dimension_is_unclassified_with_usable_dimensions_kept`). |
| 5 | State assignment is independent of historical performance and changes only on new quarterly information | Met | Bands come from inputs only (`test_band_is_the_25th_percentile_of_absolute_values`). A state is recorded once per company and report period (`test_an_assignment_is_recorded_once_and_never_overwritten`, `test_a_recorded_state_survives_rebuilds_and_data_revisions`). |
| 6 | Stale, Unclassified, evidence labels and Pattern Update have separate meanings and displays | Met | Separate fields and page sections. Tests: `test_an_unusable_newer_report_keeps_the_dated_state_and_marks_it_stale`, `test_an_overdue_next_report_is_flagged_separately`, `test_neutral_gets_raw_changes_and_missing_inputs_are_unavailable`, `test_stale_and_unclassified_are_excluded_and_counted_with_reasons`. |
| 7 | Freeze evidence predates holdout inspection; outcome windows crossing fitting boundaries are excluded | Cut, holdout unfunded | The freeze (`research/bands_freeze.json`, 2026-10-06 15:07 UTC, bound to the definitions' SHA-256) exists. 10 states recorded under the first freeze at 14:03 UTC keep its bands, and Methodology says so. No holdout was opened, so nothing could be inspected before or after it. |
| 8 | Historical summaries use completed holdout cases only and obey the 15-case threshold | Cut, holdout unfunded | No historical summary is shown anywhere. Every evidence label is Insufficient (`test_no_state_or_outcome_is_invented`). |
| 9 | Weak is the highest evidence label; no predictive-superiority or historical-executability claim appears | Met | Only Insufficient is ever assigned. `test_no_page_recommends_and_statistics_stay_on_methodology` scans every generated page for advice language. Methodology states the retrospective limitation. |
| 10 | All three reference comparisons and their availability and limitations are recorded | Partly met | All three references are defined on Methodology and recorded as unavailable for want of a holdout. No reference result exists. |
| 11 | Demo companies come from generated output, with no fabricated numbers or hard-coded success stories | Met for the app; a silent video is drafted, narration is open | Every page number comes from cache and research files. Tests use literal expected values against fixtures, not published pages. `submission/demo.mp4` is rendered by `scripts/render_demo.py` from headless-Chrome captures of `dist/`. A narrated recording is still the operator's. |
| 12 | The user can identify which report deserves closer reading even when historical evidence is Insufficient | Met | The Radar lists the 31 current states with their Pattern Update cue and links each to its Company view. Each Company view names the latest report period and what changed. |

## Cut items

Per the v5 cut order, history-dependent work was cut first and accurate inputs, classification, explanation and disclosure were kept. Cut items:

- the chronological split
- holdout evaluation
- outcome summaries
- reference results
- secondary horizons
- drawdown
- peer strips
- timelines
- automatic refresh

The holdout needs about 12 credits per ticker-year, roughly 540 credits per extra year across 45 members. The ledger stands at 472 of the 500-credit allocation. The team has added credits since, but the new total has not been confirmed.
