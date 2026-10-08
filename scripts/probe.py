"""Probe one ticker: python scripts/probe.py BBCA --max-credits 10"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sectors.probe import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
