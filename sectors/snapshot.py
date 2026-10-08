"""Generate the dated Company view from cached captures only; makes no network calls."""

import argparse
import sys
from collections import Counter
from collections.abc import Mapping
import json
import shutil
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime, timedelta, timezone
from html import escape
from pathlib import Path
from string import Template
from typing import Any
from urllib.parse import urlencode

from sectors.api import (BASE_URL, COMPANIES, COMPANY_OVERVIEW, DAILY_PRICES, ENDPOINTS, FOREIGN_FLOW, QUARTERLY_FINANCIALS,
                         Endpoint, normalize_symbol)
from sectors.assignments import Assignment, current_for, previous_for, record_assignments
from sectors.basis import BasisCheck, load_checks
from sectors.cache import CaptureStore, is_usable
from sectors.classify import DIMENSIONS, Classification, CompanyInputs, classify_roster, snapshot_measures
from sectors.methodology import methodology_fields
from sectors.pattern import PatternUpdate, pattern_update
from sectors.radar import radar, radar_fields
from sectors.earnings import ComparableEarnings, comparable_earnings, year_earlier
from sectors.exchange import trading_calendar
from sectors.freeze import load_freeze
from sectors.numbers import plausible
from sectors.state import Band, next_report_overdue
from sectors.roster import INDEX, members

WIB = timezone(timedelta(hours=7), "WIB")
PRICE_DAYS_NEEDED = 61  # a 60-trading-day return needs 61 closes
FLOW_DAYS_NEEDED = 60
MIN_SECTOR_PEERS = 5

Row = dict[str, Any]

BASIS_FILE = Path("research/earnings_basis.json")
FREEZE_NAME, DEFINITIONS_NAME = "bands_freeze.json", "candidate_signals.yaml"
ASSIGNMENTS_NAME = "state_assignments.json"
HOLIDAYS_NAME = "idx_holidays_2026.csv"
SIGNAL_LOG_NAME = "signal_log.csv"


@dataclass(frozen=True)
class Source:
    """The newest capture of an endpoint; for date-range endpoints, rows from every usable capture are merged."""
    endpoint: Endpoint
    capture: dict[str, Any] | None
    windows: tuple[dict[str, Any], ...] = ()

    @property
    def ok(self) -> bool:
        return self.capture is not None and is_usable(self.capture)

    @property
    def problem(self) -> str:
        if self.capture is None:
            return f"{self.endpoint.label} not captured"
        reason = self.capture["error"] or f"HTTP {self.capture['status']}"
        return f"{self.endpoint.label} unavailable: {reason}"

    @property
    def params(self) -> dict[str, str]:
        return dict(self.capture["request"]["params"]) if self.capture else {}

    def body(self) -> object:
        return self.capture["body"] if self.ok and self.capture else None

    def rows(self) -> list[Row]:
        by_date: dict[str, Row] = {}
        # Oldest retrieval first, so where windows overlap the newest retrieval wins.
        for body in [window["body"] for window in self.windows] + [self.body()]:
            if isinstance(body, dict):
                body = body.get("data")
            for row in body if isinstance(body, list) else []:
                if isinstance(row, dict) and row.get("date"):
                    by_date[str(row["date"])] = row
        return [by_date[day] for day in sorted(by_date)]


@dataclass(frozen=True)
class Inputs:
    """Everything derived from the four captures, computed once."""
    sources: dict[str, Source]
    quarters: list[Row]
    prices: list[Row]
    flows: list[Row]

    @property
    def flow_missing(self) -> int:
        return sum(_number(row.get("net_foreign_inflow")) is None for row in self.flows)


def build_snapshot(symbol: str, cache_dir: Path, out_dir: Path, template_dir: Path,
                   now: datetime | None = None, checks: Mapping[str, BasisCheck] | None = None) -> dict[str, Any]:
    """One Company view. Peers come from the captured roster when there is one; earnings-basis checks come from
    research/earnings_basis.json unless given."""
    symbol = normalize_symbol(symbol)
    roster = members(cache_dir)
    universe = [symbol, *(other for other in roster or [] if other != symbol)]
    return _build(universe, [symbol], roster is not None, cache_dir, out_dir, template_dir,
                  now or datetime.now(UTC), load_checks(BASIS_FILE) if checks is None else checks)[0]


