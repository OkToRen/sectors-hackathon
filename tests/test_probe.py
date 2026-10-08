import json
import tempfile
import unittest
from collections.abc import Mapping
from datetime import UTC, date, datetime
from pathlib import Path

from sectors.api import HttpResponse, TransportError
from sectors.probe import ProbeLimits, execute, plan, reconcile, run_probe
from tests.fakes import API_KEY, FakeTransport

TODAY = date(2026, 10, 6)
NOW = datetime(2026, 10, 6, 3, 0, tzinfo=UTC)
MEASURED = datetime(2026, 10, 6, 3, 30, tzinfo=UTC)


def all_text(root: Path) -> str:
    return "\n".join(path.read_text() for path in root.rglob("*") if path.is_file())


class ProbeTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.cache = Path(self.tmp.name) / "cache"

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def probe(self, transport: FakeTransport, budget: int = 50, run_cap: int = 20) -> list[str]:
        report = run_probe("bbca", self.cache, transport, API_KEY, ProbeLimits(budget, run_cap), clock=lambda: NOW)
        return [result.status for result in report.results]

    def test_captures_all_four_endpoints_with_key_only_in_header(self) -> None:
        transport = FakeTransport(TODAY)
        self.assertEqual(self.probe(transport), ["fetched"] * 4)
        paths = [url for url, _ in transport.calls]
        self.assertEqual(len(paths), 4)
        self.assertTrue(all(headers["Authorization"] == API_KEY for _, headers in transport.calls))
        self.assertTrue(all(API_KEY not in url for url in paths))
        self.assertIn("https://api.sectors.app/v2/foreign-flow/BBCA/?start=2026-07-09&end=2026-10-06", paths)
        self.assertNotIn(API_KEY, all_text(self.cache))

    def test_reusing_a_capture_makes_no_identical_request(self) -> None:
        self.probe(FakeTransport(TODAY))
        second = FakeTransport(TODAY)
        self.assertEqual(self.probe(second), ["reused"] * 4)
        self.assertEqual(second.calls, [])

    def test_ledger_records_documented_cost_separately_from_provider_charges(self) -> None:
        self.probe(FakeTransport(TODAY, headers={"X-Credits-Used": "1", "Content-Type": "application/json"}))
        entries = [json.loads(line) for line in (self.cache / "ledger.jsonl").read_text().splitlines()]
        by_endpoint = {entry["endpoint"]: entry for entry in entries}
        self.assertEqual(by_endpoint["quarterly_financials"]["documented_credits"], 5)
        self.assertEqual(by_endpoint["company_overview"]["documented_credits"], 1)
        self.assertEqual(by_endpoint["daily_prices"]["provider_charge_headers"], {"x-credits-used": "1"})

    def test_run_cap_stops_before_exceeding(self) -> None:
        transport = FakeTransport(TODAY)
        report = run_probe("BBCA", self.cache, transport, API_KEY, ProbeLimits(50, 6), clock=lambda: NOW)
        self.assertEqual([o.status for o in report.results], ["fetched", "fetched", "skipped", "skipped"])
        self.assertIn("per-run cap", report.results[2].detail)
        self.assertEqual(report.counted_this_run, 6)

    def test_allocation_counts_credits_from_earlier_runs(self) -> None:
        self.probe(FakeTransport(TODAY), budget=9, run_cap=8)
        later = FakeTransport(date(2026, 10, 7))
        report = run_probe("BBCA", self.cache, later, API_KEY, ProbeLimits(9, 8),
                           clock=lambda: datetime(2026, 10, 7, 3, 0, tzinfo=UTC))
        self.assertEqual({r.status for r in report.results}, {"skipped"})
        self.assertIn("credit allocation", report.results[2].detail)
        self.assertEqual(later.calls, [])

    def test_run_cap_cannot_exceed_allocation(self) -> None:
        with self.assertRaises(ValueError):
            ProbeLimits(5, 10)
        with self.assertRaises(ValueError):
            ProbeLimits(0, 0)

    def test_rejects_symbols_that_are_not_idx_tickers(self) -> None:
        with self.assertRaises(ValueError):
            run_probe("../etc", self.cache, FakeTransport(TODAY), API_KEY, ProbeLimits(50, 20), clock=lambda: NOW)

    def test_window_ends_on_the_jakarta_date(self) -> None:
        late_utc = datetime(2026, 10, 5, 20, 0, tzinfo=UTC)  # already 6 October in WIB
        transport = FakeTransport(TODAY)
        run_probe("BBCA", self.cache, transport, API_KEY, ProbeLimits(50, 20), clock=lambda: late_utc)
        self.assertTrue(transport.calls[-1][0].endswith("end=2026-10-06"))

    def test_dropped_connection_is_recorded_without_crashing(self) -> None:
        def dropped(url: str, headers: Mapping[str, str]) -> HttpResponse:
            raise TransportError("Remote end closed connection")
        report = run_probe("BBCA", self.cache, dropped, API_KEY, ProbeLimits(50, 20), clock=lambda: NOW)
        self.assertEqual({r.status for r in report.results}, {"unavailable"})
        self.assertIn("network error", report.results[0].detail)

    def test_endpoint_failures_are_reported_and_transient_ones_retried(self) -> None:
        transport = FakeTransport(TODAY, failures={"/foreign-flow/": 503, "/company/report/": 404})
        self.assertEqual(self.probe(transport), ["unavailable", "fetched", "fetched", "unavailable"])
        retry = FakeTransport(TODAY)
        self.assertEqual(self.probe(retry), ["reused", "reused", "reused", "fetched"])
        self.assertEqual(len(retry.calls), 1)

    def test_undated_captures_refresh_on_a_later_jakarta_date(self) -> None:
        self.probe(FakeTransport(TODAY))
        later = FakeTransport(date(2026, 10, 7))
        run_probe("BBCA", self.cache, later, API_KEY, ProbeLimits(50, 20),
                  clock=lambda: datetime(2026, 10, 7, 3, 0, tzinfo=UTC))
        self.assertEqual(len(later.calls), 4)
        self.assertEqual(self.probe(FakeTransport(TODAY)), ["reused"] * 4)

    def test_unparseable_success_is_unavailable_and_retried(self) -> None:
        def html(url: str, headers: Mapping[str, str]) -> HttpResponse:
            return HttpResponse(200, {}, b"<html>gateway</html>")
        report = run_probe("BBCA", self.cache, html, API_KEY, ProbeLimits(50, 20), clock=lambda: NOW)
        self.assertEqual({r.status for r in report.results}, {"unavailable"})
        self.assertIn("not JSON", report.results[0].detail)
        self.assertEqual(self.probe(FakeTransport(TODAY)), ["fetched"] * 4)

    def test_provider_reported_charge_above_documented_cost_is_enforced(self) -> None:
        transport = FakeTransport(TODAY, headers={"X-Credits-Used": "10"})
        report = run_probe("BBCA", self.cache, transport, API_KEY, ProbeLimits(16, 14), clock=lambda: NOW)
        self.assertEqual([r.status for r in report.results], ["fetched", "skipped", "skipped", "skipped"])
        self.assertEqual(report.counted_this_run, 10)
        self.assertIn("charged more than documented", report.results[1].detail)

    def test_key_in_transport_error_never_reaches_report_or_cache(self) -> None:
        def leaky(url: str, headers: Mapping[str, str]) -> HttpResponse:
            raise TransportError(f"bad header {headers['Authorization']}")
        report = run_probe("BBCA", self.cache, leaky, API_KEY, ProbeLimits(50, 20), clock=lambda: NOW)
        self.assertNotIn(API_KEY, " ".join(r.detail for r in report.results))
        self.assertNotIn(API_KEY, all_text(self.cache))

    def test_an_overcharge_blocks_later_runs_too(self) -> None:
        run_probe("BBCA", self.cache, FakeTransport(TODAY, headers={"X-Credits-Used": "10"}), API_KEY,
                  ProbeLimits(16, 14), clock=lambda: NOW)
        later = FakeTransport(TODAY)
        report = run_probe("BBRI", self.cache, later, API_KEY, ProbeLimits(16, 14), clock=lambda: NOW)
        self.assertEqual(later.calls, [])
        self.assertIn("charged more than documented", report.results[0].detail)

    def test_wrong_shape_success_is_unavailable_and_retried(self) -> None:
        def wrong(url: str, headers: Mapping[str, str]) -> HttpResponse:
            if "/financials/" in url:
                return HttpResponse(200, {}, b'[{"date": "not-a-date"}]')
            if "/daily/" in url:
                return HttpResponse(200, {}, b'[{"date": "20261001", "close": 100}, {"date": "2026-10-06", "close": 200}]')
            return HttpResponse(200, {}, b'{"detail": "upstream unavailable"}')
        report = run_probe("BBCA", self.cache, wrong, API_KEY, ProbeLimits(50, 20), clock=lambda: NOW)
        self.assertEqual({r.status for r in report.results}, {"unavailable"})
        self.assertIn("unexpected response shape", report.results[1].detail)
        self.assertEqual(self.probe(FakeTransport(TODAY)), ["fetched"] * 4)

    def test_overcharge_evidence_in_an_older_ledger_blocks_spending(self) -> None:
        self.cache.mkdir(parents=True)
        (self.cache / "ledger.jsonl").write_text(json.dumps(
            {"endpoint": "daily_prices", "documented_credits": 1, "estimated_max_credits": 1, "counted_credits": 1,
             "provider_charge_headers": {"x-credits-used": "10"}}) + "\n")
        transport = FakeTransport(TODAY)
        run_probe("BBCA", self.cache, transport, API_KEY, ProbeLimits(16, 14), clock=lambda: NOW)
        self.assertEqual(transport.calls, [])

    def test_older_cached_wrong_shape_success_is_refetched(self) -> None:
        self.probe(FakeTransport(TODAY))
        capture = next((self.cache / "captures" / "BBCA" / "quarterly_financials").glob("*.json"))
        record = json.loads(capture.read_text())
        record["body"] = [{"date": "not-a-date"}]
        capture.write_text(json.dumps(record))
        self.assertEqual(self.probe(FakeTransport(TODAY)), ["reused", "fetched", "reused", "reused"])

    def test_reserve_holds_back_part_of_the_allocation(self) -> None:
        run_probe("BBCA", self.cache, FakeTransport(TODAY), API_KEY, ProbeLimits(20, 6), clock=lambda: NOW)
        later = datetime(2026, 10, 7, 3, 0, tzinfo=UTC)
        report = run_probe("BBCA", self.cache, FakeTransport(date(2026, 10, 7)), API_KEY,
                           ProbeLimits(13, 6, reserve=2), clock=lambda: later)
        self.assertEqual([r.status for r in report.results], ["fetched", "skipped", "fetched", "fetched"])
        self.assertIn("reserve of 2", report.results[1].detail)
        self.assertEqual(report.counted_total, 9)

    def test_default_reserve_is_a_tenth_of_the_allocation(self) -> None:
        self.assertEqual(ProbeLimits(500, 20).kept, 50)
        self.assertEqual(ProbeLimits(9, 8).kept, 1)
        with self.assertRaises(ValueError):
            ProbeLimits(8, 8)
        with self.assertRaises(ValueError):
            ProbeLimits(50, 20, reserve=0)

    def test_a_rate_limit_stops_the_rest_of_the_run(self) -> None:
        transport = FakeTransport(TODAY, failures={"/financials/": 429})
        self.assertEqual(self.probe(transport), ["fetched", "unavailable", "skipped", "skipped"])
        self.assertEqual(len(transport.calls), 2)

    def test_more_quarters_than_reserved_counts_as_an_overcharge(self) -> None:
        normal = FakeTransport(TODAY)

        def six_quarters(url: str, headers: Mapping[str, str]) -> HttpResponse:
            if "/financials/" in url:
                rows = [{"date": f"202{year}-0{month}-30", "earnings": 1} for year in (5, 6) for month in (3, 4, 6)]
                return HttpResponse(200, {}, json.dumps(rows).encode())
            return normal(url, headers)
        report = run_probe("BBCA", self.cache, six_quarters, API_KEY, ProbeLimits(50, 20), clock=lambda: NOW)
        self.assertEqual([r.status for r in report.results], ["fetched", "fetched", "skipped", "skipped"])
        self.assertIn("charged more than documented", report.results[2].detail)
        self.assertEqual(report.counted_this_run, 7)

    def ledger_total(self) -> int:
        return sum(json.loads(line)["counted_credits"] for line in (self.cache / "ledger.jsonl").read_text().splitlines())

    def test_reconciling_to_measured_usage_sets_the_ledger_total_once(self) -> None:
        self.probe(FakeTransport(TODAY, failures={"/financials/": 503}))
        self.assertEqual(self.ledger_total(), 8)
        self.assertEqual(reconcile(self.cache, 3, "dashboard", measured_at=MEASURED), -5)
        self.assertEqual(reconcile(self.cache, 3, "dashboard", measured_at=MEASURED), 0)
        self.assertEqual(self.ledger_total(), 3)

    def test_a_measurement_older_than_any_ledger_entry_is_refused(self) -> None:
        self.probe(FakeTransport(TODAY, failures={"/financials/": 503}))
        reconcile(self.cache, 3, "dashboard", measured_at=MEASURED)
        after = datetime(2026, 10, 6, 4, 0, tzinfo=UTC)
        run_probe("BBCA", self.cache, FakeTransport(TODAY), API_KEY, ProbeLimits(50, 20), clock=lambda: after)
        total = self.ledger_total()
        for measured_at in (MEASURED, NOW, after):
            with self.subTest(measured_at=measured_at), self.assertRaises(ValueError):
                reconcile(self.cache, 3, "dashboard", measured_at=measured_at)
        self.assertEqual(self.ledger_total(), total)

    def test_a_measurement_needing_no_adjustment_still_blocks_older_ones(self) -> None:
        self.probe(FakeTransport(TODAY, failures={"/financials/": 503}))
        self.assertEqual(reconcile(self.cache, 8, "dashboard", measured_at=datetime(2026, 10, 6, 6, 0, tzinfo=UTC)), 0)
        with self.assertRaises(ValueError):
            reconcile(self.cache, 3, "dashboard", measured_at=MEASURED)
        self.assertEqual(self.ledger_total(), 8)

    def test_negative_measured_usage_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            reconcile(self.cache, -1, "dashboard", measured_at=MEASURED)

    def test_rate_limited_requests_cost_nothing(self) -> None:
        self.probe(FakeTransport(TODAY, failures={"/financials/": 429}))
        entries = [json.loads(line) for line in (self.cache / "ledger.jsonl").read_text().splitlines()]
        self.assertEqual([e["counted_credits"] for e in entries if e["status"] == 429], [0])

    def test_live_requests_can_be_paced(self) -> None:
        pauses: list[float] = []
        requests = [("BBCA", request) for request in plan("BBCA", TODAY)]
        execute(requests, self.cache, FakeTransport(TODAY), API_KEY, ProbeLimits(50, 20), clock=lambda: NOW,
                pause=2.5, sleep=pauses.append)
        self.assertEqual(pauses, [2.5, 2.5, 2.5])


if __name__ == "__main__":
    unittest.main()
