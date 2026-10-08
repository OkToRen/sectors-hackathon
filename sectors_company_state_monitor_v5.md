# Company State Monitor (v5)

Sectors Hackathon 2026 · Market Intelligence

This plan consolidates the decisions confirmed during the grill-with-docs interview. The original v4 is preserved. Submission dates carried forward from v4: 8 October 2026, 23:59 WIB; registration/onboarding close 7 October, 23:59 WIB. Check organizer requirements before submission.

## Product and user

**One-liner:** A dated snapshot of current LQ45 companies that explains where fundamentals, price, and foreign flow disagree, with exploratory historical comparisons.

**Primary user:** An individual who already follows an IDX watchlist and reviews it weekly.

**Immediate job:** Decide which company's latest financial report deserves closer reading.

**Core question:** Which companies changed, what changed, and what happened in past cases with the same descriptive state?

The product describes observations and historical outcomes. It makes no buy/sell recommendations or claims of a superior investment strategy. A failed historical comparison does not remove a descriptive state.

## What changed from v4

- Descriptive state rules are independent of predictive validation.
- The final chronological holdout stays untouched; walk-forward is limited to development data.
- Results are retrospective research until original disclosure dates and historical data vintages are verified.
- Evidence caps at Weak for this submission. Moderate and Strong are disabled.
- Historical cases match state only. State confidence and major-driver subdivisions are removed.
- Missing classification inputs produce Unclassified; overdue data produces a separate Stale flag.
- Market Confirmation is renamed Pattern Update and measures descriptive pattern persistence.
- The deliverable is a dated static snapshot with manual regeneration, planned for one builder.
- All reference comparisons remain, but states need not beat them to exist.

## Domain boundaries

Canonical terms live in `CONTEXT.md`.

Keep these separate in data and presentation:

1. **Company State:** the descriptive classification at an information-availability date.
2. **Data availability:** whether required inputs support classification.
3. **Freshness:** whether a previously assigned state is awaiting overdue information.
4. **Pattern Update:** subsequent price/flow movement relative to the assigned pattern.
5. **Evidence Strength:** support for the historical estimate, not outcome direction.
6. **Historical outcomes:** observed sector-outperformance rate and median sector-relative return.

Neutral means "No named setup matched," not "Nothing notable happened." Unclassified is not a Company State. Stale retains the dated previous state rather than rewriting it. Insufficient refers to historical evidence rather than current classification inputs.

## Universe and data contract

Use the current LQ45 roster over each company's available history. Keep the full roster visible, including companies with unavailable classifications. Record roster capture date, sector mapping date, coverage, exclusions, and reasons.

Historical results describe today's constituents using the available sector mapping. They do not represent a historical LQ45 portfolio, and they inherit current-membership selection and potentially current-sector classification limitations.

Use Sectors v2. Its documentation establishes current membership lookup, quarterly financial records, and a foreign-flow request window; actual historical coverage and point-in-time fidelity require probes.

### Probe before bulk fetching

Fetch one ticker across the necessary endpoints and inspect:

- Actual credit charges and the confirmed team allocation.
- Available dates and missing periods for financials, prices, and foreign flow.
- Whether financial `date` means period end, and whether a separate original disclosure timestamp is returned.
- Original-versus-restated values, version identifiers, and any as-of retrieval support.
- Standalone-versus-cumulative quarterly earnings, accounting units, currencies, and consolidation basis.
- Corporate-action adjustment, dividend treatment, trading dates, and market-cap dates.
- Current roster/sector fields and any documented historical membership support.

Record findings and example schemas without secrets. Budget only against verified team credits. Stop expansion before exceeding that budget; retain a refresh/error buffer. Cache responses by endpoint and parameters, fetch only missing periods, and keep keys out of the repository.

Foreign flow permits at most 90 days per request; this is not evidence of only 90 days of total history. Probe depth and paginate/cache accordingly.

### Data publication gates

Require comparable accounting units and standalone-quarter earnings. Derive standalone quarters from cumulative reports only when their basis matches; Q4 can be full-year less nine-month earnings only under that same check.

Percentage earnings growth requires positive current and prior comparable-quarter earnings. Loss-to-profit, profit-to-loss, persistent losses, zero boundaries, and inconsistent accounting remain explicitly identified and Unclassified in this MVP.

Use verified corporate-action-adjusted prices. Label price return versus total return according to the actual series; do not imply dividends are included unless verified. Unresolved corporate actions block affected calculations.