def build_roster(cache_dir: Path, out_dir: Path, template_dir: Path, now: datetime | None = None,
                 checks: Mapping[str, BasisCheck] | None = None) -> list[dict[str, Any]]:
    """A Company view for every roster member plus the roster index."""
    roster = members(cache_dir)
    if roster is None:
        raise ValueError(f"No usable {INDEX} roster capture; run the roster probe first.")
    now = now or datetime.now(UTC)
    pages = _build(roster, roster, True, cache_dir, out_dir, template_dir, now,
                   load_checks(BASIS_FILE) if checks is None else checks)
    capture = CaptureStore(cache_dir).latest(INDEX, COMPANIES.name)
    sector_dates = sorted(row["retrieved_at"] for page in pages for row in page["coverage"]
                          if row["endpoint"] == COMPANY_OVERVIEW.name and row["retrieved_at"])
    dates = {"roster_retrieved_at": capture["retrieved_at"] if capture else None,
             "sectors_retrieved_from": sector_dates[0] if sector_dates else None,
             "sectors_retrieved_to": sector_dates[-1] if sector_dates else None}
    index = Template((template_dir / "index.html").read_text())
    fields = _index_fields(pages, now, dates)
    (out_dir / "index.html").write_text(index.substitute({**fields, **radar_fields(radar(pages), len(pages))}))
    method = Template((template_dir / "methodology.html").read_text())
    (out_dir / "methodology.html").write_text(method.substitute({
        **fields, **methodology_fields(pages, cache_dir.parent / "research", FREEZE_NAME, SIGNAL_LOG_NAME),
        "flow_days": str(FLOW_DAYS_NEEDED)}))
    (out_dir / "roster.json").write_text(json.dumps(
        {"index": INDEX, "generated_at": now.astimezone(UTC).isoformat(timespec="seconds"), **dates,
         "members": [_index_row(page) for page in pages]}, indent=2) + "\n")
    return pages


def _build(universe: list[str], targets: list[str], with_peers: bool, cache_dir: Path, out_dir: Path,
           template_dir: Path, now: datetime, checks: Mapping[str, BasisCheck]) -> list[dict[str, Any]]:
    sources, inputs = load_inputs(universe, cache_dir, checks)
    frozen = load_freeze(cache_dir.parent / "research" / FREEZE_NAME,
                         cache_dir.parent / "research" / DEFINITIONS_NAME)
    # Only frozen bands may publish states; without a freeze every dimension is left unbanded.
    today = now.astimezone(WIB).date()
    calendar = trading_calendar(cache_dir.parent / "research" / HOLIDAYS_NAME, today)
    roster = classify_roster(inputs, today, frozen or dict.fromkeys(DIMENSIONS), calendar)
    priced = [str(r["date"]) for c in inputs.values() for r in c.prices if str(r["date"]) <= today.isoformat()]
    as_of = date.fromisoformat(max(priced)) if priced else today
    ledger = cache_dir.parent / "research" / ASSIGNMENTS_NAME
    stamp = now.astimezone(UTC).isoformat(timespec="seconds")
    assignments = record_assignments(ledger, [
        Assignment(symbol, period, c.availability_date, c.state, c.labels,
                   {dim: getattr(c, dim).value for dim in DIMENSIONS},
                   {dim: _band(roster.bands[dim]) for dim in DIMENSIONS}, stamp, {"price": c.price.reference})
        for symbol in targets if (c := roster.companies[symbol]).state and c.availability_date
        and (period := inputs[symbol].earnings.latest_period)])
    currents = {symbol: current_for(assignments, symbol, inputs[symbol].earnings.latest_period, today.isoformat())
                for symbol in targets}
    now_measures = snapshot_measures(inputs, as_of, calendar, {
        symbol: reference for symbol, current in currents.items()
        if current and (reference := current.references.get("price"))})
    template = Template((template_dir / "company.html").read_text())
    out_dir.mkdir(parents=True, exist_ok=True)
    pages = []
    for symbol in targets:
        current = currents[symbol]
        previous = previous_for(assignments, symbol, current.period) if current else None
        if current is None:
            update = None
        elif as_of.isoformat() <= current.availability_date:
            update = PatternUpdate(False, None, None, None, "No market data after the assignment yet.")
        else:
            update = pattern_update(current.state, current.values,
                                    {dim: m.value for dim, m in now_measures.get(symbol, {}).items()}, current.bands)
        data = _view_model(symbol, sources[symbol], now, inputs[symbol].earnings, roster.companies[symbol],
                           roster.bands, frozen is not None, with_peers, checks.get(symbol), current, previous)
        data["pattern_update"] = None if update is None else {**asdict(update), "as_of": as_of.isoformat(),
                                                              "since": current.availability_date if current else None}
        data["pattern_text"] = _pattern_text(data["pattern_update"], data["price_reference"])
        (out_dir / f"{symbol}.json").write_text(json.dumps(data, indent=2) + "\n")
        (out_dir / f"{symbol}.html").write_text(template.substitute(_html_fields(data)))
        pages.append(data)
    shutil.copyfile(template_dir / "styles.css", out_dir / "styles.css")
    return pages


def load_inputs(universe: list[str], cache_dir: Path, checks: Mapping[str, BasisCheck]
                ) -> tuple[dict[str, dict[str, Source]], dict[str, CompanyInputs]]:
    """Every member's sources and the classification inputs built from them; the build and the band freeze share
    this so a freeze is calibrated on exactly what the pages show."""
    store = CaptureStore(cache_dir)
    sources = {symbol: {endpoint.name: Source(endpoint, store.latest(symbol, endpoint.name),
                                              tuple(store.usable(symbol, endpoint.name))
                                              if endpoint in (DAILY_PRICES, FOREIGN_FLOW) else ())
                        for endpoint in ENDPOINTS} for symbol in universe}
    inputs = {symbol: CompanyInputs(_text(_overview(found).get("sector")),
                                    comparable_earnings(found[QUARTERLY_FINANCIALS.name].rows(),
                                                        _verified(checks.get(symbol)),
                                                        _rates(checks.get(symbol))),
                                    found[DAILY_PRICES.name].rows(), found[FOREIGN_FLOW.name].rows())
              for symbol, found in sources.items()}
    return sources, inputs


