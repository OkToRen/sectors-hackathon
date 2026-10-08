# Package the submission

Status: in-progress

## What to build

Prepare the hackathon submission for the 8 October 2026, 23:59 WIB deadline: a README, a clean reproduction check from cache, a real-output demo video and a final review against the v5 completion criteria.

Source: [Company State Monitor v5](../../../sectors_company_state_monitor_v5.md), "Delivery and cut order" and "Completion criteria".

## Acceptance criteria

- [x] The README covers the universe, sector mapping, dates, snapshot time, actual credit usage including the 429 bookings, manual regeneration and reproduction steps.
- [x] A fresh checkout regenerates the app from cache with no network calls and no secrets.
- [x] Each of the 12 v5 completion criteria is checked off with evidence, or listed as cut with the reason.
- [x] The demo video uses real generated output only.
- [ ] The organizer's submission requirements are checked before submitting. Submitting is the operator's action.

## Blocked by

Ticket 09. If time runs short, follow the v5 cut order: keep accurate inputs, classification, explanation and disclosure, and cut the secondary items first.

Progress 2026-10-06: `README.md`, `scripts/check_reproduction.py` (94 files, 0 differences, sockets blocked, no secrets) and `research/validation_report.md` (12 criteria; 7 and 8 cut, 10 partly met, all for want of a holdout) are written. Still open, all operator actions: record the demo video from `dist/`, decide how `cache/` ships (it is gitignored), check the organizer's submission requirements, and submit before 8 October 23:59 WIB.

Progress 2026-10-08: `submission/demo.mp4` (116 s, 1440x900, silent) is rendered by `scripts/render_demo.py` from headless-Chrome captures of the served `dist/`, with `submission/demo-script.md` as timed narration. Recording it surfaced three page-copy defects, each fixed test-first and rebuilt: the Contradicting note's verb agreement ("Foreign flow now sits"), an empty blockers list on all 31 classified pages (now "None"), and Methodology omitting that 10 states keep the 14:03 UTC first-freeze bands (now counted from the pages). README and the validation report were corrected to the 15:07 UTC freeze; reproduction rebuilt 94 files with 0 differences. `dist/` is also gitignored, not just `cache/`. No organizer rules page was found online. Still open for the operator: narrate or re-record the video, decide how `cache/` and `dist/` ship, check the organizer's requirements, and submit before 8 October 23:59 WIB.


Progress 2026-10-08 (later): local git repository initialised. `company-state-monitor-submission.zip` holds the committed source plus `cache/` and `dist/`. Extracted alone, it passed the tests and the reproduction check (0 differences). No API key appears in any packaged file. Still open, all operator actions: check the organizer's requirements, optionally narrate the video, push to a remote if the organizers want a repository link, and submit before 8 October 23:59 WIB.
