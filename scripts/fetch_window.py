"""Fetch an extra date window of daily prices and/or foreign flow, through the budgeted probe path:
python scripts/fetch_window.py --start 2026-06-01 --end 2026-07-08 --prices all --flow BBCA,ICBP --max-credits 68 [--dry-run]"""

import argparse
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sectors.api import DAILY_PRICES, FOREIGN_FLOW, normalize_symbol, urllib_transport  # noqa: E402
from sectors.env import setting  # noqa: E402
from sectors.probe import PlannedRequest, ProbeLimits, execute  # noqa: E402
from sectors.roster import members  # noqa: E402


def symbols(spec: str, roster: list[str]) -> list[str]:
    return roster if spec == "all" else [normalize_symbol(s) for s in spec.split(",") if s.strip()]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", required=True)
    parser.add_argument("--end", required=True)
    parser.add_argument("--prices", default="", help="'all' or comma-separated tickers")
    parser.add_argument("--flow", default="", help="'all' or comma-separated tickers")
    parser.add_argument("--max-credits", type=int, required=True)
    parser.add_argument("--pause", type=float, default=0.0, help="seconds between live requests")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--cache", type=Path, default=Path("cache"))
    parser.add_argument("--env-file", type=Path, default=Path(".env"))
    args = parser.parse_args()
    roster = members(args.cache) or []
    window = (("start", args.start), ("end", args.end))
    requests = [(s, PlannedRequest(e, e.path.format(symbol=s), window, 1))
                for e, spec in ((DAILY_PRICES, args.prices), (FOREIGN_FLOW, args.flow)) for s in symbols(spec, roster)]
    limits = ProbeLimits(int(setting("SECTORS_CREDIT_BUDGET", args.env_file)), args.max_credits)
    report = execute(requests, args.cache, None if args.dry_run else urllib_transport,
                     setting("SECTORS_API_KEY", args.env_file), limits, pause=args.pause)
    for result in report.results:
        if result.status not in ("reused", "fetched", "planned"):
            print(f"{result.owner:6} {result.endpoint:14} {result.status:12} {result.detail}")
    print(f"{dict(Counter(r.status for r in report.results))}. This run: {report.counted_this_run} credits. "
          f"Ledger total: {report.counted_total} of {report.allocation}, keeping {limits.kept} in reserve.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