def _overview(sources: dict[str, Source]) -> dict[str, Any]:
    report = sources[COMPANY_OVERVIEW.name].body()
    details = report.get("overview") if isinstance(report, dict) else None
    return details if isinstance(details, dict) else {}


def _text(value: object) -> str | None:
    """Provider text fields; anything else is treated as missing."""
    return value if isinstance(value, str) and value else None


def _number(value: object) -> int | float | None:
    return plausible(value)


def _revenue_growth(quarters: list[Row], period: str | None) -> float | None:
    """Revenue on the same comparable-quarter comparison as the state's earnings, as supporting context only."""
    by_period = {str(q["date"]): _number(q.get("revenue")) for q in quarters}
    latest, prior = (by_period.get(period), by_period.get(year_earlier(period))) if period else (None, None)
    return latest / prior - 1 if latest and prior and latest > 0 and prior > 0 else None


def _verified(check: BasisCheck | None) -> dict[str, int | float]:
    return check.earnings if check is not None and check.status == "verified" else {}


def _rates(check: BasisCheck | None) -> dict[str, float] | None:
    return check.rates if check is not None and check.status == "verified" and check.rates else None


def _band(b: Band | None) -> dict[str, Any] | None:
    return None if b is None else asdict(b)


def _view_model(symbol: str, sources: dict[str, Source], now: datetime, earnings: ComparableEarnings,
                classification: Classification, bands: dict[str, Band | None], frozen: bool, with_roster: bool,
                check: BasisCheck | None, assignment: Assignment | None = None,
                previous: Assignment | None = None) -> dict[str, Any]:
    """The current state is the newest recorded assignment already public, shown as recorded with its own bands. If
    it is for an earlier report than the latest, that dated state is kept and marked stale once its next report is
    overdue."""
    retained = assignment is not None and assignment.period != earnings.latest_period
    report = sources[COMPANY_OVERVIEW.name].body()
    report = report if isinstance(report, dict) else {}
    details = report.get("overview")
    details = details if isinstance(details, dict) else {}
    inputs = Inputs(sources, *(sources[e.name].rows() for e in (QUARTERLY_FINANCIALS, DAILY_PRICES, FOREIGN_FLOW)))
    quarter = inputs.quarters[-1] if inputs.quarters else {}
    price = inputs.prices[-1] if inputs.prices else {}
    flow_values = [_number(row.get("net_foreign_inflow")) for row in inputs.flows]
    return {
        "symbol": symbol,
        "company_name": _text(report.get("company_name")),
        "sector": _text(details.get("sector")),
        "sub_sector": _text(details.get("sub_sector")),
        "listing_date": _text(details.get("listing_date")),
        "generated_at": now.astimezone(UTC).isoformat(timespec="seconds"),
        "data_availability": "Classified" if (assignment or classification).state else "Unclassified",
        "state": assignment.state if assignment else classification.state,
        "assigned_at": assignment.assigned_at if assignment else None,
        "state_period": assignment.period if assignment else None,
        "state_availability_date": assignment.availability_date if assignment else classification.availability_date,
        "stale": assignment is not None and next_report_overdue(assignment.period, now.astimezone(WIB).date()),
        "previous_state": None if previous is None else {"state": previous.state, "period": previous.period,
                                                         "availability_date": previous.availability_date},
        "availability": {"date": classification.availability_date, "estimated": True,
                         "next_report_overdue": classification.overdue},
        "dimensions": {dim: {"value": assignment.values[dim] if assignment else getattr(classification, dim).value,
                             "label": assignment.labels[dim] if assignment else classification.labels[dim],
                             "reason": "" if assignment else getattr(classification, dim).reason,
                             "band": assignment.bands[dim] if assignment else _band(bands[dim])}
                       for dim in DIMENSIONS},
        "price_reference": assignment.references.get("price") if assignment else classification.price.reference,
        "price_peers": classification.price.peers,
        "peer_reference": classification.price.reference,
        "bands_frozen": frozen,
        "evidence_strength": "Insufficient",
        "inputs": {
            "report_periods": [row["date"] for row in inputs.quarters],
            "latest_report_period": quarter.get("date"),
            "latest_earnings": _number(quarter.get("earnings")),
            "latest_revenue": _number(quarter.get("revenue")),
            "latest_close_date": price.get("date"),
            "latest_close": _number(price.get("close")),
            "latest_market_cap": _number(price.get("market_cap")),
            "price_days_returned": len(inputs.prices),
            "flow_days_returned": len(inputs.flows),
            "flow_days_missing_value": inputs.flow_missing,
            "flow_first_date": inputs.flows[0]["date"] if inputs.flows else None,
            "flow_last_date": inputs.flows[-1]["date"] if inputs.flows else None,
            # A sum over missing days would treat them as zero, so it stays unavailable.
            "net_foreign_flow_sum": sum(v for v in flow_values if v is not None)
            if flow_values and None not in flow_values else None,
        },
        "comparable_earnings": asdict(earnings),
        "revenue_growth": _revenue_growth(inputs.quarters, assignment.period if assignment
                                          else earnings.latest_period),
        "earnings_basis": _basis_note(earnings, check),
        "basis_check": None if check is None else {"status": check.status, "reason": check.reason,
                                                   "source": check.source},
        "blockers": _blockers(inputs, earnings, classification if assignment is None or retained else None,
                              with_roster, check),
        "coverage": [row for source in sources.values() for row in _coverage(source)],
        "credits": _credits(sources),
    }


