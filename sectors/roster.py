"""The current LQ45 roster, captured through the same budgeted probe path, then probed member by member."""

import argparse
import sys
from collections import Counter
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from sectors.api import COMPANIES, Transport, normalize_symbol, urllib_transport
from sectors.cache import CaptureStore, is_usable
from sectors.env import setting
from sectors.probe import WIB, PlannedRequest, ProbeLimits, ProbeReport, execute, plan

INDEX = "LQ45"


def roster_request() -> tuple[str, PlannedRequest]:
    params = (("where", f"indices in ['{INDEX}']"), ("limit", "200"))
    return INDEX, PlannedRequest(COMPANIES, COMPANIES.path, params, 1)


def members(cache_dir: Path) -> list[str] | None:
    """Symbols from the newest usable roster capture, or None when no roster has been captured."""
    capture = CaptureStore(cache_dir).latest(INDEX, COMPANIES.name)
    if capture is None or not is_usable(capture):
        return None
    return sorted(normalize_symbol(row["symbol"]) for row in capture["body"]["results"])


def run_roster(cache_dir: Path, transport: Transport | None, api_key: str, limits: ProbeLimits,
               clock: Callable[[], datetime] = lambda: datetime.now(UTC)) -> ProbeReport:
    """Without a transport this is a dry run: it reports what would be reused, fetched or skipped."""
    first = execute([roster_request()], cache_dir, transport, api_key, limits, clock)
    symbols = members(cache_dir)
    if symbols is None:
        return first
    today = clock().astimezone(WIB).date()
    rest = execute([(symbol, request) for symbol in symbols for request in plan(symbol, today)],
                   cache_dir, transport, api_key, limits, clock, earlier=first)
    return ProbeReport(first.results + rest.results, rest.counted_this_run, rest.counted_total, limits.allocation,
                       rest.planned_unrecorded, rest.rate_limited)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=f"Capture the {INDEX} roster, then probe every member.")
    parser.add_argument("--max-credits", type=int, required=True, help="per-run credit cap")
    parser.add_argument("--dry-run", action="store_true", help="report decisions and costs without any request")
    parser.add_argument("--cache", type=Path, default=Path("cache"))
    parser.add_argument("--env-file", type=Path, default=Path(".env"))
    args = parser.parse_args(argv)
    allocation = setting("SECTORS_CREDIT_BUDGET", args.env_file)
    if not allocation.isdigit():
        print("Set SECTORS_CREDIT_BUDGET to the confirmed team allocation before probing.", file=sys.stderr)
        return 2
    try:
        limits = ProbeLimits(int(allocation), args.max_credits)
        report = run_roster(args.cache, None if args.dry_run else urllib_transport,
                            setting("SECTORS_API_KEY", args.env_file), limits)
    except ValueError as error:
        print(error, file=sys.stderr)
        return 2
    for result in report.results:
        print(f"{result.owner:6} {result.endpoint:22} {result.status:12} {result.detail}")
    counts = Counter(result.status for result in report.results)
    verb = "Planned" if args.dry_run else "Counted"
    print(f"{dict(counts)}. {verb} this run: {report.counted_this_run} credits. Ledger total"
          f"{' after this plan' if args.dry_run else ''}: {report.counted_total} of {report.allocation}, "
          f"keeping {limits.kept} in reserve.")
    return 0
