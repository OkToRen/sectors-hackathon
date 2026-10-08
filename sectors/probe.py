"""One-ticker probe: capture the required Sectors endpoints within a credit allocation."""

import argparse
import json
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urlencode

from sectors.api import (BASE_URL, COMPANY_OVERVIEW, DAILY_PRICES, FOREIGN_FLOW, QUARTERLY_FINANCIALS,
                         Endpoint, Transport, TransportError, is_stable_answer, is_success, normalize_symbol,
                         charge, provider_charge_headers, reported_charge, urllib_transport)
from sectors.cache import CaptureStore, Params, is_usable
from sectors.env import setting

# Five quarters reach the same quarter a year earlier; ~90 calendar days hold ~60 trading days.
QUARTERS_REQUESTED = 5
WINDOW_DAYS = 89
WIB = timezone(timedelta(hours=7), "WIB")

Status = Literal["fetched", "reused", "skipped", "unavailable", "planned"]


@dataclass(frozen=True)
class ProbeLimits:
    """Credits kept in reserve are never spent by a probe; they cover refreshes and errors.
    Without an explicit reserve, a tenth of the allocation (at least one credit) is kept."""
    allocation: int
    run_cap: int
    reserve: int | None = None

    def __post_init__(self) -> None:
        if self.allocation <= 0:
            raise ValueError("A confirmed, positive credit allocation is required.")
        if not 1 <= self.kept < self.allocation:
            raise ValueError("The reserve must be at least one credit and leave part of the allocation spendable.")
        if not 0 < self.run_cap <= self.spendable:
            raise ValueError("The per-run cap must be positive and within the allocation less the reserve.")

    @property
    def kept(self) -> int:
        return self.reserve if self.reserve is not None else max(1, self.allocation // 10)

    @property
    def spendable(self) -> int:
        return self.allocation - self.kept


@dataclass(frozen=True)
class PlannedRequest:
    endpoint: Endpoint
    path: str
    params: Params
    estimated_max_credits: int


@dataclass(frozen=True)
class FetchResult:
    owner: str
    endpoint: str
    status: Status
    detail: str


@dataclass(frozen=True)
class ProbeReport:
    """counted_total includes credits a dry run planned but did not record; rate_limited carries across stages."""
    results: list[FetchResult]
    counted_this_run: int
    counted_total: int
    allocation: int
    planned_unrecorded: int = 0
    rate_limited: bool = False


def plan(symbol: str, today: date) -> list[PlannedRequest]:
    window = (("start", (today - timedelta(days=WINDOW_DAYS)).isoformat()), ("end", today.isoformat()))
    requests: list[tuple[Endpoint, Params, int]] = [
        (COMPANY_OVERVIEW, (("sections", "overview"),), 1),
        (QUARTERLY_FINANCIALS, (("n_quarters", str(QUARTERS_REQUESTED)),), QUARTERS_REQUESTED),
        (DAILY_PRICES, window, 1),
        (FOREIGN_FLOW, window, 1),
    ]
    return [PlannedRequest(endpoint, endpoint.path.format(symbol=symbol), params, estimate)
            for endpoint, params, estimate in requests]


def run_probe(symbol: str, cache_dir: Path, transport: Transport, api_key: str, limits: ProbeLimits,
              clock: Callable[[], datetime] = lambda: datetime.now(UTC)) -> ProbeReport:
    symbol = normalize_symbol(symbol)
    # IDX trades on Jakarta time, so the window ends on today's WIB date.
    today = clock().astimezone(WIB).date()
    return execute([(symbol, request) for request in plan(symbol, today)], cache_dir, transport, api_key, limits,
                   clock)


def execute(requests: list[tuple[str, PlannedRequest]], cache_dir: Path, transport: Transport | None,
            api_key: str, limits: ProbeLimits,
            clock: Callable[[], datetime] = lambda: datetime.now(UTC),
            earlier: ProbeReport | None = None, pause: float = 0.0,
            sleep: Callable[[float], object] = time.sleep) -> ProbeReport:
    """Reuse, budget-check and fetch each request in order. Without a transport nothing is fetched: requests
    that would be fetched are reported as planned, so a dry run prints the same decisions at no cost. An earlier
    stage of the same run passes its report so caps, planned credits and a rate limit carry over."""
    if not api_key and transport is not None:
        raise ValueError("SECTORS_API_KEY is not set.")
    store = CaptureStore(cache_dir, secret=api_key)
    ledger = store.ledger()
    unrecorded = earlier.planned_unrecorded if earlier else 0
    counted_total = sum(int(entry["counted_credits"]) for entry in ledger) + unrecorded
    counted_run = earlier.counted_this_run if earlier else 0
    overcharged = any(_overcharged(entry) for entry in ledger)
    rate_limited = earlier.rate_limited if earlier else False
    sent = 0
    results: list[FetchResult] = []
    vintage = clock().astimezone(WIB).date().isoformat()
    for owner, request in requests:
        name = request.endpoint.name

        def report(status: Status, detail: str) -> None:
            results.append(FetchResult(owner, name, status, detail))

        capture_path = store.capture_path(owner, name, request.path, request.params, vintage)
        existing = store.load(capture_path)
        if existing and existing["reusable"] and (is_usable(existing) or not is_success(existing["status"])):
            report("reused", f"capture from {existing['retrieved_at']}")
            continue
        estimate = request.estimated_max_credits
        if rate_limited:
            report("skipped", "the provider rate-limited an earlier request in this run")
            continue
        if overcharged:
            report("skipped", "the provider charged more than documented; verify actual costs before spending more")
            continue
        if counted_run + estimate > limits.run_cap:
            report("skipped", f"would exceed the per-run cap of {limits.run_cap} credits")
            continue
        if counted_total + estimate > limits.spendable:
            report("skipped", f"would exceed the confirmed credit allocation of {limits.allocation} "
                              f"less its reserve of {limits.kept}")
            continue
        if transport is None:
            counted_run += estimate
            counted_total += estimate
            unrecorded += estimate
            report("planned", f"up to {estimate} credit(s)")
            continue
        if pause and sent:
            sleep(pause)  # spacing live requests keeps bursts under the provider's rate limit
        sent += 1
        record = _request(transport, api_key, owner, request, clock)
        counted = record["documented_credits"] if record["documented_credits"] is not None else estimate
        counted = max(counted, reported_charge(record["provider_charge_headers"]) or 0)
        counted_run += counted
        counted_total += counted
        store.save(capture_path, record)
        store.append_ledger({key: record[key] for key in
                             ("retrieved_at", "symbol", "endpoint", "status", "error", "documented_credits",
                              "estimated_max_credits", "provider_charge_headers")}
                            | {"request": record["request"], "counted_credits": counted})
        overcharged = overcharged or _overcharged(record)
        rate_limited = rate_limited or record["status"] == 429
        if is_usable(record):
            report("fetched", f"HTTP {record['status']}")
        else:
            report("unavailable", record["error"] or f"HTTP {record['status']}")
    return ProbeReport(results, counted_run, counted_total, limits.allocation, unrecorded, rate_limited)


def _request(transport: Transport, api_key: str, symbol: str, request: PlannedRequest,
             clock: Callable[[], datetime]) -> dict[str, Any]:
    record: dict[str, Any] = {
        "schema": 1, "symbol": symbol, "endpoint": request.endpoint.name,
        "request": {"base_url": BASE_URL, "path": request.path, "params": [list(p) for p in request.params]},
        "retrieved_at": None,
        "estimated_max_credits": request.estimated_max_credits,
        "status": None, "error": None, "body": None, "reusable": False,
        "documented_credits": None, "provider_charge_headers": {},
    }
    url = f"{BASE_URL}{request.path}?{urlencode(request.params)}"
    try:
        response = transport(url, {"Authorization": api_key, "Accept": "application/json"})
    except TransportError as error:
        record.update(error=f"network error: {error}".replace(api_key, "[redacted]"), retrieved_at=_stamp(clock))
        return record
    problem = None
    try:
        body: object = json.loads(response.body)
    except ValueError:
        problem = f"HTTP {response.status} body is not JSON"
        body = response.body.decode(errors="replace")[:2000]
    else:
        if is_success(response.status) and not request.endpoint.shape_ok(body):
            problem = f"HTTP {response.status} with an unexpected response shape"
    record.update(status=response.status, body=body, retrieved_at=_stamp(clock),
                  documented_credits=charge(request.endpoint, response.status, body),
                  provider_charge_headers=provider_charge_headers(response.headers),
                  reusable=problem is None and is_stable_answer(response.status), error=problem)
    return record


def reconcile(cache_dir: Path, measured_used: int, source: str, measured_at: datetime) -> int:
    """Record provider-measured usage as of measured_at by appending the adjustment that brings the ledger total to
    it. Only a measurement newer than every ledger entry is accepted: an older or same-second one cannot tell which
    charges it saw, so it is refused and a fresh reading is needed. Repeating the latest reconciliation adds nothing.
    Returns the adjustment."""
    if measured_used < 0:
        raise ValueError("Measured usage cannot be negative.")
    stamp = measured_at.astimezone(UTC).isoformat(timespec="seconds")
    store = CaptureStore(cache_dir)
    ledger = store.ledger()
    latest = ledger[-1] if ledger else None
    if latest and latest.get("kind") == "reconciliation" and (latest["retrieved_at"], latest["measured_used"]) == (
            stamp, measured_used):
        return 0
    if any(str(entry["retrieved_at"]) >= stamp for entry in ledger):
        raise ValueError("The ledger has entries at or after this measurement; take a fresh reading.")
    adjustment = measured_used - sum(int(entry["counted_credits"]) for entry in ledger)
    # Recorded even at zero, so the measurement's time still blocks older readings.
    store.append_ledger({"kind": "reconciliation", "retrieved_at": stamp, "measured_used": measured_used,
                         "source": source, "counted_credits": adjustment})
    return adjustment


def _overcharged(entry: dict[str, Any]) -> bool:
    """More was spent than reserved for the request, or the provider reported more than the documented cost
    (the reserved estimate where none is documented)."""
    if entry.get("kind") == "reconciliation":
        return False
    expected = entry["documented_credits"] if entry["documented_credits"] is not None else entry["estimated_max_credits"]
    documented_over = (entry["documented_credits"] or 0) > int(entry["estimated_max_credits"])
    return documented_over or (reported_charge(entry["provider_charge_headers"]) or 0) > int(expected)


def _stamp(clock: Callable[[], datetime]) -> str:
    return clock().astimezone(UTC).isoformat(timespec="seconds")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Probe one ticker across the required Sectors v2 endpoints.")
    parser.add_argument("symbol")
    parser.add_argument("--max-credits", type=int, required=True, help="per-run credit cap")
    parser.add_argument("--cache", type=Path, default=Path("cache"))
    parser.add_argument("--env-file", type=Path, default=Path(".env"))
    args = parser.parse_args(argv)
    allocation = setting("SECTORS_CREDIT_BUDGET", args.env_file)
    if not allocation.isdigit():
        print("Set SECTORS_CREDIT_BUDGET to the confirmed team allocation before probing.", file=sys.stderr)
        return 2
    try:
        limits = ProbeLimits(int(allocation), args.max_credits)
        report = run_probe(args.symbol, args.cache, urllib_transport,
                           setting("SECTORS_API_KEY", args.env_file), limits)
    except ValueError as error:
        print(error, file=sys.stderr)
        return 2
    for result in report.results:
        print(f"{result.endpoint:22} {result.status:12} {result.detail}")
    print(f"Credits counted this run: {report.counted_this_run}, from documented costs, or the reserved estimate "
          f"where the documentation is silent. Ledger total: {report.counted_total} of {report.allocation}. "
          f"Provider charge headers, if any, are stored separately in the ledger.")
    return 0
