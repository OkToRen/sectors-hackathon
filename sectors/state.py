"""The descriptive state engine: dimension measures, neutral bands and the v5 state mapping."""

import calendar
import statistics
from dataclasses import dataclass
from datetime import date
from typing import Any, Literal

from sectors.numbers import plausible

PRICE_CLOSES = 61  # a 60-trading-day return needs 61 closes
FLOW_DAYS = 60
MIN_PEERS = 5
MIN_BAND_VALUES = 5
EPSILON = 1e-9  # thresholds are "above"; ratios exactly at them must not round over
MAX_DAILY_MOVE = 0.35  # IDX daily price limits keep ordinary moves inside this; larger means a corporate action
SHARE_TOLERANCE = 1e-6  # float rounding of market cap / close; any real share-count change exceeds it

Category = Literal["positive", "neutral", "negative"]
Reference = Literal["sector", "roster"]
LABELS = {
    "fundamentals": {"positive": "Improving", "neutral": "Flat", "negative": "Weakening"},
    "price": {"positive": "Leading", "neutral": "Flat", "negative": "Lagging"},
    "flow": {"positive": "Accumulating", "neutral": "Neutral", "negative": "Distributing"},
}
# Every condition in a row is required; the rows are mutually exclusive (v5 "Exact state mapping").
STATES = (
    ("Ignored Improvement", {"Improving"}, {"Flat", "Lagging"}, {"Neutral", "Accumulating"}),
    ("Confirmed Strength", {"Improving"}, {"Leading"}, {"Accumulating"}),
    ("Crowded Optimism", {"Weakening"}, {"Leading"}, {"Accumulating"}),
    ("Early Deterioration", {"Weakening"}, {"Flat", "Leading"}, {"Neutral", "Distributing"}),
)


@dataclass(frozen=True)
class Measure:
    value: float | None
    reason: str = ""
    peers: int | None = None
    reference: Reference | None = None


@dataclass(frozen=True)
class Band:
    half_width: float
    population: int


def state_for(fundamentals: str, price: str, flow: str) -> str:
    for name, f, p, fl in STATES:
        if fundamentals in f and price in p and flow in fl:
            return name
    return "Neutral"


def band(values: list[float]) -> Band | None:
    """Half-width is the 25th percentile of absolute values; too few values or a zero band blocks the dimension."""
    magnitudes = [abs(v) for v in values]
    if len(magnitudes) < MIN_BAND_VALUES:
        return None
    half_width = statistics.quantiles(magnitudes, n=4, method="inclusive")[0]
    return Band(half_width, len(magnitudes)) if half_width > 0 else None


def categorize(value: float, b: Band) -> Category:
    """Boundaries are neutral."""
    return "positive" if value > b.half_width else "negative" if value < -b.half_width else "neutral"


def availability_date(period_end: str) -> date:
    """The conservative three-calendar-month proxy (to the month end), used because no disclosure date is
    returned."""
    end = date.fromisoformat(period_end)
    year, month = divmod(end.month - 1 + 3, 12)
    year, month = end.year + year, month + 1
    return date(year, month, calendar.monthrange(year, month)[1])


def next_report_overdue(period_end: str, today: date) -> bool:
    """True once the next quarter's estimated availability date has passed without it."""
    return today > availability_date(availability_date(period_end).isoformat())




def window_dates(calendar: list[str], until: date, length: int) -> list[str]:
    """The last `length` market trading dates on or before `until`."""
    return [day for day in calendar if day <= until.isoformat()][-length:]


def _closes(rows: list[dict[str, Any]]) -> dict[str, float]:
    return {str(r["date"]): float(c) for r in rows if (c := plausible(r.get("close"))) and c > 0}


def corporate_action(rows: list[dict[str, Any]]) -> str | None:
    """The first date the unadjusted price series cannot be trusted. A constant implied share count (market cap /
    close) means no split, consolidation or issue happened, so unadjusted closes are comparable; any share change
    (even on a flat day, which could hide an offsetting consolidation), a missing market cap, or a move beyond IDX
    daily limits fails that check."""
    previous: tuple[float, float] | None = None
    for row in sorted(rows, key=lambda r: str(r["date"])):
        close, cap = plausible(row.get("close")), plausible(row.get("market_cap"))
        if not close or close <= 0:
            continue
        if not cap or cap <= 0:
            return str(row["date"])
        shares = cap / close
        if previous is not None:
            moved = close / previous[0] - 1
            changed = shares / previous[1] - 1
            if abs(moved) > MAX_DAILY_MOVE + EPSILON or abs(changed) > SHARE_TOLERANCE + EPSILON:
                return str(row["date"])
        previous = (close, shares)
    return None


