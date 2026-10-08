"""Fake Sectors transport used at the probe seam."""

import json
from collections.abc import Mapping
from datetime import date, timedelta
from urllib.parse import parse_qsl, urlsplit

from sectors.basis import BasisCheck
from sectors.api import HttpResponse

API_KEY = "test-key-do-not-leak-7f3a"


def daily_rows(symbol: str, end: date, days: int) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    day = end
    while len(rows) < days:
        if day.weekday() < 5:
            # The close depends only on the date, so overlapping windows agree as real captures do.
            rows.append({"symbol": symbol, "date": day.isoformat(), "close": 9000 + (day - date(2026, 1, 1)).days,
                         "open": None, "high": None, "low": None, "volume": 1000,
                         "market_cap": (9000 + (day - date(2026, 1, 1)).days) * 120_000_000_000})
        day -= timedelta(days=1)
    return sorted(rows, key=lambda row: str(row["date"]))


def flow_rows(symbol: str, end: date, days: int, null_days: int = 0) -> list[dict[str, object]]:
    rows = []
    for index, row in enumerate(daily_rows(symbol, end, days)):
        value = None if index < null_days else 1_000_000
        rows.append({"date": row["date"], "net_foreign_inflow": value, "foreign_buy_idr": None,
                     "foreign_sell_idr": None, "foreign_share": None})
    return rows


QUARTERS: list[dict[str, object]] = [
    {"symbol": "BBCA.JK", "date": "2026-06-30", "revenue": 30_000_000_000_000, "earnings": 14_150_000_000_000},
    {"symbol": "BBCA.JK", "date": "2026-03-31", "revenue": 29_000_000_000_000, "earnings": 14_000_000_000_000},
    {"symbol": "BBCA.JK", "date": "2025-12-31", "revenue": 28_000_000_000_000, "earnings": None},
    {"symbol": "BBCA.JK", "date": "2025-09-30", "revenue": 27_000_000_000_000, "earnings": 13_500_000_000_000},
    {"symbol": "BBCA.JK", "date": "2025-06-30", "revenue": 26_000_000_000_000, "earnings": 13_000_000_000_000},
]


class FakeTransport:
    """Answers each endpoint with realistic bodies, or a configured failure."""

    def __init__(self, today: date, failures: Mapping[str, int] | None = None,
                 headers: Mapping[str, str] | None = None, flow_null_days: int = 0,
                 roster: tuple[str, ...] = ("BBCA", "BBRI")) -> None:
        self.roster = roster
        self.today = today
        self.failures = dict(failures or {})
        self.headers = dict(headers or {})
        self.flow_null_days = flow_null_days
        self.calls: list[tuple[str, dict[str, str]]] = []

    def __call__(self, url: str, headers: Mapping[str, str]) -> HttpResponse:
        self.calls.append((url, dict(headers)))
        parts = urlsplit(url)
        params = dict(parse_qsl(parts.query))
        path = parts.path
        for fragment, status in self.failures.items():
            if fragment in path:
                return HttpResponse(status, self.headers, json.dumps({"detail": "failed"}).encode())
        body: object
        if path == "/v2/companies/":
            body = {"pagination": {"has_next": False, "total_count": len(self.roster)},
                    "results": [{"symbol": f"{symbol}.JK", "company_name": f"PT {symbol} Tbk"} for symbol in self.roster]}
        elif "/company/report/" in path:
            body = {"symbol": "BBCA.JK", "company_name": "PT Bank Central Asia Tbk.",
                    "overview": {"sector": "Financials", "sub_sector": "Banks", "listing_date": "2000-05-31"}}
        elif "/financials/quarterly/" in path:
            body = QUARTERS[: int(params.get("n_quarters", "5"))]
        elif "/daily/" in path:
            body = daily_rows("BBCA.JK", date.fromisoformat(params["end"]), 63)
        elif "/foreign-flow/" in path:
            body = {"symbol": "BBCA.JK", "start": params["start"], "end": params["end"],
                    "data": flow_rows("BBCA.JK", date.fromisoformat(params["end"]), 63, self.flow_null_days)}
        else:
            return HttpResponse(404, {}, b"{}")
        return HttpResponse(200, self.headers, json.dumps(body).encode())


def verified_fake_basis() -> dict[str, BasisCheck]:
    """Treats the fake BBCA quarters as verified, so tests can exercise the published-growth path."""
    earnings: dict[str, int | float] = {str(q["date"]): q["earnings"] for q in QUARTERS if isinstance(q["earnings"], int)}
    return {"BBCA": BasisCheck("BBCA", "verified", earnings, "Fake evidence for tests.", "https://example.test")}