def _blockers(inputs: Inputs, earnings: ComparableEarnings, classification: Classification | None,
              with_roster: bool, check: BasisCheck | None) -> list[dict[str, str]]:
    """Without a classification (the state is recorded), only data-quality blockers are listed."""
    blockers = [{"topic": "Source", "detail": s.problem} for s in inputs.sources.values() if not s.ok]
    if inputs.sources[QUARTERLY_FINANCIALS.name].ok and not inputs.quarters:
        blockers.append({"topic": "Accounting", "detail": "No quarterly report was returned, so comparable-quarter "
                                                          "earnings cannot be checked."})
    if inputs.quarters:
        if not _basis_covers(earnings, check):
            reason = check.reason if check is not None and check.status != "verified" else (
                "The standalone, consolidated earnings basis has not been checked against this company's own "
                "published report for both compared quarters.")
            blockers.append({"topic": "Accounting", "detail": reason})
        if earnings.condition not in ("growth", "basis_unverified"):
            blockers.append({"topic": "Accounting", "detail": _condition_text(earnings)})
    if not inputs.quarters or classification is None:
        return blockers
    if not with_roster:
        blockers.append({"topic": "Peers", "detail": "The roster was not captured, so sector peers are unknown."})
    for dim, topic in (("price", "Price"), ("flow", "Foreign flow")):
        measure = getattr(classification, dim)
        if measure.value is None and (with_roster or dim == "flow"):
            blockers.append({"topic": topic, "detail": measure.reason})
    for dim in DIMENSIONS:
        if getattr(classification, dim).value is not None and classification.labels[dim] is None:
            blockers.append({"topic": "Calibration", "detail": f"There is no usable frozen neutral band for {dim}."})
    return blockers


def _condition_text(earnings: ComparableEarnings) -> str:
    latest, prior = earnings.latest_period, earnings.prior_period
    return {
        "loss_to_profit": f"A loss in {prior} turned to a profit in {latest}; percentage growth is undefined.",
        "profit_to_loss": f"A profit in {prior} turned to a loss in {latest}; percentage growth is undefined.",
        "persistent_loss": f"Losses in both {prior} and {latest}; percentage growth is undefined.",
        "zero_boundary": f"Earnings of exactly zero in {prior} or {latest}; percentage growth is undefined.",
        "earnings_missing": f"Earnings for {prior} or {latest} are missing.",
        "prior_not_returned": f"The prior-year comparable quarter {prior} was not returned.",
        "no_reports": "No quarterly report was returned.",
        "growth": "",
        "basis_unverified": "",
    }[earnings.condition]


def _basis_covers(earnings: ComparableEarnings, basis: BasisCheck | None) -> bool:
    """Both compared quarters are verified periods holding exactly the verified, present values."""
    return basis is not None and basis.status == "verified" and all(
        period in basis.earnings and value is not None and basis.earnings[period] == value
        for period, value in ((earnings.latest_period, earnings.latest), (earnings.prior_period, earnings.prior)))


def _basis_note(earnings: ComparableEarnings, basis: BasisCheck | None) -> str | None:
    return f"{basis.reason} Source: {basis.source}" if basis is not None and _basis_covers(earnings, basis) else None


def _captures(source: Source) -> list[dict[str, Any]]:
    """Every capture behind a source: all merged windows, or the one capture."""
    if source.windows:
        return list(source.windows)
    return [source.capture] if source.capture else []


def _coverage(source: Source) -> list[dict[str, Any]]:
    """One row per contributing capture, so each request and retrieval time stays visible."""
    captures: list[dict[str, Any] | None] = list(_captures(source)) if source.ok else [source.capture]
    rows = []
    for capture in sorted(captures, key=lambda c: str(c["retrieved_at"]) if c else "", reverse=True):
        dated = Source(source.endpoint, capture).rows() if capture else []
        params = dict(capture["request"]["params"]) if capture else {}
        rows.append({
            "source": source.endpoint.label,
            "endpoint": source.endpoint.name,
            "status": capture["status"] if capture else None,
            "problem": None if source.ok else source.problem,
            "records": (len(dated) if source.endpoint is not COMPANY_OVERVIEW else 1) if source.ok else None,
            "requested_start": params.get("start"),
            "requested_end": params.get("end"),
            "first_date": dated[0]["date"] if dated else None,
            "last_date": dated[-1]["date"] if dated else None,
            "retrieved_at": capture["retrieved_at"] if capture else None,
            "request": None if capture is None else
            f"GET {capture['request']['path']}?{urlencode(list(params.items()))}",
        })
    return rows