Require at least five other eligible current-sector peers for each sector median. Use the same eligible-peer definition consistently for feature and outcome calculations and disclose peer counts. Missing peer data blocks the affected feature/outcome; never fill missing inputs with zero.

### Information availability and freshness

Use verified original disclosure dates when available. Otherwise use an explicitly marked estimated availability date. A conservative three-calendar-month proxy may be used for unknown report audit status, but is an estimation convention, not a claim of actual filing or an exact legal deadline for every quarter.

Annual financial statements and annual reports are different documents. OJK's documented annual financial-statement deadline is month three; the separate annual-report deadline is month four. Half-year financial-statement deadlines depend on audit/review status. Verify applicable interim rules before representing any date as a regulatory deadline.

If original dates or data vintages remain unverified, display: "Retrospective research using available historical records; original availability and revisions are not fully verified." A lag does not repair restatement or late-filing uncertainty.

Preserve the last assigned state and its date. Once the next expected report's availability deadline passes without usable inputs, mark Stale and exclude it from default Radar ranking. When the schedule is estimated, label the freshness date/flag as estimated too.

## Descriptive state engine

One observation is one company/reporting quarter at its actual or explicitly estimated information-availability date. Classification uses only inputs dated on or before that date. Current snapshot assignment also includes observations whose future outcomes are not yet complete.

### Three primary dimensions

| Dimension | Measure | Positive category | Neutral category | Negative category |
| --- | --- | --- | --- | --- |
| Fundamentals | Comparable standalone-quarter earnings growth against the same quarter a year earlier | Improving | Flat | Weakening |
| Price | Company 60-trading-day return less median eligible-sector-peer return over the same dates | Leading | Flat | Lagging |
| Foreign flow | Net foreign flow over 60 trading days divided by market cap at the observation date | Accumulating | Neutral | Distributing |

For each measure, its neutral-band half-width `b` is the 25th percentile of absolute values in training data, estimated without forward returns. Values above `b` are positive; below `-b` negative; boundaries are neutral. Use pooled training calibration for the MVP and disclose the calibration population. A zero, nonfinite, or otherwise unusable band blocks that dimension rather than receiving an invented fallback.

Freeze numerical bands before holdout evaluation. Supporting metrics such as revenue, margins, cash flow, or leverage can explain or contradict a state when available; they do not silently enter its classification rule.

### Exact state mapping

Every condition in a row is required. The rows are mutually exclusive.

| State | Fundamentals | Price | Foreign flow |
| --- | --- | --- | --- |
| Ignored Improvement | Improving | Flat or lagging | Neutral or accumulating |
| Confirmed Strength | Improving | Leading | Accumulating |
| Crowded Optimism | Weakening | Leading | Accumulating |
| Early Deterioration | Weakening | Flat or leading | Neutral or distributing |
| Neutral | Any complete combination matching no row above | | |

Any missing required dimension yields Unclassified, with usable dimensions still displayed. All states remain descriptive regardless of historical results. A state changes only on a new quarterly observation, never on a later price/flow update.

### Missing flow

- Current flow missing: Unclassified, with usable fundamentals and price visible.
- Historical flow missing but current inputs usable: assign the current state; historical evidence may be Insufficient.
- Partial coverage: show affected periods and coverage limits explicitly.

## Pattern Update

Compare snapshot price/flow measures with their values at the latest state assignment, using the same frozen measures and bands. It describes persistence of that state's market pattern, not investment attractiveness.

For a measure `x`, define its normalized support distance inside the state's allowed range:

- Positive category required: `(x - b) / b`.
- Neutral or positive allowed: `(x + b) / b`.
- Neutral or negative allowed: `(b - x) / b`.

Apply the corresponding allowed range to price and flow for each named state. Define a change tolerance of `0.25` in normalized support distance. Apply labels in this order:

1. **Contradicting:** either current dimension lies outside its allowed range.
2. **Stable:** both support-distance changes are within ±0.25.
3. **Strengthening:** both support distances increased by more than 0.25.
4. **Weakening:** at least one decreased by more than 0.25 and neither increased by more than 0.25.
5. **Mixed:** every remaining combination.

Respect inclusive neutral-band boundaries. Show raw price and flow changes with a plain-language explanation. Neutral receives raw changes only. Unclassified has no pattern label. Missing update inputs produce an unavailable update, not Stable. A stale company's prior state can retain contextual changes but stays outside the default ranking.

