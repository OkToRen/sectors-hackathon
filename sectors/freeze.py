"""The band freeze: bands recorded with the date and a hash of the definitions they were calibrated under."""

import hashlib
import json
import math
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sectors.state import MIN_BAND_VALUES, Band


def _digest(definitions: Path) -> str:
    return hashlib.sha256(definitions.read_bytes()).hexdigest()


def write_freeze(bands: dict[str, Band | None], definitions: Path, path: Path, now: datetime) -> None:
    path.write_text(json.dumps({
        "frozen_at": now.astimezone(UTC).isoformat(timespec="seconds"),
        "definitions": definitions.name, "definitions_sha256": _digest(definitions),
        "bands": {dim: None if b is None else {"half_width": b.half_width, "population": b.population}
                  for dim, b in bands.items()},
    }, indent=2) + "\n")


def load_freeze(path: Path, definitions: Path) -> dict[str, Band | None] | None:
    """None when nothing is frozen. A freeze made under other definitions is refused, not silently reused."""
    if not path.exists():
        return None
    record = json.loads(path.read_text())
    if record["definitions_sha256"] != _digest(definitions):
        raise ValueError(f"{path} was frozen under different definitions; rerun scripts/freeze_bands.py.")
    return {dim: usable_band(b) for dim, b in record["bands"].items()}


def usable_band(stored: dict[str, Any] | None) -> Band | None:
    """A stored band is used only if it could have been calibrated: positive, finite and from enough values."""
    if not isinstance(stored, dict):
        return None
    try:
        half_width, population = float(stored["half_width"]), int(stored["population"])
    except (KeyError, TypeError, ValueError):
        return None
    usable = math.isfinite(half_width) and half_width > 0 and population >= MIN_BAND_VALUES
    return Band(half_width, population) if usable else None
