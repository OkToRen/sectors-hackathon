"""Methodology view: every number comes from the build's own pages, the freeze record and the signal log."""

import csv
import json
from collections import Counter
from collections.abc import Iterable
from datetime import datetime
from html import escape
from pathlib import Path
from typing import Any

from sectors.freeze import usable_band
from sectors.pattern import ALLOWED, TOLERANCE
from sectors.state import STATES

DIMENSION_NAMES = {"fundamentals": "Fundamentals", "price": "Price", "flow": "Foreign flow"}
ALLOWED_WORDS = {"positive": "above the band", "neutral_or_positive": "inside or above the band",
                 "neutral_or_negative": "inside or below the band"}
MIN_EVIDENCE_CASES = 15


def methodology_fields(pages: list[dict[str, Any]], research: Path, freeze_name: str, log_name: str
                       ) -> dict[str, str]:
    freeze_path, log_path = research / freeze_name, research / log_name
    freeze = json.loads(freeze_path.read_text()) if freeze_path.exists() else None
    log = _log(log_path) if log_path.exists() else []
    classified = [p for p in pages if p["state"]]
    basis = Counter((p["basis_check"] or {}).get("status", "not checked") for p in pages)
    return {
        "member_count": str(len(pages)),
        "classified_count": str(len(classified)),
        "unclassified_count": str(len(pages) - len(classified)),
        "roster_reference_count": str(sum(1 for p in pages if p["price_reference"] == "roster")),
        "source_gaps": str(sum(1 for p in pages for b in p["blockers"] if b["topic"] == "Source")),
        "basis_rows": _rows(2, [(status.replace("_", " ").capitalize(), str(n)) for status, n in sorted(basis.items())]),
        "band_rows": _band_rows(freeze),
        "freeze_text": escape(_freeze_text(freeze, classified)),
        "mapping_rows": _rows(4, [(name, " or ".join(sorted(f)), " or ".join(sorted(p)), " or ".join(sorted(fl)))
                               for name, f, p, fl in STATES]),
        "pattern_rows": _rows(3, [(name, ALLOWED_WORDS[a["price"]], ALLOWED_WORDS[a["flow"]])
                               for name, a in ALLOWED.items()]),
        "tolerance": f"{TOLERANCE:g}",
        "min_cases": str(MIN_EVIDENCE_CASES),
        "insufficient_count": str(sum(1 for p in pages if p["evidence_strength"] == "Insufficient")),
        "composition_rows": _counted(p["state"] for p in classified),
        "sector_rows": _counted(p["sector"] or "Unavailable" for p in classified),
        "log_rows": _rows(3, [(row["date"], row["decision"], row["finding"]) for row in log]),
        "log_count": str(len(log)),
    }


def _rows(columns: int, rows: list[tuple[str, ...]]) -> str:
    if not rows:
        return f'<tr><td colspan="{columns}">None recorded.</td></tr>'
    return "".join("<tr>" + "".join(f"<td>{escape(cell)}</td>" for cell in row) + "</tr>" for row in rows)


def _counted(values: Iterable[str]) -> str:
    return _rows(2, [(value, str(n)) for value, n in sorted(Counter(values).items(), key=lambda kv: (-kv[1], kv[0]))])


def _band_rows(freeze: dict[str, Any] | None) -> str:
    if freeze is None:
        return "<li>No bands are frozen.</li>"
    return "".join(f"<li>{escape(DIMENSION_NAMES[dim])} ±{b.half_width:.2%} from {b.population} roster values</li>"
                   if (b := usable_band(stored)) else f"<li>{escape(DIMENSION_NAMES[dim])}: no usable band</li>"
                   for dim, stored in freeze["bands"].items())


def _log(path: Path) -> list[dict[str, str]]:
    """An unquoted comma would silently cut a finding short, so a row with extra fields is refused."""
    with path.open() as handle:
        rows = list(csv.DictReader(handle))
    for line, row in enumerate(rows, start=2):
        if None in row:
            raise ValueError(f"{path.name} line {line} has more fields than its header; quote the finding.")
    return rows


def _freeze_text(freeze: dict[str, Any] | None, classified: list[dict[str, Any]]) -> str:
    if freeze is None:
        return "No freeze is recorded, so no states are published."
    frozen = datetime.fromisoformat(freeze["frozen_at"])
    text = (f"Frozen {frozen:%Y-%m-%d %H:%M} UTC against {freeze['definitions']} "
            f"(SHA-256 {freeze['definitions_sha256'][:12]}).")
    kept = [p for p in classified if any(p["dimensions"][dim]["band"] != freeze["bands"].get(dim)
                                         for dim in DIMENSION_NAMES)]
    if not kept:
        return text
    times = " and ".join(sorted({f"{datetime.fromisoformat(p['assigned_at']):%Y-%m-%d %H:%M}" for p in kept}))
    was = "was" if len(kept) == 1 else "were"
    its = "its" if len(kept) == 1 else "their"
    return (f"{text} {len(kept)} of {len(classified)} states {was} recorded at {times} UTC under an earlier freeze "
            f"and {'keeps' if len(kept) == 1 else 'keep'} {its} bands, because a state is recorded once per report "
            "period and never rewritten. Each Company view shows the bands its state used.")