def _credits(sources: dict[str, Source]) -> dict[str, Any]:
    captures = [c for s in sources.values() for c in _captures(s)]
    documented = [c["documented_credits"] for c in captures]
    return {
        "documented_estimate": sum(int(c) for c in documented if c is not None),
        "undocumented_requests": sum(c is None for c in documented),
        "provider_reported": {c["endpoint"]: c["provider_charge_headers"]
                              for c in captures if c["provider_charge_headers"]},
    }


# HTML rendering

def _idr(value: int | float | None) -> str:
    if value is None:
        return "Unavailable"
    for size, unit in ((1e12, "tn"), (1e9, "bn"), (1e6, "mn")):
        if abs(value) >= size:
            scaled = value / size
            return f"IDR {scaled:,.{2 if abs(scaled) < 100 else 0}f} {unit}"
    return f"IDR {value:,.0f}"


def _raw(value: int | float | None) -> str:
    """Every returned digit, with grouping only."""
    return "unavailable" if value is None else f"{value:,}"


def _card(label: str, metric: str, detail: str, note: str, missing: bool = False) -> str:
    return (f'<article class="reading{" missing" if missing else ""}"><h3>{escape(label)}</h3>'
            f'<p class="figure">{escape(metric)}</p><p class="as-of">{escape(detail)}</p>'
            f'<p class="note">{escape(note)}</p></article>')


def _cards(inputs: dict[str, Any]) -> str:
    period = inputs["latest_report_period"]
    cards = []
    if period:
        cards += [
            _card("Earnings, latest report", _idr(inputs["latest_earnings"]),
                  f"Report period {period} · raw {_raw(inputs['latest_earnings'])}",
                  "Report period date, not a filing date.",
                  inputs["latest_earnings"] is None),
            _card("Revenue, latest report", _idr(inputs["latest_revenue"]),
                  f"Report period {period} · raw {_raw(inputs['latest_revenue'])}",
                  "Supporting context only; it does not enter classification.",
                  inputs["latest_revenue"] is None),
        ]
    else:
        cards.append(_card("Quarterly financials", "Unavailable", "No quarterly record captured",
                           "Missing financials are not treated as zero.", True))
    if inputs["latest_close_date"]:
        close = inputs["latest_close"]
        cards += [
            _card("Latest close", "Unavailable" if close is None else f"IDR {_raw(close)}",
                  f"{inputs['latest_close_date']} · {inputs['price_days_returned']} trading days returned",
                  "Corporate-action adjustment unverified; not a sector-relative return.", close is None),
            _card("Market cap", _idr(inputs["latest_market_cap"]), f"As of {inputs['latest_close_date']} · raw {_raw(inputs['latest_market_cap'])}",
                  "Needed later to normalize foreign flow.", inputs["latest_market_cap"] is None),
        ]
    else:
        cards.append(_card("Daily prices", "Unavailable", "No daily prices captured",
                           "Missing prices are not treated as zero.", True))
    days, missing = inputs["flow_days_returned"], inputs["flow_days_missing_value"]
    if not days:
        cards.append(_card("Net foreign flow", "Unavailable", "No foreign-flow records captured",
                           "Missing flow is not treated as zero.", True))
    elif missing:
        cards.append(_card("Net foreign flow", "Incomplete", f"{missing} of {days} returned days have no value",
                           "No sum is shown because missing days would be counted as zero.", True))
    else:
        cards.append(_card("Net foreign flow", _idr(inputs["net_foreign_flow_sum"]),
                           f"Sum of {days} returned days, {inputs['flow_first_date']} to {inputs['flow_last_date']}"
                           f" · raw {_raw(inputs['net_foreign_flow_sum'])}",
                           "Raw sum; not normalized by market cap or compared with peers."))
    periods = inputs["report_periods"]
    if periods:
        cards.append(_card("Report periods returned", f"{len(periods)} quarters", f"{periods[0]} to {periods[-1]}",
                           "Period-end dates; original disclosure dates are not part of the schema."))
    return "".join(cards)


def _strip(row: dict[str, Any]) -> str:
    """The returned-date span drawn against the requested window."""
    if not (row["requested_start"] and row["requested_end"]):
        return ""
    start, end = date.fromisoformat(row["requested_start"]), date.fromisoformat(row["requested_end"])
    span = ""
    if row["first_date"]:
        total = max((end - start).days, 1)
        first = max(date.fromisoformat(row["first_date"]), start)
        last = min(date.fromisoformat(row["last_date"]), end)
        left, width = 100 * (first - start).days / total, max(100 * (last - first).days / total, 1.5)
        span = f'<span style="left:{left:.1f}%;width:{width:.1f}%"></span>'
    return f'<div class="strip" aria-hidden="true">{span}</div>'


