# Company State Monitor (v4)

**Sectors Hackathon 2026 · Track 03, Market Intelligence**
Submission deadline: 8 October 2026, 23:59 WIB. Registration and onboarding close 7 October, 23:59 WIB.

---

## Pitch

**One-liner:** A Sectors-powered monitor that flags when a company's fundamentals, price, and foreign flow start disagreeing, tests those setups on unseen historical data, and shows what happened the last time.

**Problem statement (for the submission form):**
> Retail investors and analysts following liquid IDX stocks have plenty of data but no quick way to see which companies just changed in a way that matters, so this tool flags those changes, explains the evidence, and shows how similar setups played out historically.

**Core question the product answers:** *Which companies just changed, why, and has this pattern meant anything before?*

This is an information and research tool. It does not give buy or sell recommendations.

---

## What changed from v3

| v3 issue | v4 resolution | Why |
|---|---|---|
| A ~20% fixed test window may hold only ~4 quarters, so a quarter-clustered bootstrap has ~4 clusters to resample | If the fixed test window has < 8 quarters, use expanding-window walk-forward as the primary evaluation; if still < 8 out-of-sample quarters, cap tiers at Weak | A bootstrap over ~4 clusters is not a real robustness check |
| Choosing a 45/60/75-day lag by train+val performance is still a tuned choice; one lag either leaks annual reports or wastes quarterly ones | Lag set per report type from regulatory filing deadlines, conservative end, never selected by performance | Removes a degree of freedom and avoids annual-report look-ahead |
| "Insufficient Evidence" listed as a Company State | Moved out of the states table; it is an evidence tier only | A company can be Ignored Improvement *and* have Insufficient evidence |
| Weak shows a Wilson interval that assumes independence | Tooltip: interval is optimistic because observations aren't fully independent | Pre-empts the obvious judge objection |
| Scope grew in v3, build plan didn't | Strong tier not built for MVP (cap at Moderate); dominance check, lag sensitivity, and Market Confirmation simplified; build plan re-split | Tuesday was ~2 days of work |
| Statistical jargon risked leaking into the main UI | Plain-language evidence labels in Company view; stats stay on Methodology page | Usability is 40% of the score |

---

## What changed from v2 (resolved in v3)

| v2 issue | v3 resolution | Why |
|---|---|---|
| Wilson intervals treated company-quarter observations as independent | Strong evidence now requires quarter-clustered bootstrap robustness | Companies in the same quarter share market and macro shocks |
| "Pool with exclusions" allowed post-hoc sector dropping | Removed; signals are pooled, independently sector-specific, or rejected | Prevents sector cherry-picking |
| Company state and Radar confidence both moved weekly | Company State is quarterly; Market Confirmation updates weekly | Aligns live monitoring with the historical observation unit |
| Candidate signals could still expand during experimentation | Candidate signal set is frozen before validation | Reduces researcher degrees of freedom |
| Only two simple baselines | Added a naive equal-weight composite baseline | Tests whether interaction/state logic adds value beyond simple aggregation |
| Historical analogues could become too sparse | Analogues match state + major driver pattern | Preserves sample size without exact feature-vector matching |
| Fixed 60-day reporting lag | Prefer filing date; otherwise choose 45/60/75-day fallback using train+validation only | Reduces look-ahead and arbitrary-lag dependence |
| Credit planning assumed extra member credits | Budget against only the guaranteed team allocation until organizer confirmation | Avoids designing around unconfirmed credits |

---

## Company states

States are assigned **quarterly** by deterministic rules on validated signals after the statement becomes usable under the filing-date / reporting-lag rule. No LLM decides state.

| State | Fundamentals | Price (sector-relative) | Foreign flow | Reading |
|---|---|---|---|---|
| **Ignored Improvement** | Improving | Flat or lagging | Neutral or accumulating | Business getting better, market hasn't priced it in |
| **Confirmed Strength** | Improving | Outperforming | Accumulating | All three agree |
| **Crowded Optimism** | Weakening | Outperforming | Accumulating | Enthusiasm running ahead of the numbers |
| **Early Deterioration** | Weakening | Not yet broken down | Neutral or distributing | Fundamentals cracking before price reacts |
| **Neutral** | No clear signal on enough dimensions | | | |