For Ignored Improvement, price catching up can weaken the original divergence. Say "price catching up" rather than implying deterioration in investment outlook.

## Historical evaluation

### Primary outcome

Use 60-trading-day sector-relative forward return: company return less the median eligible-sector-peer return over exactly the same dates. Use the verified return convention described above.

One case per company/reporting quarter. Only complete 60-day outcomes enter historical statistics or outcome-informed development decisions. Unfinished observations remain available for current classification.

Company/report dates can be irregular, so outcome windows may overlap. Disclose this and shared company/quarter/sector dependence; do not claim independent observations.

### Chronological protocol

1. Freeze the complete candidate/feature/transformation list before inspecting development comparison results.
2. Use shared calendar boundaries across companies: earliest approximately 60% of observation dates for training, next 20% for development comparison, final 20% for untouched holdout.
3. At every fitting/selection boundary, include only observations whose forward-outcome window has ended before that boundary. Purge earlier observations whose outcomes extend across it.
4. Calibrate bands from training inputs without outcome optimization.
5. Walk-forward may be used inside development data only. At each step, use past inputs and completed outcomes only.
6. Freeze state definitions, thresholds, reference groups, and display rules before opening holdout results. Record the freeze in version-control history once the repository exists.
7. Evaluate the holdout once for this submission. Log later ideas for future work, not changes selected on holdout performance.

Record exact boundaries, date ranges, completed-case counts, distinct quarters, and excluded windows. A short holdout stays short; do not recycle development observations into the product's historical evidence.

### Historical cases and evidence

Match holdout cases by Company State only, pooled across the disclosed current-constituent universe. Do not subdivide by driver patterns or remove sectors after viewing their results.

| Evidence label | Requirement | Display |
| --- | --- | --- |
| Insufficient | Fewer than 15 completed eligible holdout cases | Case count and "Not enough past cases to say"; no outcome percentages or aggregate return claims |
| Weak / exploratory | At least 15 completed eligible holdout cases | Case count, distinct quarters, observed sector-outperformance rate, median excess return, and coverage/concentration disclosures |

Moderate and Strong are disabled for this submission. A positive or negative estimate does not promote evidence strength. Display observed outcomes, not a directional advantage inferred from weak estimates.

Describe company or sector concentration explicitly, with counts/shares. Discuss dependence and uncertainty on Methodology. Any interval shown there must state its assumptions; a Wilson interval treats cases as independent and must be labeled optimistic. No bootstrap robustness or significance claim is required or implied by Weak.

### Three reference comparisons

Keep all three:

1. 60-day sector-relative momentum.
2. Comparable-quarter earnings growth.
3. Equal-weight composite of standardized fundamental, price, and foreign-flow measures.

For the composite, standardize using training means and standard deviations; invalid training variance blocks the affected comparison. Freeze training-derived lower/upper-third cutoffs for each reference score before holdout evaluation. Apply them to the same eligible holdout population as the state comparisons.

Report group outcome distributions and sample counts alongside state results. State and reference groups may overlap and are not matched causal comparisons. No significance, strategy superiority, or requirement that states beat every reference. Record small cells and sector/company composition.

### Research artifacts

- `research/candidate_signals.yaml`: feature definitions, accounting/availability conventions, bands, state rules, and reference definitions with freeze status.
- `research/signal_log.csv`: candidate decisions and data-quality/research findings, including rejected exploratory ideas.
- `research/validation_report.md`: probes, exclusions, chronological boundaries, reference comparisons, composition, limitations, and completed-case counts.
- README: universe, sector mapping, dates, snapshot time, actual credit usage, manual regeneration, and reproduction instructions.

## Three product views

### Radar

Show snapshot date and coverage. Lead with recent quarterly state transitions, ordered by observation date. Use Pattern Update changes as secondary research cues, with a deterministic ticker tie-break rather than a claim of investment attractiveness.

Keep the full roster accessible; default ranking excludes Stale and Unclassified companies. Show counts and reasons for those exclusions. Link each company to the report-review workflow and Company view.

### Company

- Current/previous dated state, or Unclassified with reasons.
- Separate freshness flag and actual/estimated availability date.
- Three primary dimension labels and raw values.
- Up to three "what changed" bullets.
- Available supporting and contradicting metrics.
- Pattern Update and raw price/flow changes.
- Historical cases, Weak/Insufficient label, composition, and permitted outcome summaries.
- Retrospective-data limitation near historical results.
- Research-only disclaimer; no buy/sell/attractive/avoid language.

