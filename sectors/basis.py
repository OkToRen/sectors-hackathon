"""Earnings-basis checks: are a company's Sectors quarters standalone, consolidated and in comparable units?"""

import csv
import json
import math
import statistics
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal

from sectors.numbers import plausible

Status = Literal["verified", "mismatch", "reporting_currency", "no_published_figure", "quarters_missing",
                 "not_checked"]
TOLERANCE = 0.01  # published half-year figures are rounded; cumulative quarters miss by far more
CUMULATIVE_GAP = 0.25
MIN_RATE_REPORTERS = 5
Q2_2025, Q1_2026, Q2_2026 = "2025-06-30", "2026-03-31", "2026-06-30"
QUARTER_NAMES = {Q2_2025: "Q2 2025", Q1_2026: "Q1 2026", Q2_2026: "Q2 2026"}
TN = 10**12
MILLION = 10**6


@dataclass(frozen=True)
class Published:
    reporting_currency: str
    h1_2026_tn: float | None
    h1_2025_tn: float | None
    source: str
    note: str


@dataclass(frozen=True)
class PublishedConverted:
    """Published profit of a company reporting in another currency, in millions of that currency."""
    currency: str
    line: str
    q1_2025: float
    h1_2025: float
    q1_2026: float
    h1_2026: float
    source_q1: str
    source_h1: str
    note: str


@dataclass(frozen=True)
class BasisCheck:
    symbol: str
    status: Status
    earnings: dict[str, int | float] = field(default_factory=dict)
    reason: str = ""
    source: str | None = None
    rates: dict[str, float] = field(default_factory=dict)  # rupiah per reporting-currency unit; empty for IDR


def assess(symbol: str, quarters: list[dict[str, Any]], published: Published | None) -> BasisCheck:
    """Verified when Q1 + Q2 2026 is within 1% of the published H1 2026 profit, Q2 2026 alone is not (so the
    quarters are not cumulative), and Q2 2025 is likewise not the published H1 2025 figure."""
    if published is None:
        return BasisCheck(symbol, "not_checked", reason="This company's published results have not been checked.")
    source = published.source
    if published.reporting_currency != "IDR":
        return BasisCheck(symbol, "reporting_currency", reason=(
            f"Reports in {published.reporting_currency}; Sectors converts to rupiah, so rupiah growth would mix in "
            "exchange-rate moves."), source=source)
    if not source.strip():
        return BasisCheck(symbol, "no_published_figure", reason="No source is recorded for the published figure.")
    # Validated after conversion to rupiah, with the same bound as provider values, so overflow cannot slip through.
    totals = [None if total is None else plausible(total * TN) for total in (published.h1_2026_tn,
                                                                              published.h1_2025_tn)]
    if any(not total for total in totals):
        return BasisCheck(symbol, "no_published_figure", reason="No usable published half-year profit was found.",
                          source=source)
    values = {str(row["date"]): plausible(row.get("earnings")) for row in quarters}
    needed = [values.get(period) for period in (Q2_2025, Q1_2026, Q2_2026)]
    if any(value is None for value in needed):
        return BasisCheck(symbol, "quarters_missing", reason="Q2 2025, Q1 2026 and Q2 2026 earnings are needed.",
                          source=source)
    q2_2025, q1, q2 = (v for v in needed if v is not None)
    h1, h1_prior = (total for total in totals if total)
    line, (l2_2025, l1, l2) = _matching_line(quarters, (q2_2025, q1, q2), h1)
    gap = abs(l1 + l2 - h1) / abs(h1)
    if gap > TOLERANCE:
        return BasisCheck(symbol, "mismatch", reason=(
            f"Q1 + Q2 2026 {line} of IDR {(l1 + l2) / TN:.2f} tn differ from the published H1 2026 profit of "
            f"IDR {h1 / TN:.2f} tn by {gap:.2%}." + (f" Note: {published.note}." if published.note else "")),
            source=source)
    if abs(l2 - h1) / abs(h1) <= CUMULATIVE_GAP or abs(l2_2025 - h1_prior) / abs(h1_prior) <= CUMULATIVE_GAP:
        return BasisCheck(symbol, "mismatch", reason="A Q2 figure is close to its half-year total, so the quarters "
                                                     "may be cumulative.", source=source)
    return BasisCheck(symbol, "verified", {Q2_2025: q2_2025, Q1_2026: q1, Q2_2026: q2}, (
        f"Q1 + Q2 2026 {line} of IDR {(l1 + l2) / TN:.2f} tn are within {gap:.1%} of the published H1 2026 profit "
        f"of IDR {h1 / TN:.2f} tn; Q2 2025 of IDR {q2_2025 / TN:.2f} tn is a standalone quarter "
        f"against a published H1 2025 of IDR {h1_prior / TN:.2f} tn."), source)


