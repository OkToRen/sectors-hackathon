"""Radar: recent state transitions, newest observation first (v5 "Three product views")."""

from dataclasses import dataclass
from html import escape
from typing import Any

# Larger departures from the assigned pattern come first; this is a research cue, not a ranking of companies.
PATTERN_ORDER = {"Contradicting": 0, "Weakening": 1, "Mixed": 2, "Strengthening": 3, "Stable": 4}


@dataclass(frozen=True)
class RadarRow:
    symbol: str
    company_name: str | None
    sector: str | None
    state: str
    previous_state: str | None
    observed: str
    estimated: bool
    pattern_available: bool
    pattern_label: str | None


@dataclass(frozen=True)
class Radar:
    ranked: list[RadarRow]
    stale: list[str]
    unclassified: dict[str, list[str]]


def radar(pages: list[dict[str, Any]]) -> Radar:
    ranked: list[RadarRow] = []
    stale: list[str] = []
    unclassified: dict[str, list[str]] = {}
    for page in sorted(pages, key=lambda p: p["symbol"]):
        if page["state"] is None:
            reason = page["blockers"][0]["topic"] if page["blockers"] else "No state assigned"
            unclassified.setdefault(reason, []).append(page["symbol"])
        elif page["stale"]:
            stale.append(page["symbol"])
        else:
            update, previous = page["pattern_update"] or {}, page["previous_state"]
            ranked.append(RadarRow(page["symbol"], page["company_name"], page["sector"], page["state"],
                                   previous["state"] if previous else None, page["state_availability_date"],
                                   page["availability"]["estimated"], bool(update.get("available")),
                                   update.get("label")))
    # Sort is stable over the ticker order above, so ties fall back to the ticker.
    ranked.sort(key=lambda r: PATTERN_ORDER.get(r.pattern_label or "", len(PATTERN_ORDER)))
    ranked.sort(key=lambda r: r.observed, reverse=True)
    return Radar(ranked, stale, dict(sorted(unclassified.items())))


def radar_fields(result: Radar, member_count: int) -> dict[str, str]:
    rows = []
    for row in result.ranked:
        before = row.previous_state or "First recorded state"
        cue = (row.pattern_label or "raw changes only") if row.pattern_available else "Pattern Update unavailable"
        observed = f"Public {row.observed}" + (" (estimated)" if row.estimated else "")
        rows.append(f'<li><a href="{escape(row.symbol)}.html"><strong>{escape(row.symbol)}</strong> '
                    f'<span>{escape(row.state)}</span></a>'
                    f'<span class="sub">{escape(before if row.previous_state is None else "from " + before)}</span>'
                    f'<span class="sub">{escape(observed)} · {escape(cue)}</span></li>')
    excluded = []
    if result.stale:
        excluded.append(f"<li>Stale, {len(result.stale)}: next report overdue, estimated ({escape(', '.join(result.stale))})</li>")
    for reason, symbols in result.unclassified.items():
        excluded.append(f"<li>Unclassified, {len(symbols)}: {escape(reason)} ({escape(', '.join(symbols))})</li>")
    return {
        "radar_count": f"{len(result.ranked)} of {member_count} members ranked",
        "radar_rows": "".join(rows) or "<li>No member has a current, fresh Company State.</li>",
        "radar_excluded": "".join(excluded) or "<li>None excluded.</li>",
    }