**Insufficient Evidence is not a state.** It is an evidence tier (see Evidence tiers). Company State and evidence strength are always shown separately, e.g. "Ignored Improvement · Evidence: Insufficient".

"Improving" and "weakening" are defined relative to the company's own history and its sector peers, using thresholds fixed on the training period only.

---

## Signal families

Candidate signals. Each one has to beat the baseline in validation to survive (see Methodology).

**Fundamental trajectory** (quarterly, after reporting lag)
- Revenue growth and its acceleration
- Earnings / EPS growth and its acceleration
- Margin change
- Operating cash-flow trend
- Leverage change

**Market behavior** (daily, sampled at quarterly observation dates for state assignment; recomputed weekly for Market Confirmation)
- 20 / 60-day sector-relative return
- Drawdown from 120-day high
- Abnormal volume vs 60-day average

**Foreign flow** (daily, sampled at quarterly observation dates for state assignment; recomputed weekly for Market Confirmation)
- Net foreign flow over 20 / 60 days, scaled by market cap
- Persistence: share of days with net foreign buying
- Price-flow divergence

Cut for the MVP: broker activity, analyst estimates, news, filings, dividend metrics.

---

## Methodology

### Universe
Start with LQ45 constituents that have adequate history.

Any organizer-confirmed credit pool beyond the guaranteed allocation goes toward sample size, in this order:
1. **Longer history for LQ45**, if the API has it. This adds out-of-sample observations per company and covers more market regimes.
2. **Widen to IDX80.** This adds companies per sector, which the heterogeneity test needs. If the API's history turns out to be shallow, do this first.

Document the final universe and date range in the README. The README also states plainly that this is not full-IDX coverage.

### Observation unit
One observation = one company at one quarterly **information-availability date**.

**Preferred rule:** use the actual Sectors filing / disclosure date if available.

**Fallback rule:** if filing dates are unavailable, set the lag **per report type from the regulatory filing deadlines**, taking the conservative end:
- **Interim (Q1–Q3) reports:** conservative end of the interim deadline (roughly 1–2 months depending on audit/review status)
- **Annual (Q4) reports:** the annual deadline (roughly 3 months)

**Verify the current OJK deadlines before coding these numbers.** The lag is never chosen by which value gives better results. A one-row sensitivity table (results at ±15 days) goes in `validation_report.md` as documentation only.

Price and flow features are computed as of the resulting observation date.

Observations are non-overlapping per company. Daily rows that reuse the same quarterly fundamentals are **not** counted as separate observations.

### Target
Sector-relative forward return: company return minus its sector's median return over the next 60 trading days (primary). 20 and 120 days are reported as secondary.

### Sector heterogeneity
A sector-relative target removes sector-wide moves from the return. It does **not** make a signal mean the same thing in every sector. Pooling is a hypothesis to test, not an assumption.

Run these checks on train + validation only for each candidate signal:
- **Per-sector direction check:** estimate the signal → forward-return relationship separately for each sector with ≥ 10 observations.
- **Leave-one-sector-out:** calibrate without sector S, then evaluate on S. Repeat for each sector.
- **Dominance check (simple version):** one table in `validation_report.md` showing each sector's share of observations and of the pooled effect. Flag any sector supplying more than half the effect.

Then assign exactly one status:
- **Pooled** if direction is broadly consistent and leave-one-sector-out does not reverse the conclusion.
- **Sector-specific** only if that sector has enough observations for its own independent validation and the sector rule is frozen before test evaluation.
- **Rejected** if the relationship materially reverses across sectors and sector-specific validation is too sparse.

**No post-hoc sector exclusions.** A sector cannot simply be removed because it weakens the result after inspection.

