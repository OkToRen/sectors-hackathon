"""Sectors v2 endpoints, documented credit costs, and the HTTP transport seam."""

import http.client
import re
import urllib.error
import urllib.request
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import date
from typing import Protocol

BASE_URL = "https://api.sectors.app"
CHARGE_HEADER_HINTS = ("credit", "quota", "ratelimit", "rate-limit", "usage")


@dataclass(frozen=True)
class HttpResponse:
    status: int
    headers: Mapping[str, str]
    body: bytes


class TransportError(Exception):
    """The request never produced an HTTP status."""


class Transport(Protocol):
    def __call__(self, url: str, headers: Mapping[str, str]) -> HttpResponse: ...


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """Following a redirect would resend the Authorization header to wherever it points."""

    def redirect_request(self, *args: object, **kwargs: object) -> None:
        return None


_OPENER = urllib.request.build_opener(_NoRedirect)


def urllib_transport(url: str, headers: Mapping[str, str]) -> HttpResponse:
    request = urllib.request.Request(url, headers={**headers, "User-Agent": "company-state-monitor/0.1"})
    try:
        try:
            with _OPENER.open(request, timeout=30) as response:
                return HttpResponse(response.status, dict(response.headers.items()), response.read())
        except urllib.error.HTTPError as error:
            with error:
                return HttpResponse(error.code, dict(error.headers.items()), error.read())
    except http.client.HTTPException as error:  # truncated or malformed responses
        raise TransportError(type(error).__name__) from None
    except OSError as error:  # URLError, timeouts, resets and dropped connections
        raise TransportError(str(getattr(error, "reason", error)) or type(error).__name__) from None


def provider_charge_headers(headers: Mapping[str, str]) -> dict[str, str]:
    """Headers that may report a measured charge or quota; everything else is dropped."""
    return {name.lower(): value for name, value in headers.items()
            if any(hint in name.lower() for hint in CHARGE_HEADER_HINTS)}


def reported_charge(headers: Mapping[str, str]) -> int | None:
    """An integer charge the provider reports for this request; remaining/limit quotas are not charges."""
    values = [int(value) for name, value in headers.items()
              if any(word in name for word in ("used", "charge", "cost")) and value.strip().isdigit()]
    return max(values, default=None)


def is_success(status: int | None) -> bool:
    return status is not None and 200 <= status < 300


def is_stable_answer(status: int | None) -> bool:
    """Successes and not-found answers are kept; other failures may be retried."""
    return is_success(status) or status == 404


def normalize_symbol(symbol: str) -> str:
    normalized = symbol.strip().upper().removesuffix(".JK")
    if not re.fullmatch(r"[A-Z]{4}", normalized):
        raise ValueError(f"Not an IDX ticker: {symbol!r}")
    return normalized


# Documented charges for a response, or None where the documentation is silent.
def _company_report(status: int, body: object) -> int | None:
    return 1 if is_stable_answer(status) else 0 if status == 400 else None


def _daily(status: int, body: object) -> int | None:
    return 1 if is_success(status) else None


def _foreign_flow(status: int, body: object) -> int | None:
    if is_stable_answer(status):
        return 1
    return 0 if status in (400, 401, 403, 429) or status >= 500 else None


def _per_quarter(status: int, body: object) -> int | None:
    if is_success(status):
        return len(body) if isinstance(body, list) else None
    return 1 if status == 404 else None


def _dated_rows(body: object) -> bool:
    def dated(row: object) -> bool:
        try:
            value = row.get("date") if isinstance(row, dict) else None
            # Rows sort as text, so only the canonical YYYY-MM-DD form is accepted.
            return isinstance(value, str) and date.fromisoformat(value).isoformat() == value
        except ValueError:
            return False
    return isinstance(body, list) and all(dated(row) for row in body)


def _overview_shape(body: object) -> bool:
    return isinstance(body, dict) and isinstance(body.get("symbol"), str)


def _flow_shape(body: object) -> bool:
    return isinstance(body, dict) and _dated_rows(body.get("data"))


def _roster_shape(body: object) -> bool:
    """A complete page of valid, distinct IDX tickers; a partial roster would silently drop members."""
    if not isinstance(body, dict) or not isinstance(body.get("pagination"), dict):
        return False
    rows, pages = body.get("results"), body["pagination"]
    if not isinstance(rows, list) or pages.get("has_next") is not False or pages.get("total_count") != len(rows):
        return False
    try:
        symbols = [normalize_symbol(row["symbol"]) for row in rows]
    except (TypeError, KeyError, ValueError, AttributeError):
        return False
    return len(set(symbols)) == len(symbols)


def charge(endpoint: "Endpoint", status: int, body: object) -> int | None:
    """Documented cost of a response. Rate-limited requests cost nothing: on 2026-10-06 the Sectors dashboard
    showed 350 credits used, exactly the cost of the successful requests, after 54 requests got HTTP 429."""
    return 0 if status == 429 else endpoint.documented_charge(status, body)


def _structured_query(status: int, body: object) -> int | None:
    return 1 if is_success(status) else None


@dataclass(frozen=True)
class Endpoint:
    name: str
    label: str
    path: str
    documented_charge: Callable[[int, object], int | None]
    shape_ok: Callable[[object], bool]


COMPANY_OVERVIEW = Endpoint("company_overview", "Company overview", "/v2/company/report/{symbol}/", _company_report,
                            _overview_shape)
QUARTERLY_FINANCIALS = Endpoint("quarterly_financials", "Quarterly financials",
                                "/v2/financials/quarterly/{symbol}/", _per_quarter, _dated_rows)
DAILY_PRICES = Endpoint("daily_prices", "Daily prices", "/v2/daily/{symbol}/", _daily, _dated_rows)
FOREIGN_FLOW = Endpoint("foreign_flow", "Foreign flow", "/v2/foreign-flow/{symbol}/", _foreign_flow, _flow_shape)
COMPANIES = Endpoint("companies", "Companies screener", "/v2/companies/", _structured_query, _roster_shape)
ENDPOINTS = (COMPANY_OVERVIEW, QUARTERLY_FINANCIALS, DAILY_PRICES, FOREIGN_FLOW)
ENDPOINT_BY_NAME = {endpoint.name: endpoint for endpoint in (*ENDPOINTS, COMPANIES)}
