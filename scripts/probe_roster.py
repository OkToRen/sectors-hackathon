"""Probe the LQ45 roster: python scripts/probe_roster.py --max-credits 360 [--dry-run]"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sectors.roster import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