Per-sector results go into `validation_report.md`, with small cells explicitly flagged.

### Split
0. **Candidate-set freeze:** before opening validation results, freeze the complete candidate signal / transformation list in `research/candidate_signals.yaml`. New ideas discovered later are logged for future work and cannot enter the submitted model.
1. **Train:** earliest ~60% of dates. Fit thresholds / transformations and draft state rules using only that frozen candidate set.
2. **Validation:** next ~20%. Prune signals that flip sign, lose strength, fail heterogeneity checks, or fail baseline comparisons.
3. **Freeze** all signal definitions, thresholds, and state rules. Commit with a tag (`v-frozen`).
4. **Test:** final ~20%, untouched until after the freeze. All analogue stats in the product come from here.

### Evaluation mode (decided by history depth)
After the first fetch, count how many quarters the ~20% test window would contain.
- **≥ 8 quarters:** fixed split as above is the primary evaluation.
- **< 8 quarters:** use **expanding-window walk-forward** as the primary evaluation. Train on everything up to quarter q, predict quarter q+1, roll forward. This produces out-of-sample predictions for almost every quarter after the first training window. The candidate-set freeze and the frozen rule *definitions* still apply; only thresholds are refit at each step, using past data only.
- **Still < 8 out-of-sample quarters after walk-forward:** cap all evidence tiers at **Weak** and say so on the Methodology page.

Record the chosen mode and the quarter count in the README.

### Baselines
A signal or state rule must add value beyond all three baselines in validation:
- Sector-relative 60-day momentum alone
- Earnings-growth rank alone
- **Naive equal-weight composite:** standardized fundamental + price + foreign-flow family scores averaged with no interaction logic

The third baseline tests whether the project's divergence/state logic adds value beyond simply averaging the same ingredients.

### Evidence tiers
All tiers use **out-of-sample observations** and the primary 60-day horizon.

The UI may show a 95% Wilson interval for hit rate because it is intuitive, but company-quarter observations are not fully independent. Companies observed in the same quarter share market and macro shocks. Therefore, **Moderate and Strong evidence also require a quarter-clustered bootstrap that resamples whole observation dates/quarters rather than individual companies.**

| Tier | Requirements | What the product shows |
|---|---|---|
| **Insufficient** | n < 15 | No analogue percentage; label only |
| **Weak** | n ≥ 15, but the Wilson interval includes 50% or another Moderate requirement fails | Hit rate + interval, marked exploratory |
| **Moderate** | n ≥ 30; Wilson lower bound > 50%; same sign in validation and test; quarter-clustered bootstrap does not materially reverse the effect | Hit rate + interval + median excess return |
| **Strong** | n ≥ 50; Wilson lower bound > 55%; quarter-clustered bootstrap remains favorable for hit-rate uplift and median excess return; beats all three baselines on test; passes heterogeneity checks | Full stats |

Expect Strong to be rare, possibly absent. **For the MVP, Strong is not built.** Tiers cap at Moderate, and the Methodology page states that Strong requires more history than the current dataset provides. The Strong row stays here as the future definition.

**Quarter-count cap:** if the primary evaluation has < 8 out-of-sample quarters, no tier above Weak is shown, regardless of n.

**Weak-tier tooltip:** "This interval treats each company-quarter as independent. Companies in the same quarter share market shocks, so the true uncertainty is wider." 

Secondary horizons (20d, 120d) are shown for context but never set the tier.

### Historical analogue matching
Analogues match on:
1. **Company State**, and
2. **Major driver pattern** (for example, earnings acceleration + foreign accumulation + price lag).

They do **not** require an exact multidimensional nearest-neighbor match across every feature. The major-driver vocabulary is frozen before test evaluation. If a pattern has too few out-of-sample observations, the product shows **Insufficient Evidence**.

### Rejected signals
Every tested signal is logged with its decision, metric, and reason in `research/signal_log.csv`, and shown in the product's Methodology page. Rejected signals are part of the pitch, not something to hide.

---