def _utc(stamp: str | None) -> str:
    return stamp[:16].replace("T", " ") if stamp else "—"


def _coverage_row(row: dict[str, Any]) -> str:
    problem = row["problem"]
    state = "Returned" if problem is None else problem.split(": ", 1)[1] if ": " in problem else "Not captured"
    window = (f"{row['requested_start']} to {row['requested_end']}" if row["requested_start"]
              else "Latest available")
    returned = f"{row['first_date']} to {row['last_date']}" if row["first_date"] else "—"
    retrieved = _utc(row["retrieved_at"])
    records = "—" if row["records"] is None else str(row["records"])
    return (f'<tr class="{"ok" if problem is None else "gap"}"><th scope="row">{escape(row["source"])}'
            f'<span class="status-text">{escape(state)}</span></th><td class="num">{escape(records)}</td>'
            f'<td>{escape(window)}</td><td>{escape(returned)}{_strip(row)}</td><td>{escape(retrieved)}</td></tr>')


def _html_fields(data: dict[str, Any]) -> dict[str, str]:
    generated = datetime.fromisoformat(data["generated_at"]).astimezone(WIB)
    credits = data["credits"]
    reported = credits["provider_reported"]
    credit_detail = ((f"Plus {credits['undocumented_requests']} request(s) whose cost is not documented. "
                      if credits["undocumented_requests"] else "")
                     + ("Provider-reported charge headers: " + "; ".join(
                         f"{name}: {headers}" for name, headers in reported.items()) + "."
                        if reported else "No provider-reported charge was returned with these captures, so "
                                         "measured usage remains unverified."))
    meta = [str(part) for part in (data["sector"], data["sub_sector"]) if part] or ["Sector unavailable"]
    if data["listing_date"]:
        meta.append(f"Listed {data['listing_date']}")
    ends = [row["requested_end"] for row in data["coverage"] if row["requested_end"]]
    requests = "".join(
        f'<li><code>{escape(row["request"])}</code><span>{escape(row["source"])}, retrieved '
        f'{escape(_utc(row["retrieved_at"]))} UTC</span></li>' for row in data["coverage"] if row["request"])
    fields = {
        "symbol": data["symbol"],
        "company_name": data["company_name"] or data["symbol"],
        "company_meta": " · ".join(meta),
        "generated_at": f"{generated.day} {generated:%b %Y, %H:%M}",
        "data_through": max(ends) if ends else "unavailable",
        "credit_figure": str(credits["documented_estimate"]),
        "credit_detail": credit_detail,
        "base_url": BASE_URL,
        "blocker_count": str(len(data["blockers"])),
    }
    escaped = {name: escape(value) for name, value in fields.items()}
    return escaped | {
        "input_cards": _cards(data["inputs"]),
        **_earnings_fields(data),
        **_state_fields(data),
        **_peer_fields(data),
        "blockers": "".join(f'<li><strong>{escape(b["topic"])}</strong><span>{escape(b["detail"])}</span></li>'
                            for b in data["blockers"]) or (
            "<li><strong>None</strong><span>Every input classification needs was available and passed its "
            "checks.</span></li>"),
        "coverage_rows": "".join(_coverage_row(row) for row in data["coverage"]),
        "requests": requests or "<li>No captures.</li>",
    }


def _earnings_fields(data: dict[str, Any]) -> dict[str, str]:
    earnings = data["comparable_earnings"]
    growth = earnings["condition"] == "growth"
    detail = (f"{earnings['latest_period']} · raw {_raw(earnings['latest'])} against {earnings['prior_period']} · "
              f"raw {_raw(earnings['prior'])}" if earnings["latest_period"] else "No quarterly record captured")
    basis = data["earnings_basis"] or ("Basis not yet checked against this company's own published report, so "
                                       "it stays a classification blocker.")
    return {
        "earnings_label": "Growth" if growth else "Not computed",
        "earnings_figure": escape(f"{earnings['growth']:+.1%}" if growth else EARNINGS_LABELS[earnings["condition"]]),
        "earnings_detail": escape(detail),
        "earnings_basis": escape(f"Basis: {basis}" if data["earnings_basis"] else basis),
        "earnings_missing": "" if growth else " missing",
    }


DIMENSION_TITLES = {"fundamentals": "Fundamentals", "price": "Price vs {reference}", "flow": "Foreign flow"}
DIMENSION_UNITS = {"fundamentals": "comparable-quarter earnings growth",
                   "price": "60-day price return less the {reference} median",
                   "flow": "60-day net foreign flow over market cap"}
REFERENCE_NAMES = {"sector": "sector", "roster": INDEX, None: "sector"}