def _matching_line(quarters: list[dict[str, Any]], earnings: tuple[float, float, float],
                   h1: float) -> tuple[str, tuple[float, float, float]]:
    """Published profit is either attributable or includes minority interests, and Sectors earnings can be either,
    so the half-year may match earnings with minorities taken out or added back; earnings itself is tried first.
    Growth always uses earnings."""
    by_date = {str(row["date"]): plausible(row.get("minorities")) for row in quarters}
    minorities = [by_date.get(period) for period in (Q2_2025, Q1_2026, Q2_2026)]
    lines = [("earnings", earnings)]
    if all(m is not None for m in minorities):
        m = [float(v) for v in minorities if v is not None]
        lines += [("earnings less minorities", (earnings[0] - m[0], earnings[1] - m[1], earnings[2] - m[2])),
                  ("earnings plus minorities", (earnings[0] + m[0], earnings[1] + m[1], earnings[2] + m[2]))]
    within = [line for line in lines if abs(line[1][1] + line[1][2] - h1) / abs(h1) <= TOLERANCE]
    return within[0] if within else min(lines, key=lambda line: abs(line[1][1] + line[1][2] - h1))


def implied_rates(quarters: list[dict[str, Any]], published: PublishedConverted) -> dict[str, float] | None:
    """Rupiah per reporting-currency unit Sectors used for each standalone quarter: its rupiah earnings over the
    published quarter (Q2 is the half-year less Q1)."""
    standalone = {Q2_2025: published.h1_2025 - published.q1_2025, Q1_2026: published.q1_2026,
                  Q2_2026: published.h1_2026 - published.q1_2026}
    values = {str(row["date"]): plausible(row.get("earnings")) for row in quarters}
    rates = {}
    for period, amount in standalone.items():
        value = values.get(period)
        if value is None or not math.isfinite(amount) or amount == 0:
            return None
        rates[period] = value / (amount * MILLION)
    return rates


def common_rates(implied: list[dict[str, float]]) -> dict[str, float]:
    """Sectors converts every reporter at one rate per quarter; the median of enough reporters estimates it and a
    misreported company cannot move it."""
    by_period: dict[str, list[float]] = {}
    for rates in implied:
        for period, rate in rates.items():
            if math.isfinite(rate) and rate > 0:
                by_period.setdefault(period, []).append(rate)
    return {period: statistics.median(values) for period, values in by_period.items()
            if len(values) >= MIN_RATE_REPORTERS}