## Evidence strength vs state confidence

These are two separate numbers and the product shows both.

**State confidence** asks how cleanly the company matches the **quarterly state rules** at its latest information-availability date. It is based on distance past frozen thresholds and agreement across signal families. Shown as High / Medium / Low.

**Market Confirmation** is separate and may update weekly using only price and foreign-flow data since the last quarterly state assignment. It can strengthen, weaken, or contradict the state, but it does not silently change the quarterly Company State.

MVP definition (keep it simple): compare the current sector-relative price and foreign-flow z-scores with their values at the last state assignment.
- Both moved in the direction the state implies → **Strengthening**
- Small change in both → **Stable**
- Moved against the state → **Weakening**
- Moved strongly against the state → **Contradicting**

Fix the thresholds on train data.

**Evidence strength** asks how much the historical pattern means. It is set strictly by the Evidence tiers table: Strong / Moderate / Weak / Insufficient. The hit-rate interval is always shown next to the label.

No 0–100 scores. Labels only, with the underlying numbers one click away.

---

## Product

Three views. Compare is folded into the Company view.

### 1. Radar (homepage)
- **Top section:** quarterly Company State transitions from the latest information-availability dates.
- **Main list:** companies ranked by weekly **Market Confirmation change** since their latest quarterly state.
- State flips are highlighted, but weekly price/flow movement never rewrites the quarterly state.

This keeps the live product aligned with the historical observation unit while still giving the Radar something useful to show outside earnings season.

### 2. Company view
- Current and previous quarterly state, transition date
- State confidence + evidence strength, using plain-language labels (see below)
- Weekly Market Confirmation: strengthening / stable / weakening / contradicting
- What changed (3 plain-language bullets max)
- Supporting vs contradicting evidence
- Peer strip: percentile vs sector on growth, valuation, return, and flow
- State timeline
- Historical analogues: n, % outperformed sector, median 60d excess return, median drawdown (out-of-sample only)

**Plain-language evidence labels (Company view)**

| Tier | What the user sees |
|---|---|
| Moderate | "Moderate evidence: held up on data the model never saw." |
| Weak | "Weak evidence: early pattern, not yet reliable." |
| Insufficient | "Not enough past cases to say." |

Terms like Wilson interval, clustered bootstrap, and walk-forward never appear in the Radar or Company view. They live on the Methodology page.

### 3. Methodology
- Evaluation mode (fixed split or walk-forward) and out-of-sample quarter count
- Universe and date range
- Train / validation / test dates
- Signal log (retained and rejected)
- Baseline comparison
- Disclaimer

### Example output (placeholder numbers)

> **[TICKER] · Ignored Improvement**
> Previous: Neutral · Changed: [n] trading days ago
> State confidence: High · Evidence strength: Moderate
>
> **What changed**
> - Earnings growth accelerated two quarters in a row
> - Net foreign buying on [x]% of the last 60 days
> - Price still [y]% behind sector over 60 days
>
> **Contradicting:** operating cash flow hasn't improved yet
>
> **Historically:** [n] out-of-sample cases with this setup. [z]% beat their sector over the next 60 trading days (95% interval [l]–[u]%). Median excess return [a]%, median drawdown [b]%.
>
> *Research and analysis only. Not investment advice.*

---

## Repo structure

```
scripts/
  fetch_data.py        # Sectors API → local cache, only fetches missing periods
  build_features.py    # features, reporting lag, peer normalization, targets
  run_validation.py    # train/val/test, baselines, signal_log.csv
  generate_states.py   # frozen rules → current states, transitions, analogues
research/
  candidate_signals.yaml # frozen before validation
  signal_log.csv
  validation_report.md
app/                   # Radar, Company, Methodology
cache/                 # gitignored raw responses
README.md              # universe, dates, how to reproduce, credit usage
```

Demo companies come from the generated Radar output. Nothing is hard-coded.

---

## API credit budget

**Engineering assumption: budget only against the guaranteed team allocation until organizers confirm anything beyond it.**