No High/Medium/Low state confidence, prediction score, or 0–100 score. Statistical terminology stays on Methodology. Source-report links are useful when returned by verified data; do not invent them.

### Methodology

Explain source coverage, publication/vintage limitations, current-universe selection, accounting and return conventions, neutral bands, state mappings, Pattern Update semantics, split/freeze, completed outcomes, reference comparisons, composition, uncertainty, and signal log.

## Delivery and cut order

Plan for one builder. Generate a static app from cached data with a dated snapshot and a manual refresh command. No background scheduler or live-monitor promise is required.

First make one real company work end to end, then expand to the roster. A data-quality gate can block publication even under deadline pressure; publish unavailable labels and reasons instead of invented results.

Suggested sequence, aligned with v4's submission window:

- **5 October:** organizer onboarding/credit confirmation, one-ticker probes, data contract, candidate freeze, one-company vertical slice.
- **6 October:** cache expansion, accounting normalization, features, training bands, development/reference comparisons, rule freeze.
- **7 October:** holdout evaluation, state generation, Pattern Update, Radar/Company/Methodology, coverage checks.
- **8 October:** polish, reproduction check, README, real-output video, and submission with buffer.

Prioritize accurate inputs, classification, explanation, and disclosure; historical comparisons come next. If evidence is sparse, keep Insufficient. If no comparison is favorable, the research-triage product still works.

Cut secondary horizons, median drawdown, peer strips, timelines, automatic refresh, richer confidence labels, driver matching, and wider-universe expansion. Preserve all three reference definitions and report unavailable comparisons honestly if their inputs fail.

## Completion criteria

1. A real cached-data pipeline generates the dated app and can be regenerated manually.
2. Universe, sector mapping, coverage, exclusions, dates, and credit usage are documented.
3. Required accounting, peer, adjustment, and availability checks pass for every published calculation.
4. State mappings are exhaustive via Neutral/Unclassified handling and mutually exclusive.
5. State assignment is independent of historical performance and changes only on new quarterly information.
6. Stale, Unclassified, evidence labels, and Pattern Update have separate meanings and displays.
7. Freeze evidence predates holdout inspection; outcome windows crossing fitting boundaries are excluded.
8. Historical summaries use completed holdout cases only and obey the 15-case display threshold.
9. Weak is the highest evidence label; no predictive-superiority or historical-executability claim appears.
10. All three reference comparisons and their availability/limitations are recorded.
11. Demo companies come from generated output; no fabricated numbers or hard-coded success stories.
12. The user can identify which report deserves closer reading even when historical evidence is Insufficient.

## Verified documentation and remaining gates

- [Sectors quarterly financials](https://docs.sectors.app/api-references/v2/indonesia/report/quarterly-financials): documented report date; original publication timestamps and revision history are not established by the public schema.
- [Sectors quarterly-date helper](https://docs.sectors.app/api-references/v2/indonesia/helper-list/company-quarterly-dates).
- [Sectors foreign flow](https://docs.sectors.app/api-references/v2/indonesia/brokers/foreign-flow-by-symbol): up to 90 days per request; earliest historical coverage remains a probe.
- [Sectors companies screener](https://docs.sectors.app/api-references/v2/indonesia/screener/companies): current sector/index fields; historical membership remains unverified.
- [Sectors v2 migration](https://docs.sectors.app/get-started/v2/migration-guide): v1 endpoints discontinued 11 May 2026.
- [OJK POJK 14/2022](https://www.ojk.go.id/id/regulasi/Documents/Pages/Penyampaian-Laporan-Keuangan-Berkala-Emiten-atau-Perusahaan-Publik/POJK%2014%20-%2004%20-%202022.pdf): annual financial statements and audit-dependent half-year timing.
- [OJK POJK 29/2016](https://www.ojk.go.id/id/kanal/pasar-modal/regulasi/peraturan-ojk/Documents/Pages/POJK-Laporan-Tahunan-Emiten-Perusahaan-Publik/POJK-Laporan-Tahunan.pdf): separate annual-report timing.

Remaining gates are factual: actual credits, endpoint costs, history depth, missing values, accounting schema, publication/vintage fidelity, adjustments, peer coverage, and applicable IDX interim deadlines. They are not permission to silently substitute convenient data or promise unsupported results.
