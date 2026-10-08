"""Classify every roster member's latest quarter with neutral bands calibrated across the roster (ADR 0003)."""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from typing import Any

from sectors.earnings import ComparableEarnings
from sectors.state import (LABELS, Band, Measure, Reference, availability_date, band, categorize, flow_measure,
                           next_report_overdue, price_measure, state_for)

DIMENSIONS = ("fundamentals", "price", "flow")


@dataclass(frozen=True)
class CompanyInputs:
    sector: str | None
    earnings: ComparableEarnings
    prices: list[dict[str, Any]]
    flows: list[dict[str, Any]]


@dataclass(frozen=True)
class Classification:
    availability_date: str | None
    overdue: bool
    fundamentals: Measure
    price: Measure
    flow: Measure
    labels: dict[str, str | None]
    state: str | None
    reasons: list[str]


@dataclass(frozen=True)
class RosterClassification:
    bands: dict[str, Band | None]
    companies: dict[str, Classification]


def classify_roster(roster: dict[str, CompanyInputs], today: date, frozen: Mapping[str, Band | None] | None = None,
                    calendar: list[str] | None = None) -> RosterClassification:
    """Frozen bands are used as given; without them the bands are calibrated across this roster. Windows follow the
    exchange calendar, so a trading day missing from the data blocks instead of being skipped."""
    measures = roster_measures(roster, today, calendar or [])
    bands = dict(frozen) if frozen is not None else calibrate(measures)
    return RosterClassification(bands, {symbol: _classify(roster[symbol], measures[symbol], bands, today)
                                        for symbol in roster})


def calibrate(measures: dict[str, dict[str, Measure]]) -> dict[str, Band | None]:
    return {dim: band([v for m in measures.values() if (v := m[dim].value) is not None]) for dim in DIMENSIONS}


def roster_measures(roster: dict[str, CompanyInputs], today: date,
                    calendar: list[str]) -> dict[str, dict[str, Measure]]:
    """Measures at each latest report's availability date, on the exchange trading calendar."""
    return {symbol: _measures(symbol, company, roster, calendar, today) for symbol, company in roster.items()}


def snapshot_measures(roster: dict[str, CompanyInputs], as_of: date, calendar: list[str],
                      references: Mapping[str, Reference]) -> dict[str, dict[str, Measure]]:
    """Price and flow over the 60 trading days ending at the snapshot date for each assigned member, for Pattern
    Update. Price uses only the reference recorded at assignment, so the change compares like with like."""
    measures = {}
    for symbol, reference in references.items():
        company = roster[symbol]
        sector, others = _peers(symbol, roster)
        pinned = (sector, {}) if reference == "sector" else ({}, others)
        measures[symbol] = {"price": price_measure(company.prices, *pinned, as_of, calendar),
                            "flow": flow_measure(company.flows, company.prices, as_of, calendar)}
    return measures


def _peers(symbol: str, roster: dict[str, CompanyInputs]
           ) -> tuple[dict[str, list[dict[str, Any]]], dict[str, list[dict[str, Any]]]]:
    """Sector peers, and every other roster member for when the sector has too few eligible ones."""
    sector = roster[symbol].sector
    others = {other: c.prices for other, c in roster.items() if other != symbol}
    return {other: prices for other, prices in others.items()
            if sector is not None and roster[other].sector == sector}, others


def _measures(symbol: str, company: CompanyInputs, roster: dict[str, CompanyInputs], calendar: list[str],
              today: date) -> dict[str, Measure]:
    period = company.earnings.latest_period
    if period is None:
        missing = Measure(None, "No quarterly report was returned, so there is no availability date.")
        return {dim: missing for dim in DIMENSIONS}
    until = availability_date(period)
    if until > today:
        pending = Measure(None, f"The {period} report is not yet available on its estimated date, {until}.")
        return {dim: pending for dim in DIMENSIONS}
    fundamentals = Measure(company.earnings.growth) if company.earnings.condition == "growth" else Measure(
        None, "Comparable-quarter earnings growth is not available.")
    return {"fundamentals": fundamentals, "price": price_measure(company.prices, *_peers(symbol, roster), until,
                                                                calendar),
            "flow": flow_measure(company.flows, company.prices, until, calendar)}


def _classify(company: CompanyInputs, measures: dict[str, Measure], bands: dict[str, Band | None],
              today: date) -> Classification:
    labels: dict[str, str | None] = {}
    reasons = []
    for dim in DIMENSIONS:
        measure, b = measures[dim], bands[dim]
        if measure.value is None:
            labels[dim] = None
            reasons.append(f"{dim.capitalize()}: {measure.reason}")
        elif b is None:
            labels[dim] = None
            reasons.append(f"{dim.capitalize()}: no usable frozen neutral band.")
        else:
            labels[dim] = LABELS[dim][categorize(measure.value, b)]
    f, p, fl = labels["fundamentals"], labels["price"], labels["flow"]
    state = state_for(f, p, fl) if f and p and fl else None
    period = company.earnings.latest_period
    return Classification(availability_date(period).isoformat() if period else None,
                          period is not None and next_report_overdue(period, today),
                          measures["fundamentals"], measures["price"], measures["flow"], labels, state, reasons)