Do not design the MVP around unconfirmed per-member onboarding credits. If additional legitimate team credits are confirmed, treat them as expansion budget for longer history or a wider universe.

Everyone fetches into one shared cache, so no endpoint is ever pulled twice. Keep API keys out of the repo.

| Use | Est. share |
|---|---|
| Company metadata + sector membership | small |
| Quarterly financials for the universe | ~30% |
| Daily price history | ~30% |
| Foreign flow history | ~25% |
| Buffer for refreshes and mistakes | ~15% |

First action: one fetch per endpoint for one ticker to measure real cost and history depth, then adjust.

If credits run short, cut in this order:
1. IDX80 expansion
2. 120-day horizon
3. Foreign flow depth

---

## Fallback if no signal survives

If nothing beats the baselines out of sample, the product still works as a research triage tool:

> "Shows which companies' fundamentals, price, and foreign flow just started disagreeing, so you know where to look first."

Divergence detection is useful without predictive power. Analogue stats show as Weak or Insufficient, honestly, and the Methodology page becomes the credibility story ("we tested 12 signals, here's why none survived"). Same app, different framing in the video.

---

## Video plan

**Judging video (≤ 3 min)**

| Time | Beat | Content |
|---|---|---|
| 0:00–0:35 | Hook | One real transition from the Radar. "This company's earnings turned up two quarters ago. Price hasn't moved. Foreign money has." |
| 0:35–1:20 | Evidence | Company view: what changed, supporting vs contradicting, peer strip |
| 1:20–2:15 | Proof | Analogue stats, then the Methodology page: out-of-sample split, baseline comparison, rejected signals |
| 2:15–3:00 | Use it | Radar pan, who it's for, disclaimer, repo link |

**Teaser (1 min):** hook + Radar + one analogue stat. Screen recording only.

---

## Build plan

| Day | Focus |
|---|---|
| Mon 5 Oct | Register team, finish onboarding, claim credits. Measure endpoint cost and history depth, then decide evaluation mode (fixed split vs walk-forward). Verify OJK filing deadlines. Fetch and cache the universe. Write and commit `candidate_signals.yaml`. |
| Tue 6 Oct | Features, deadline-based lags, targets. Training/validation (or walk-forward) run, three baselines, per-sector direction table + simple dominance table. Prune, freeze, tag. |
| Wed 7 Oct | Out-of-sample evaluation and tiers (capped at Moderate). State engine, analogues, simple Market Confirmation. App: Radar, Company, Methodology. **Registration closes 23:59.** |
| Thu 8 Oct | Morning: polish, README. Afternoon: record both videos, social post, submit by ~20:00 for buffer. **Hard close 23:59.** |

**If Tuesday overruns, drop in this order:**
1. Secondary horizons (20d, 120d)
2. Leave-one-sector-out (keep the per-sector direction table)
3. Lag sensitivity table

Never drop the candidate freeze, the freeze tag, or the baselines.

Submitting freezes the repo. Fix nothing after you hit submit.

---

## Scope

**Must have**
- Cached Sectors pipeline, reproducible from scripts
- Fundamental + price signals
- Foreign flow, if history depth allows
- Candidate-set freeze + train/val/test split + freeze tag + three baselines + signal log
- Quarterly 4-state engine + simple weekly Market Confirmation + transitions + evidence tiers (capped at Moderate)
- Evaluation mode chosen by quarter count (walk-forward if < 8 test quarters)
- Deadline-based reporting lags
- Radar, Company view, Methodology page
- Disclaimer

**Should have**
- State timeline
- Walk-forward evaluation
- Secondary horizons (20d, 120d)

**Cut**
- Strong evidence tier (defined, not built)
- Jev classifier
- Broker data
- News and filings
- Alerts
- Wider universe
- Market-regime conditioning

---

## Resolved methodology risks

