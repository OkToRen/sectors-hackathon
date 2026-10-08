"""Record provider-measured credit usage in the ledger:
python scripts/reconcile_credits.py --used 350 --at 2026-10-06T05:40:00+00:00 --source "Sectors dashboard" """

import argparse
from datetime import datetime
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sectors.probe import reconcile  # noqa: E402

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--used", type=int, required=True, help="credits the provider reports as used")
    parser.add_argument("--source", required=True, help="where the measurement came from")
    parser.add_argument("--at", type=datetime.fromisoformat, required=True,
                        help="when the measurement was taken, ISO 8601 with a UTC offset")
    parser.add_argument("--cache", type=Path, default=Path("cache"))
    args = parser.parse_args()
    adjustment = reconcile(args.cache, args.used, args.source, args.at)
    print(f"Ledger adjusted by {adjustment} credits so usage up to {args.at.isoformat()} is {args.used}.")