def _state_fields(data: dict[str, Any]) -> dict[str, str]:
    availability = data["availability"]
    when = (f"Latest report {data['inputs']['latest_report_period']}, estimated public "
            f"{availability['date']}." if availability["date"] else "No quarterly report was returned.")
    overdue = " The next report is overdue on that estimated schedule." if availability["next_report_overdue"] else ""
    if data["state"] and data["state_period"] != data["inputs"]["latest_report_period"]:
        stale = " It is stale: the next report is overdue without usable inputs." if data["stale"] else ""
        why = (f"Kept from the {data['state_period']} report (estimated public {data['state_availability_date']}), "
               f"because the latest report cannot be classified yet.{stale}")
    elif data["state"]:
        why = f"Assigned at the estimated availability date. {when}{overdue}"
    else:
        why = f"{len(data['blockers'])} requirements below are not yet met, so no state is assigned. {when}{overdue}"
    cards = []
    reference = REFERENCE_NAMES[data["price_reference"]]
    for dim, title in DIMENSION_TITLES.items():
        title, d = title.format(reference=reference), data["dimensions"][dim]
        band = d["band"]
        band_text = (f"Neutral band ±{band['half_width']:.2%} from {band['population']} roster values"
                     if band else "No neutral band")
        if d["value"] is None:
            cards.append(_card(title, "Unavailable", d["reason"], band_text, True))
        else:
            cards.append(_card(title, d["label"] or "Unbanded",
                               f"{d['value']:+.2%} {DIMENSION_UNITS[dim].format(reference=reference)}",
                               band_text, d["label"] is None))
    return {
        "state_value": escape(data["state"] or "Unclassified"),
        "state_class": "" if data["state"] else " hold",
        "state_why": escape(why),
        "dimensions_intro": escape(f"Measured at the estimated availability date, {data['state_availability_date']}, "
                                   "with bands calibrated across the LQ45 members of that snapshot."
                                   if data["state_availability_date"] else
                                   "No availability date can be estimated without a quarterly report."),
        "dimension_cards": "".join(cards),
        "changes": "".join(f"<li>{escape(text)}</li>" for text in _changes(data)) or
        "<li>No dimension could be measured, so nothing is described.</li>",
        "previous_state": escape(_previous_text(data["previous_state"])),
        "pattern_update": escape(data.get("pattern_text") or ""),
    }


def _changes(data: dict[str, Any]) -> list[str]:
    """Up to three plain-language changes, each from a measured dimension, plus a supporting or contradicting
    revenue comparison."""
    dims, earnings = data["dimensions"], data["comparable_earnings"]
    lines = []
    if dims["fundamentals"]["value"] is not None:
        period = data["state_period"] or earnings["latest_period"]
        lines.append(f"Earnings {dims['fundamentals']['value']:+.1%} against the same quarter a year earlier "
                     f"({period} vs {year_earlier(period)}).")
        revenue = data["revenue_growth"]
        if revenue is not None:
            agrees = (revenue > 0) == (dims["fundamentals"]["value"] > 0)
            lines[-1] += (f" Revenue {revenue:+.1%} on the same comparison, which "
                          f"{'supports' if agrees else 'contradicts'} the earnings direction.")
    if dims["price"]["value"] is not None:
        value = dims["price"]["value"]
        lines.append(f"Price {'beat' if value > 0 else 'trailed'} the {REFERENCE_NAMES[data['price_reference']]} "
                     f"median by {abs(value):.1%} over the "
                     f"60 trading days to {data['state_availability_date']}.")
    if dims["flow"]["value"] is not None:
        value = dims["flow"]["value"]
        lines.append(f"Foreign investors were net {'buyers' if value > 0 else 'sellers'} of {abs(value):.2%} of "
                     "market cap over the same 60 trading days.")
    return lines[:3]


def _pattern_text(update: dict[str, Any] | None, reference: str | None) -> str:
    if update is None:
        return "Pattern Update: none, because no state is assigned."
    if not update["available"]:
        return f"Pattern Update since {update['since']}: unavailable. {update['note']}"
    against = INDEX if reference == "roster" else "the sector"
    changes = (f"Since then price relative to {against} moved {update['price_change'] * 100:+.1f} percentage points "
               f"and foreign flow {update['flow_change'] * 100:+.3f} points of market cap, to {update['as_of']}.")
    label = f"{update['label']}. " if update["label"] else ""
    note = f" {update['note']}" if update["note"] else ""
    return f"Pattern Update since {update['since']}: {label}{changes}{note}"


def _previous_text(previous: dict[str, Any] | None) -> str:
    if previous is None:
        return "Previous state: unavailable; no earlier quarter has a recorded state."
    return (f"Previous state: {previous['state']}, for the {previous['period']} report (estimated public "
            f"{previous['availability_date']}).")


