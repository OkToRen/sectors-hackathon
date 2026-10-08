"""Build the views offline from cache: python scripts/build_snapshot.py [SYMBOL]"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sectors.snapshot import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
