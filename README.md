# Company State Monitor

A research triage tool for people reviewing an IDX watchlist. For each current LQ45 member it describes, at a dated snapshot, how fundamentals, sector-relative price and foreign flow combine into a Company State, and how that pattern has moved since. It helps decide which financial report to read next. It does not forecast returns or recommend trades.

The app is a static site generated from cached Sectors API v2 responses. Open `dist/index.html` after a build.

- **Radar** (`index.html`) lists current states, newest observation first, and counts the members left out with their reasons. The full roster sits below it.
- **Company views** (`<SYMBOL>.html`) show the dated state, the raw inputs, the three dimension readings, Pattern Update and every blocker.
- **Methodology** (`methodology.html`) explains sources, conventions, bands, mappings, the freeze and what cannot yet be said.

## Snapshot

| | |
| --- | --- |
| Universe | Current LQ45 roster, 45 members, captured 2026-10-06 05:20 UTC |
| Sector mapping | Each member's current sector from its Sectors company overview, retrieved 2026-10-06 05:21 to 09:01 UTC; 9 sectors |
| Latest report | Quarter ending 2026-06-30, treated as public 2026-09-30 (estimated: period end plus three months) |
| Market data | Daily prices and foreign flow up to 2026-10-05 |
| Bands frozen | 2026-10-06 15:07 UTC (`research/bands_freeze.json`). 10 states recorded under the first freeze at 14:03 UTC keep its bands, since a recorded state is never rewritten |
| Pages generated | 2026-10-08 (each page shows its own generation time) |

**Coverage.** 31 of 45 members have a Company State: 27 Neutral, 2 Early Deterioration, 1 Ignored Improvement, 1 Confirmed Strength. 13 of them are priced against the LQ45 median because their sector has fewer than 5 eligible peers. 14 are Unclassified. 11 are first blocked on accounting: 5 US-dollar reporters whose latest report is Q1 2026 have no matched quarters, 3 US-dollar reporters' published quarters do not line up with Sectors' conversion, BMRI matches no published line, and 2 have a loss in one of the two quarters, so growth is undefined. 3 are first blocked by a corporate action in the price window. Every member keeps a page with its reasons.

**Earnings basis.** Sectors does not document whether quarterly earnings are standalone or cumulative. Each member was checked against its own published results (`research/published_earnings.csv`, `research/published_converted_earnings.csv`, `scripts/verify_earnings_basis.py`): 36 verified, 4 mismatches, 5 US-dollar reporters unmatched. Rupiah reporters verify when Q1 + Q2 2026 matches the published half-year on earnings, or on earnings less or plus minorities. Sectors converts US-dollar reporters at one rate per quarter (16,231, 16,999 and 17,899 rupiah per dollar for Q2 2025, Q1 2026 and Q2 2026); the 9 whose published dollar quarters match it within 1% have growth measured in dollars.

## Credit usage

The team allocation is 500 Sectors credits. `cache/ledger.jsonl` books every request at its documented maximum, before the outcome is known:

| Outcome | Requests | Credits booked |
| --- | ---: | ---: |
| Successful (HTTP 200) | 268 | 472 |
| Rate-limited (HTTP 429) | 55 | 92 |
| Network error, no response | 4 | 8 |
| Dashboard reconciliation | 1 | -100 |
| **Ledger total** | | **472** |

At 2026-10-06 09:01 UTC the Sectors dashboard showed 350 credits used. That equalled the successful requests up to then, so rate-limited and failed requests are not billed. The ledger was reconciled to that reading (`scripts/reconcile_credits.py`), which removed the 100 credits booked for them. The 97 credits of successful requests booked after it brought the estimate to 447. On 2026-10-08, 25 more credits refetched quarterly financials for the five US-dollar reporters whose latest report was Q1 2026 (AMMN, MBMA, MDKA, MEDC, PGAS). Sectors still returned Q1 2026 as their latest quarter, so nothing changed for them. The estimate is now **472 of 500 used**. The team has since added credits, but the dashboard has not been re-read, so the post-reconciliation figure is an estimate.

## Regenerate

The build is offline. It reads `cache/` and `research/`, and needs no API key.

```bash
python3.14 -m venv .venv
```

```bash
.venv/bin/python scripts/build_snapshot.py
```

This rewrites `dist/`. Recorded states in `research/state_assignments.json` are kept: a state is assigned once per company and report period and never rewritten by a later build.

To check that a clean copy reproduces the published pages with the network blocked and no secrets present:

```bash
.venv/bin/python scripts/check_reproduction.py
```

It copies `sectors/`, `scripts/`, `app/`, `research/` and `cache/` into a temporary folder, strips `SECTORS_*` variables, refuses every socket connection, builds, and compares each page with `dist/` apart from the generation time. On 2026-10-08 it built 94 files with 0 differences.

`cache/` and `dist/` are both listed in `.gitignore`, so a git checkout alone can neither rebuild nor show the pages. `company-state-monitor-submission.zip` carries the committed source plus both folders (the cache holds raw API responses and no key). Extracted on its own, it passed the tests and the reproduction check on 2026-10-08.

### Fetching new data

Live fetching spends credits. Copy `.env.example` to `.env` and set `SECTORS_API_KEY` and `SECTORS_CREDIT_BUDGET`. Always dry-run first:

```bash
.venv/bin/python scripts/probe_roster.py --dry-run
```

Then run without `--dry-run`, rebuild, and reconcile the ledger with a fresh dashboard reading. Changing definitions in `research/candidate_signals.yaml` requires a signal log entry and a new freeze (`scripts/freeze_bands.py`).

## Demo video

`submission/demo.mp4` is a silent walkthrough rendered from the built pages, not from mock-ups. To render it again after a rebuild, serve `dist/` and run the script. It needs Google Chrome and ffmpeg.

```bash
.venv/bin/python -m http.server 8765 --directory dist --bind 127.0.0.1
```

```bash
.venv/bin/python scripts/render_demo.py submission/demo.mp4
```

The shot list is the `SHOTS` table in `scripts/render_demo.py`. A narration script matched to it is in `submission/demo-script.md`.

## Tests

The standard library runs the tests. mypy runs in strict mode.

```bash
.venv/bin/python -m unittest discover
```

```bash
.venv/bin/pip install -r requirements-dev.txt
```

```bash
.venv/bin/mypy
```

## Limits

- Retrospective research using available historical records; original availability and revisions are not fully verified.
- Neutral bands are calibrated across today's members, not on history ([ADR 0003](docs/adr/0003-calibrate-bands-on-the-current-snapshot.md)). No chronological holdout has been evaluated, so every evidence label is Insufficient and no outcome or reference comparison is reported.
- The roster and sectors are today's. Any historical result would describe today's members, not a historical LQ45 portfolio.
- Prices are unadjusted closes. Dividends are not included, and a corporate action blocks the affected window.

The v5 completion criteria are reviewed one by one in [research/validation_report.md](research/validation_report.md). Design decisions are in [docs/adr](docs/adr) and domain terms in [CONTEXT.md](CONTEXT.md).

Research and analysis only. Not investment advice.
