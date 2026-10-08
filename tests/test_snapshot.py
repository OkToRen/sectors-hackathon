import json
import re
import tempfile
import unittest
from collections.abc import Mapping
from datetime import UTC, date, datetime
from pathlib import Path
from unittest import mock

from sectors.api import HttpResponse
from sectors.basis import BasisCheck
from sectors.api import DAILY_PRICES
from sectors.probe import PlannedRequest, ProbeLimits, execute, run_probe
from sectors.snapshot import build_snapshot
from tests.fakes import API_KEY, FakeTransport, verified_fake_basis

TODAY = date(2026, 10, 6)
PROBED = datetime(2026, 10, 6, 3, 0, tzinfo=UTC)
GENERATED = datetime(2026, 10, 6, 5, 30, tzinfo=UTC)
TEMPLATE_DIR = Path(__file__).resolve().parents[1] / "app"
STATE_NAMES = ["Ignored Improvement", "Confirmed Strength", "Crowded Optimism", "Early Deterioration"]


def text_of(html: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html))


class SnapshotTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.cache, self.out = root / "cache", root / "dist"

        self.checks = verified_fake_basis()

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def probe(self, transport: FakeTransport) -> None:
        run_probe("BBCA", self.cache, transport, API_KEY, ProbeLimits(50, 20), clock=lambda: PROBED)

    def build(self) -> tuple[str, dict[str, object]]:
        with mock.patch("urllib.request.urlopen", side_effect=AssertionError("network used")), \
             mock.patch("socket.create_connection", side_effect=AssertionError("network used")):
            build_snapshot("BBCA", self.cache, self.out, TEMPLATE_DIR, now=GENERATED, checks=self.checks)
        html = (self.out / "BBCA.html").read_text()
        return html, json.loads((self.out / "BBCA.json").read_text())

    def test_offline_view_shows_timestamp_inputs_coverage_and_provenance(self) -> None:
        self.probe(FakeTransport(TODAY))
        html, data = self.build()
        page = text_of(html)
        self.assertIn("Snapshot generated 6 Oct 2026, 12:30 WIB", page)
        self.assertIn("PT Bank Central Asia Tbk.", page)
        self.assertIn("Financials", page)
        self.assertIn("IDR 14.15 tn", page)
        self.assertIn("Report period 2026-06-30", page)
        self.assertIn("2026-07-09 to 2026-10-06", page)
        self.assertIn("2026-07-10 to 2026-10-06", page)
        self.assertIn("IDR 30.00 tn", page)
        self.assertIn("Listed 2000-05-31", page)
        self.assertIn("2026-10-06 03:00", page)
        self.assertIn("GET /v2/foreign-flow/BBCA/?start=2026-07-09&amp;end=2026-10-06", html)
        self.assertIn("8 credits, documented estimate", page)
        self.assertIn("No provider-reported charge", page)
        self.assertTrue((self.out / "styles.css").exists())
        self.assertNotIn("$", page)
        self.assertEqual(data["data_availability"], "Unclassified")
        self.assertEqual(data["evidence_strength"], "Insufficient")

    def test_no_state_or_outcome_is_invented(self) -> None:
        self.probe(FakeTransport(TODAY))
        html, data = self.build()
        page = text_of(html)
        self.assertIn("Unclassified", page)
        self.assertIn("Historical evidence Insufficient", page)
        for name in STATE_NAMES:
            self.assertNotIn(name, page)
        evidence = text_of(html.split('class="arch quiet"', 1)[1].split("</div>", 1)[0])
        self.assertIn("Insufficient", evidence)
        self.assertNotIn("%", evidence)
        for outcome_word in ("outperform", "excess return", "win rate", "hit rate"):
            self.assertNotIn(outcome_word, page.lower())
        self.assertIsNone(data["state"])

    def test_classification_blockers_are_visible(self) -> None:
        self.probe(FakeTransport(TODAY))
        _, data = self.build()
        blockers = data["blockers"]
        assert isinstance(blockers, list)
        gates = " ".join(gate["detail"] for gate in blockers)
        for phrase in ["roster was not captured", "No IDX holiday list covers 2026", "no usable frozen neutral band"]:
            self.assertIn(phrase, gates)
        self.assertNotIn("Accounting", [gate["topic"] for gate in blockers])
        self.assertEqual(data["comparable_earnings"], {
            "condition": "growth", "latest_period": "2026-06-30", "prior_period": "2025-06-30",
            "latest": 14_150_000_000_000, "prior": 13_000_000_000_000, "growth": 0.0884615385})

    def test_missing_earnings_on_unverified_periods_are_not_covered_by_evidence(self) -> None:
        self.probe(FakeTransport(TODAY))
        capture = next((self.cache / "captures" / "BBCA" / "quarterly_financials").glob("*.json"))
        record = json.loads(capture.read_text())
        record["body"] = [{"date": "2023-09-30", "earnings": None}, {"date": "2024-09-30", "earnings": None}]
        capture.write_text(json.dumps(record))
        _, data = self.build()
        self.assertIsNone(data["earnings_basis"])
        self.assertIn("compared quarters", " ".join(b["detail"] for b in data["blockers"]))  # type: ignore[attr-defined]

    def test_a_recorded_basis_problem_is_the_accounting_reason(self) -> None:
        self.probe(FakeTransport(TODAY))
        self.checks = {"BBCA": BasisCheck("BBCA", "reporting_currency", {}, "Reports in USD; growth would mix FX.",
                                          "https://example.test")}
        _, data = self.build()
        blockers, earnings = data["blockers"], data["comparable_earnings"]
        assert isinstance(blockers, list) and isinstance(earnings, dict)
        self.assertIn({"topic": "Accounting", "detail": "Reports in USD; growth would mix FX."}, blockers)
        self.assertEqual(earnings["condition"], "basis_unverified")

    def test_unverified_company_keeps_the_basis_blocker(self) -> None:
        run_probe("BBRI", self.cache, FakeTransport(TODAY), API_KEY, ProbeLimits(50, 20), clock=lambda: PROBED)
        build_snapshot("BBRI", self.cache, self.out, TEMPLATE_DIR, now=GENERATED, checks=self.checks)
        data = json.loads((self.out / "BBRI.json").read_text())
        self.assertIn({"topic": "Accounting", "detail": "The standalone, consolidated earnings basis has not been "
                       "checked against this company's own published report for both compared quarters."}, data["blockers"])
        self.assertEqual(data["comparable_earnings"]["condition"], "basis_unverified")
        self.assertIsNone(data["comparable_earnings"]["growth"])

    def test_missing_values_stay_unavailable_not_zero(self) -> None:
        self.probe(FakeTransport(TODAY, failures={"/financials/quarterly/": 404}, flow_null_days=2))
        html, data = self.build()
        page = text_of(html)
        self.assertIn("Quarterly financials unavailable: HTTP 404", page)
        self.assertIn("Incomplete", page)
        self.assertIn("2 of 63 returned days have no value", page)
        inputs = data["inputs"]
        assert isinstance(inputs, dict)
        self.assertIsNone(inputs["latest_earnings"])
        self.assertIsNone(inputs["net_foreign_flow_sum"])

    def test_newer_failure_does_not_hide_an_earlier_successful_capture(self) -> None:
        self.probe(FakeTransport(TODAY))
        later = datetime(2026, 10, 7, 3, 0, tzinfo=UTC)
        run_probe("BBCA", self.cache, FakeTransport(date(2026, 10, 7), failures={"/daily/": 503}), API_KEY,
                  ProbeLimits(50, 20), clock=lambda: later)
        html, _ = self.build()
        self.assertNotIn("Daily prices unavailable", text_of(html))
        self.assertIn("63 trading days returned", text_of(html))

    def test_newer_unparseable_success_does_not_hide_an_earlier_capture(self) -> None:
        self.probe(FakeTransport(TODAY))
        def gateway(url: str, headers: Mapping[str, str]) -> HttpResponse:
            return HttpResponse(200, {}, b"<html>gateway</html>")
        run_probe("BBCA", self.cache, gateway, API_KEY, ProbeLimits(50, 20),
                  clock=lambda: datetime(2026, 10, 7, 3, 0, tzinfo=UTC))
        html, _ = self.build()
        self.assertIn("63 trading days returned", text_of(html))

    def test_only_unparseable_success_is_shown_unavailable(self) -> None:
        def gateway(url: str, headers: Mapping[str, str]) -> HttpResponse:
            return HttpResponse(200, {}, b"<html>gateway</html>")
        run_probe("BBCA", self.cache, gateway, API_KEY, ProbeLimits(50, 20), clock=lambda: datetime(2026, 10, 6, 3, 0, tzinfo=UTC))
        html, _ = self.build()
        self.assertIn("Daily prices unavailable: HTTP 200 body is not JSON", text_of(html))

    def test_older_cached_wrong_shape_success_is_unavailable_offline(self) -> None:
        self.probe(FakeTransport(TODAY))
        capture = next((self.cache / "captures" / "BBCA" / "quarterly_financials").glob("*.json"))
        record = json.loads(capture.read_text())
        record["body"] = [{"date": "not-a-date"}]
        capture.write_text(json.dumps(record))
        html, _ = self.build()
        self.assertIn("No quarterly record captured", text_of(html))

    def test_price_windows_from_separate_captures_are_merged_by_date(self) -> None:
        self.probe(FakeTransport(TODAY))
        earlier = PlannedRequest(DAILY_PRICES, "/v2/daily/BBCA/", (("start", "2026-04-01"), ("end", "2026-07-08")), 1)
        execute([("BBCA", earlier)], self.cache, FakeTransport(date(2026, 7, 8)), API_KEY, ProbeLimits(50, 20),
                clock=lambda: datetime(2026, 10, 6, 4, 0, tzinfo=UTC))
        _, data = self.build()
        inputs = data["inputs"]
        assert isinstance(inputs, dict)
        self.assertEqual(inputs["price_days_returned"], 63 + 63)
        self.assertEqual(inputs["latest_close_date"], "2026-10-06")
        coverage = data["coverage"]
        assert isinstance(coverage, list)
        prices = [row for row in coverage if row["endpoint"] == "daily_prices"]
        self.assertEqual([(r["requested_end"], r["last_date"], r["records"]) for r in prices],
                         [("2026-07-08", "2026-07-08", 63), ("2026-10-06", "2026-10-06", 63)])
        credits = data["credits"]
        assert isinstance(credits, dict)
        self.assertEqual(credits["documented_estimate"], 8 + 1)

    def test_without_a_freeze_no_state_is_published(self) -> None:
        self.probe(FakeTransport(TODAY))
        _, data = self.build()
        dimensions = data["dimensions"]
        assert isinstance(dimensions, dict)
        self.assertEqual({d["band"] for d in dimensions.values()}, {None})
        self.assertFalse(data["bands_frozen"])

    def test_fractional_provider_values_are_shown_not_dropped(self) -> None:
        self.probe(FakeTransport(TODAY))
        capture = next((self.cache / "captures" / "BBCA" / "daily_prices").glob("*.json"))
        record = json.loads(capture.read_text())
        record["body"][-1]["close"] = 9100.5
        capture.write_text(json.dumps(record))
        html, _ = self.build()
        self.assertIn("IDR 9,100.5", text_of(html))

    def test_scaled_values_also_show_every_returned_digit(self) -> None:
        self.probe(FakeTransport(TODAY))
        capture = next((self.cache / "captures" / "BBCA" / "daily_prices").glob("*.json"))
        record = json.loads(capture.read_text())
        record["body"][-1]["market_cap"] = 754123456789012.5
        capture.write_text(json.dumps(record))
        html, _ = self.build()
        self.assertIn("raw 754,123,456,789,012.5", text_of(html))

    def test_non_text_company_fields_are_treated_as_missing(self) -> None:
        self.probe(FakeTransport(TODAY))
        capture = next((self.cache / "captures" / "BBCA" / "company_overview").glob("*.json"))
        record = json.loads(capture.read_text())
        record["body"]["company_name"] = 123
        record["body"]["overview"]["sector"] = ["Financials"]
        capture.write_text(json.dumps(record))
        html, _ = self.build()
        self.assertIn("BBCA · Banks · Listed 2000-05-31 BBCA A dated", text_of(html))
        self.assertNotIn("Financials", text_of(html))

    def test_nonfinite_numbers_are_unavailable(self) -> None:
        self.probe(FakeTransport(TODAY))
        capture = next((self.cache / "captures" / "BBCA" / "daily_prices").glob("*.json"))
        record = json.loads(capture.read_text())
        record["body"][-1]["close"] = float("inf")
        capture.write_text(json.dumps(record))
        html, _ = self.build()
        self.assertNotIn("IDR inf", text_of(html))
        self.assertIn("Latest close Unavailable", text_of(html))

    def test_implausibly_large_numbers_are_unavailable(self) -> None:
        self.probe(FakeTransport(TODAY))
        capture = next((self.cache / "captures" / "BBCA" / "daily_prices").glob("*.json"))
        record = json.loads(capture.read_text())
        record["body"][-1]["close"] = 10**400
        capture.write_text(json.dumps(record))
        flow = next((self.cache / "captures" / "BBCA" / "foreign_flow").glob("*.json"))
        record = json.loads(flow.read_text())
        for row in record["body"]["data"]:
            row["net_foreign_inflow"] = 1e308
        flow.write_text(json.dumps(record))
        html, _ = self.build()
        self.assertIn("Latest close Unavailable", text_of(html))
        self.assertNotIn("IDR inf", text_of(html))
        self.assertIn("Net foreign flow Incomplete", text_of(html))

    def test_empty_financials_keep_the_accounting_blocker(self) -> None:
        self.probe(FakeTransport(TODAY))
        capture = next((self.cache / "captures" / "BBCA" / "quarterly_financials").glob("*.json"))
        record = json.loads(capture.read_text())
        record["body"] = []
        capture.write_text(json.dumps(record))
        html, _ = self.build()
        self.assertIn("Accounting No quarterly report was returned", text_of(html))

    def test_snapshot_output_never_contains_the_key(self) -> None:
        self.probe(FakeTransport(TODAY))
        self.build()
        for path in self.out.rglob("*"):
            self.assertNotIn(API_KEY, path.read_text())

    def test_text_from_provider_is_escaped(self) -> None:
        self.probe(FakeTransport(TODAY))
        capture = next((self.cache / "captures" / "BBCA" / "company_overview").glob("*.json"))
        record = json.loads(capture.read_text())
        record["body"]["company_name"] = "<script>alert(1)</script>"
        capture.write_text(json.dumps(record))
        html, _ = self.build()
        self.assertNotIn("<script>", html)
        self.assertIn("&lt;script&gt;", html)

    def test_uncaptured_company_still_builds_unclassified(self) -> None:
        html, data = self.build()
        self.assertIn("Unclassified", text_of(html))
        self.assertIn("Company overview not captured", text_of(html))
        self.assertEqual(data["coverage"][0]["records"], None)  # type: ignore[index]


if __name__ == "__main__":
    unittest.main()