def assess_converted(symbol: str, quarters: list[dict[str, Any]], published: PublishedConverted | None,
                     rates: dict[str, float]) -> BasisCheck:
    """Verified when every compared quarter converts at the shared rate: that ties the published standalone
    quarters to Sectors' rupiah quarters, which also rules out cumulative figures."""
    blocked = BasisCheck(symbol, "reporting_currency", reason=(
        "Reports in a currency other than rupiah, and its published quarters have not been matched to Sectors' "
        "conversion, so rupiah growth would mix in exchange-rate moves."))
    if published is None or any(period not in rates for period in QUARTER_NAMES):
        return blocked
    source = published.source_h1
    implied = implied_rates(quarters, published)
    if implied is None:
        return BasisCheck(symbol, "quarters_missing", reason="Q2 2025, Q1 2026 and Q2 2026 earnings are needed.",
                          source=source)
    for period, rate in implied.items():
        gap = abs(rate / rates[period] - 1)
        if gap > TOLERANCE:
            return BasisCheck(symbol, "mismatch", reason=(
                f"Reports in {published.currency}. {QUARTER_NAMES[period]} converts at {rate:,.0f} rupiah per "
                f"{published.currency} against the shared {rates[period]:,.0f} ({gap:.2%} apart), so the published "
                f"{published.currency} quarters and Sectors' rupiah quarters do not line up."), source=source)
    values = {str(row["date"]): plausible(row.get("earnings")) for row in quarters}
    q2_2025, q1, q2 = (f"{implied[p]:,.0f}" for p in QUARTER_NAMES)
    return BasisCheck(symbol, "verified", {p: v for p in QUARTER_NAMES if (v := values[p]) is not None}, (
        f"Reports in {published.currency}. Sectors' rupiah quarters divided by the published {published.currency} "
        f"standalone quarters give {q2_2025}, {q1} and {q2} rupiah per {published.currency} for Q2 2025, Q1 2026 and Q2 2026, each "
        f"within 1% of the rate shared by other {published.currency} reporters, so growth is measured in "
        f"{published.currency} at those rates."), source, {p: rates[p] for p in QUARTER_NAMES})


def read_published_converted(path: Path) -> dict[str, PublishedConverted]:
    with path.open(newline="") as handle:
        return {row["symbol"]: PublishedConverted(row["currency"], row["line"], float(row["q1_2025"]),
                                                  float(row["h1_2025"]), float(row["q1_2026"]),
                                                  float(row["h1_2026"]), row["source_q1"], row["source_h1"],
                                                  row["note"])
                for row in csv.DictReader(handle)}


def read_published(path: Path) -> dict[str, Published]:
    with path.open(newline="") as handle:
        return {row["symbol"]: Published(row["reporting_currency"], _float(row["h1_2026_idr_tn"]),
                                         _float(row["h1_2025_idr_tn"]), row["source"], row["note"])
                for row in csv.DictReader(handle)}


def _float(text: str) -> float | None:
    return float(text) if text.strip() else None


def write_checks(checks: list[BasisCheck], path: Path) -> None:
    path.write_text(json.dumps({check.symbol: asdict(check) for check in checks}, indent=2, sort_keys=True) + "\n")


def load_checks(path: Path) -> dict[str, BasisCheck]:
    """Checks recorded by scripts/verify_earnings_basis.py; a missing file means nothing is verified. Stored
    entries are evidence from outside this run, so a verified entry must still carry a source and plausible values."""
    if not path.exists():
        return {}
    return {symbol: _trusted(BasisCheck(symbol, entry["status"], dict(entry["earnings"]), entry["reason"],
                                        entry["source"], dict(entry.get("rates") or {})))
            for symbol, entry in json.loads(path.read_text()).items()}


def _trusted(check: BasisCheck) -> BasisCheck:
    if check.status != "verified":
        return check
    has_source = isinstance(check.source, str) and bool(check.source.strip())
    values_ok = bool(check.earnings) and all(plausible(value) is not None for value in check.earnings.values())
    rates_ok = not check.rates or (check.rates.keys() == check.earnings.keys() and all(
        isinstance(rate, (int, float)) and math.isfinite(rate) and rate > 0 for rate in check.rates.values()))
    if has_source and values_ok and rates_ok:
        return check
    return BasisCheck(check.symbol, "no_published_figure",
                      reason="A stored verification lacks a source or valid values, so it is not trusted.",
                      source=check.source)