def _peer_fields(data: dict[str, Any]) -> dict[str, str]:
    peers, reference, sector = data["price_peers"], data["peer_reference"], data["sector"]
    if reference is None:
        reason = data["dimensions"]["price"]["reason"] or "No price window was measured."
        return {"peers_title": "Sector peers", "peers_figure": "Unavailable" if peers is None else str(peers),
                "peers_detail": escape(reason), "peers_missing": " missing"}
    detail = (f"of at least {MIN_SECTOR_PEERS} {sector or 'sector'} roster members needed" if reference == "sector"
              else f"other {INDEX} members, because {sector or 'the sector'} has fewer than {MIN_SECTOR_PEERS} "
                   "eligible sector peers")
    return {"peers_title": "Sector peers" if reference == "sector" else f"{INDEX} peers", "peers_figure": str(peers),
            "peers_detail": escape(detail), "peers_missing": ""}


def _index_row(page: dict[str, Any]) -> dict[str, Any]:
    return {"symbol": page["symbol"], "company_name": page["company_name"], "sector": page["sector"],
            "data_availability": page["data_availability"], "state": page["state"],
            "availability": page["availability"], "stale": page["stale"], "state_period": page["state_period"],
            "ranked": page["state"] is not None and not page["stale"],
            "earnings": page["comparable_earnings"],
            "eligible_peers": page["price_peers"], "peer_reference": page["peer_reference"],
            "blockers": len(page["blockers"]),
            "source_problems": sum(1 for b in page["blockers"] if b["topic"] == "Source")}


EARNINGS_LABELS = {
    "loss_to_profit": "Loss to profit", "profit_to_loss": "Profit to loss", "persistent_loss": "Persistent loss",
    "zero_boundary": "Zero earnings", "earnings_missing": "Earnings missing",
    "prior_not_returned": "Prior year not returned", "no_reports": "No reports",
    "basis_unverified": "Basis unverified",
}


def _earnings_label(earnings: dict[str, Any]) -> str:
    if earnings["condition"] == "growth":
        return f"{earnings['growth']:+.1%} vs {earnings['prior_period']}"
    return EARNINGS_LABELS[earnings["condition"]]


def _status_note(row: dict[str, Any]) -> str:
    overdue = (f" · stale, kept from the {row['state_period']} report" if row["stale"] else
               " · next report overdue (estimated)" if row["availability"]["next_report_overdue"] else "")
    blockers = f"{row['blockers']} blockers" if row["blockers"] else "all inputs met"
    return escape(blockers + overdue)


def _index_fields(pages: list[dict[str, Any]], now: datetime, dates: dict[str, str | None]) -> dict[str, str]:
    generated = now.astimezone(WIB)
    rows = []
    for page in sorted(pages, key=lambda p: (p["sector"] or "~", p["symbol"])):
        row = _index_row(page)
        peers = ("unknown" if row["eligible_peers"] is None else f"{row['eligible_peers']} {INDEX}"
                 if row["peer_reference"] == "roster" else str(row["eligible_peers"]))
        problems = f' · {row["source_problems"]} source(s) unavailable' if row["source_problems"] else ""
        rows.append(
            f'<tr><th scope="row"><a href="{escape(row["symbol"])}.html">{escape(row["symbol"])}</a></th>'
            f'<td>{escape(row["company_name"] or "Name unavailable")}</td>'
            f'<td>{escape(row["sector"] or "Unavailable")}</td>'
            f'<td>{escape(_earnings_label(row["earnings"]))}</td><td>{escape(peers)}</td>'
            f'<td>{escape(row["state"] or "Unclassified")}<span class="sub">{_status_note(row)}{escape(problems)}'
            f'</span></td></tr>')
    sectors = Counter(page["sector"] or "Unavailable" for page in pages)
    return {
        "index": INDEX,
        "generated_at": escape(f"{generated.day} {generated:%b %Y, %H:%M}"),
        "member_count": str(len(pages)),
        "sector_count": str(len(sectors)),
        "min_peers": str(MIN_SECTOR_PEERS),
        "price_days": str(PRICE_DAYS_NEEDED),
        "rows": "".join(rows),
        "dates": escape(f"Roster captured {_utc(dates['roster_retrieved_at'])} UTC · sectors from company overviews "
                        f"retrieved {_span(dates['sectors_retrieved_from'], dates['sectors_retrieved_to'])}"),
    }


def _span(start: str | None, end: str | None) -> str:
    if start is None or end is None:
        return "unavailable"
    first, last = _utc(start), _utc(end)
    return f"{first} UTC" if first == last else f"{first} to {last} UTC"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate Company views from cached captures (offline). "
                                                 "Without a symbol, builds every roster member and the index.")
    parser.add_argument("symbol", nargs="?")
    parser.add_argument("--cache", type=Path, default=Path("cache"))
    parser.add_argument("--out", type=Path, default=Path("dist"))
    parser.add_argument("--templates", type=Path, default=Path("app"))
    args = parser.parse_args(argv)
    if args.symbol:
        data = build_snapshot(args.symbol, args.cache, args.out, args.templates)
        print(f"Wrote {args.out / (data['symbol'] + '.html')} ({data['data_availability']}).")
        return 0
    try:
        pages = build_roster(args.cache, args.out, args.templates)
    except ValueError as error:
        print(error, file=sys.stderr)
        return 2
    print(f"Wrote {args.out / 'index.html'} and {len(pages)} Company views.")
    return 0
