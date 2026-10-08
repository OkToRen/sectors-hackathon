"""Calibrate the neutral bands across the cached roster and freeze them with the definitions' hash (offline):
python scripts/freeze_bands.py"""

import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sectors.basis import load_checks  # noqa: E402
from sectors.classify import calibrate, roster_measures  # noqa: E402
from sectors.freeze import write_freeze  # noqa: E402
from sectors.roster import members  # noqa: E402
from sectors.exchange import trading_calendar  # noqa: E402
from sectors.snapshot import BASIS_FILE, DEFINITIONS_NAME, FREEZE_NAME, HOLIDAYS_NAME, WIB, load_inputs  # noqa: E402

if __name__ == "__main__":
    cache, research = Path("cache"), Path("research")
    roster = members(cache)
    if roster is None:
        raise SystemExit("No usable roster capture; run the roster probe first.")
    _, inputs = load_inputs(roster, cache, load_checks(BASIS_FILE))
    today = datetime.now(UTC).astimezone(WIB).date()
    bands = calibrate(roster_measures(inputs, today, trading_calendar(research / HOLIDAYS_NAME, today)))
    write_freeze(bands, research / DEFINITIONS_NAME, research / FREEZE_NAME, datetime.now(UTC))
    for dim, b in bands.items():
        print(f"{dim:13} " + ("no band" if b is None else f"±{b.half_width:.4%} from {b.population} values"))