| Risk | Resolution |
|---|---|
| Cross-sectional dependence | Quarter-clustered bootstrap for Moderate / Strong evidence |
| Sector cherry-picking | No post-hoc exclusions; pool, independently validate sector-specific, or reject |
| Weekly-vs-quarterly mismatch | Quarterly Company State + separate weekly Market Confirmation |
| Researcher degrees of freedom | Freeze candidate signal set before validation |
| Complexity may add no value | Add naive equal-weight composite baseline |
| Sparse historical analogues | Match state + frozen major-driver pattern |
| Arbitrary reporting lag | Prefer filing date; otherwise choose 45/60/75-day lag using train+validation only |
| Unconfirmed credit assumptions | Budget to guaranteed allocation only |
| Too few clusters for bootstrap | Walk-forward if < 8 test quarters; cap at Weak if still < 8 |
| Lag chosen by performance | Deadline-based lag per report type; sensitivity table is documentation only |
| State vs evidence tier confusion | Insufficient Evidence is a tier, not a state |
| Wilson interval assumes independence | Weak-tier tooltip discloses it |
| Scope vs time | Strong tier not built; simplified checks; re-split build plan with drop order |
| Jargon hurting usability | Plain-language labels in main UI; stats on Methodology page |

---

## Success criteria

1. Pipeline runs end to end from `fetch_data.py` to the app on real Sectors data.
2. Universe, date range, split dates, and credit usage are documented in the README.
3. `candidate_signals.yaml` is frozen before validation results are inspected.
4. The model freeze tag exists in git history before test-set results.
5. Every analogue statistic shown is out-of-sample, carries its evidence tier, and respects the tier rules.
6. Moderate / Strong claims include quarter-clustered bootstrap robustness checks.
7. Every pooled signal has a recorded heterogeneity result; there are no post-hoc sector exclusions.
8. The signal log includes rejected signals.
9. Demo companies come from generated output.
10. No buy / sell / attractive / avoid language appears in the UI.
11. Weekly Market Confirmation never rewrites a quarterly Company State without a new quarterly observation.
12. The product remains useful under the divergence-triage fallback.
13. Evaluation mode and out-of-sample quarter count are recorded in the README; no tier above Weak appears with < 8 out-of-sample quarters.
14. Reporting lags come from filing deadlines, not from performance.
15. No statistical jargon appears in the Radar or Company view.

---

## Decisions log

| Question | Decision |
|---|---|
| Is LQ45/IDX80 credible? | LQ45 core; extra confirmed credits buy longer history first, then IDX80 |
| Fixed split or walk-forward? | Decided by history depth: fixed split if ≥ 8 test quarters, otherwise expanding-window walk-forward |
| Reporting lag | Per report type from OJK deadlines, conservative end; never tuned |
| Strong tier | Defined but not built for MVP; cap at Moderate |
| Candidate-set freeze | Freeze `candidate_signals.yaml` before validation |
| Minimum sample size | n ≥ 15 to show a number (Weak at most); Moderate n ≥ 30; Strong n ≥ 50 plus clustered-bootstrap checks |
| Baselines to beat | Sector-relative momentum, earnings-growth rank, naive equal-weight composite |
| Show probabilities or labels? | Labels, with numbers one click away |
| Sectors that don't generalize | Pooled, independently validated sector-specific, or rejected; no post-hoc exclusions |
| State update cadence | Company State quarterly; Market Confirmation weekly |
| Analogue matching | State + major driver pattern, not exact feature vector |
| Weak evidence | Insufficient / Weak, never hidden |
| Recommender risk | State names describe data; analogues show distributions; disclaimer on company view |
| Why come back? | Weekly Market Confirmation shifts plus quarterly state transitions |

## Still open

- Actual history depth for financials, prices, and foreign flow
- Whether Sectors exposes filing dates; if not, verify current OJK interim and annual filing deadlines
- How many out-of-sample quarters the data supports (sets evaluation mode and tier cap)
- Exact null coverage across the chosen universe
- Exact credit cost per endpoint
- Whether any legitimate additional team credits exist beyond the guaranteed allocation
- Real team size
