"""Comparable-quarter earnings: the latest quarter against the same quarter a year earlier."""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from typing import Any, Literal

from sectors.numbers import plausible

Condition = Literal["growth", "basis_unverified", "loss_to_profit", "profit_to_loss", "persistent_loss", "zero_boundary",
                    "earnings_missing", "prior_not_returned", "no_reports"]


@dataclass(frozen=True)
class ComparableEarnings:
    condition: Condition
    latest_period: str | None
    prior_period: str | None
    latest: int | float | None
    prior: int | float | None
    growth: float | None


def year_earlier(iso: str) -> str:
    day = date.fromisoformat(iso)
    return (day.replace(year=day.year - 1, day=28) if (day.month, day.day) == (2, 29)
            else day.replace(year=day.year - 1)).isoformat()


def comparable_earnings(quarters: list[dict[str, Any]], verified: Mapping[str, int | float],
                        rates: Mapping[str, float] | None = None) -> ComparableEarnings:
    """Growth is defined only when both quarters are positive and both carry exactly the earnings verified as
    standalone for that period; every other case is named, never computed. With conversion rates, Sectors' rupiah
    figures are divided back into the reporting currency so growth excludes exchange-rate moves."""
    if not quarters:
        return ComparableEarnings("no_reports", None, None, None, None, None)
    latest_row = max(quarters, key=lambda row: str(row["date"]))
    period, prior_period = str(latest_row["date"]), year_earlier(str(latest_row["date"]))
    latest = plausible(latest_row.get("earnings"))
    prior_row = next((row for row in quarters if row["date"] == prior_period), None)
    if prior_row is None:
        return ComparableEarnings("prior_not_returned", period, prior_period, latest, None, None)
    prior = plausible(prior_row.get("earnings"))

    def result(condition: Condition, growth: float | None = None) -> ComparableEarnings:
        return ComparableEarnings(condition, period, prior_period, latest, prior, growth)

    if latest is None or prior is None:
        return result("earnings_missing")
    if latest == 0 or prior == 0:
        return result("zero_boundary")
    if latest > 0 and prior > 0:
        if period not in verified or prior_period not in verified or (verified[period], verified[prior_period]) != (
                latest, prior):
            return result("basis_unverified")
        if rates is None:
            return result("growth", round(latest / prior - 1, 10))
        if period not in rates or prior_period not in rates:
            return result("basis_unverified")
        return result("growth", round((latest / rates[period]) / (prior / rates[prior_period]) - 1, 10))
    if latest > 0:
        return result("loss_to_profit")
    return result("profit_to_loss" if prior > 0 else "persistent_loss")
