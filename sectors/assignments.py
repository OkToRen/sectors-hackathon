"""Recorded state assignments: a state is assigned once per company and report period and then kept, so later
builds and data revisions cannot rewrite it."""

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from sectors.freeze import usable_band
from sectors.state import Reference

REFERENCES: dict[str, Reference] = {"sector": "sector", "roster": "roster"}


@dataclass(frozen=True)
class Assignment:
    symbol: str
    period: str
    availability_date: str
    state: str
    labels: dict[str, str | None]
    values: dict[str, float | None]
    bands: dict[str, dict[str, float] | None]
    assigned_at: str
    references: dict[str, Reference | None]


def load_assignments(path: Path) -> list[Assignment]:
    """Stored bands and references are parsed at this boundary: each band is usable or None, never a malformed
    record. Entries recorded before references existed were all sector-relative."""
    if not path.exists():
        return []
    assignments = []
    for entry in json.loads(path.read_text()):
        bands = {dim: (None if (b := usable_band(stored)) is None else {"half_width": b.half_width,
                                                                        "population": b.population})
                 for dim, stored in entry["bands"].items()}
        references = {dim: REFERENCES.get(stored)
                      for dim, stored in entry.get("references", {"price": "sector"}).items()}
        assignments.append(Assignment(**{**entry, "bands": bands, "references": references}))
    return assignments


def record_assignments(path: Path, new: list[Assignment]) -> list[Assignment]:
    """Append assignments for company-periods not yet recorded; existing ones are kept as they were."""
    existing = load_assignments(path)
    keys = {(a.symbol, a.period) for a in existing}
    added = [a for a in new if (a.symbol, a.period) not in keys]
    if added:
        path.parent.mkdir(parents=True, exist_ok=True)
        records = sorted(existing + added, key=lambda a: (a.symbol, a.period))
        path.write_text(json.dumps([asdict(a) for a in records], indent=2) + "\n")
    return existing + added if added else existing


def current_for(assignments: list[Assignment], symbol: str, latest_period: str | None,
                today: str) -> Assignment | None:
    """The newest recorded state already public on `today` and not newer than the latest report."""
    usable = [a for a in assignments if a.symbol == symbol and a.availability_date <= today
              and (latest_period is None or a.period <= latest_period)]
    return max(usable, key=lambda a: a.period, default=None)


def previous_for(assignments: list[Assignment], symbol: str, period: str) -> Assignment | None:
    earlier = [a for a in assignments if a.symbol == symbol and a.period < period]
    return max(earlier, key=lambda a: a.period, default=None)
