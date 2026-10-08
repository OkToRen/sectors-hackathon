"""Check each roster member's cached quarters against published half-year profits (offline):
python scripts/verify_earnings_basis.py"""

import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sectors.api import QUARTERLY_FINANCIALS  # noqa: E402
from sectors.basis import (assess, assess_converted, common_rates, implied_rates, read_published,  # noqa: E402
                           read_published_converted, write_checks)
from sectors.cache import CaptureStore, is_usable  # noqa: E402
from sectors.roster import members  # noqa: E402


def main() -> int:
    cache, research = Path("cache"), Path("research")
    roster = members(cache)
    if roster is None:
        print("No usable roster capture; run the roster probe first.", file=sys.stderr)
        return 2
    published = read_published(research / "published_earnings.csv")
    converted = read_published_converted(research / "published_converted_earnings.csv")
    store = CaptureStore(cache)
    quarters = {}
    for symbol in roster:
        capture = store.latest(symbol, QUARTERLY_FINANCIALS.name)
        quarters[symbol] = capture["body"] if capture and is_usable(capture) else []
    rates = common_rates([implied for symbol, figures in converted.items() if symbol in quarters
                          and (implied := implied_rates(quarters[symbol], figures)) is not None])
    print("Shared conversion rates:", {period: round(rate) for period, rate in rates.items()})
    checks = []
    for symbol in roster:
        check = assess(symbol, quarters[symbol], published.get(symbol))
        if check.status == "reporting_currency":
            check = assess_converted(symbol, quarters[symbol], converted.get(symbol), rates)
        checks.append(check)
    write_checks(checks, research / "earnings_basis.json")
    for check in checks:
        print(f"{check.symbol:5} {check.status:20} {check.reason}")
    print(dict(Counter(check.status for check in checks)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