def uncovered(calendar: list[str], until: date, window: list[str]) -> Measure | None:
    """A window touching a year the exchange calendar does not cover cannot be checked for missing days."""
    covered = {int(day[:4]) for day in calendar}
    first = int(window[0][:4]) if window else until.year
    missing = [year for year in range(min(first, until.year), until.year + 1) if year not in covered]
    if missing:
        return Measure(None, f"No IDX holiday list covers {missing[0]}, so its trading days are unknown.")
    return None


def price_measure(subject: list[dict[str, Any]], sector_peers: dict[str, list[dict[str, Any]]],
                  roster_peers: dict[str, list[dict[str, Any]]], until: date, calendar: list[str]) -> Measure:
    """Company 60-day price return less the median return of eligible peers over exactly the same 61 market trading
    dates ending at the availability date. Peers are the sector when at least MIN_PEERS are eligible, else every
    other roster member; `peers` counts the peers used, or the sector's when price is blocked."""
    window = window_dates(calendar, until, PRICE_CLOSES)
    if missing := uncovered(calendar, until, window):
        return missing
    if len(window) < PRICE_CLOSES:
        return Measure(None, f"{len(window)} of {PRICE_CLOSES} trading dates up to {until.isoformat()} were "
                             "returned.")
    own = _closes(subject)
    gap = next((day for day in window if day not in own), None)
    if gap:
        return Measure(None, f"{gap} has no usable close in the {PRICE_CLOSES}-trading-day window.")
    action = corporate_action([r for r in subject if window[0] <= str(r["date"]) <= window[-1]])
    if action:
        return Measure(None, f"A corporate action on {action} breaks the unadjusted price series.")
    reference: Reference = "sector"
    returns = sector = _peer_returns(sector_peers, window)
    if len(sector) < MIN_PEERS:
        reference, returns = "roster", _peer_returns(roster_peers, window)
    if len(returns) < MIN_PEERS:
        return Measure(None, f"{len(sector)} sector peers and {len(returns)} other roster members have usable closes "
                             f"on the same dates; at least {MIN_PEERS} are needed.", len(sector))
    return Measure(own[window[-1]] / own[window[0]] - 1 - statistics.median(returns), "", len(returns), reference)


def _peer_returns(peers: dict[str, list[dict[str, Any]]], window: list[str]) -> list[float]:
    returns = []
    for rows in peers.values():
        theirs = _closes(rows)
        peer_rows = [r for r in rows if window[0] <= str(r["date"]) <= window[-1]]
        if all(day in theirs for day in window) and corporate_action(peer_rows) is None:
            returns.append(theirs[window[-1]] / theirs[window[0]] - 1)
    return returns


def flow_measure(flows: list[dict[str, Any]], prices: list[dict[str, Any]], until: date,
                 calendar: list[str]) -> Measure:
    """Net foreign flow over the 60 market trading dates up to the availability date, over market cap at the
    latest of those dates."""
    window = window_dates(calendar, until, FLOW_DAYS)
    if missing := uncovered(calendar, until, window):
        return missing
    if len(window) < FLOW_DAYS:
        return Measure(None, f"{len(window)} of {FLOW_DAYS} trading dates up to {until.isoformat()} were returned.")
    by_date = {str(r["date"]): plausible(r.get("net_foreign_inflow")) for r in flows}
    gap = next((day for day in window if by_date.get(day) is None), None)
    if gap:
        return Measure(None, f"{gap} has no flow value in the {FLOW_DAYS}-trading-day window.")
    cap = next((plausible(r.get("market_cap")) for r in prices if str(r["date"]) == window[-1]), None)
    if not cap or cap <= 0:
        return Measure(None, f"No market cap at the latest close, {window[-1]}.")
    return Measure(sum(by_date[day] or 0 for day in window) / cap)
