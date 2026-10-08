import json
import shutil
from dataclasses import replace
import re
import tempfile
import unittest
from datetime import UTC, date, datetime
from pathlib import Path

from sectors.api import DAILY_PRICES, FOREIGN_FLOW
from sectors.freeze import write_freeze
from sectors.probe import PlannedRequest, ProbeLimits, execute
from sectors.state import Band
from sectors.roster import run_roster
from sectors.snapshot import build_roster
from tests.fakes import API_KEY, FakeTransport, verified_fake_basis

TODAY = date(2026, 10, 6)
PROBED = datetime(2026, 10, 6, 3, 0, tzinfo=UTC)
GENERATED = datetime(2026, 10, 6, 5, 30, tzinfo=UTC)
TEMPLATE_DIR = Path(__file__).resolve().parents[1] / "app"


class RosterBuildTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.cache, self.out = root / "cache", root / "dist"

        self.checks = verified_fake_basis()
        research = root / "research"
        research.mkdir()
        shutil.copy(TEMPLATE_DIR.parent / "research" / "idx_holidays_2026.csv", research)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def probe(self, roster: tuple[str, ...], failures: dict[str, int] | None = None) -> None:
        """The roster probe plus the earlier window that reaches back past the 30 September availability date."""
        run_roster(self.cache, FakeTransport(TODAY, roster=roster, failures=failures), API_KEY,
                   ProbeLimits(500, 400), clock=lambda: PROBED)
        window = (("start", "2026-06-01"), ("end", "2026-07-10"))
        earlier = [(s, PlannedRequest(e, e.path.format(symbol=s), window, 1))
                   for e in (DAILY_PRICES, FOREIGN_FLOW) for s in roster]
        execute(earlier, self.cache, FakeTransport(date(2026, 7, 10), failures=failures), API_KEY,
                ProbeLimits(500, 400), clock=lambda: PROBED)

    def build(self, roster: tuple[str, ...], failures: dict[str, int] | None = None) -> dict[str, dict[str, object]]:
        self.probe(roster, failures)
        build_roster(self.cache, self.out, TEMPLATE_DIR, now=GENERATED, checks=self.checks)
        return {symbol: json.loads((self.out / f"{symbol}.json").read_text()) for symbol in roster}

    def test_five_eligible_sector_peers_clear_the_peer_blocker(self) -> None:
        pages = self.build(("BBCA", "BBNI", "BBRI", "BBTN", "BMRI", "BRIS"))
        self.assertEqual(pages["BBCA"]["price_peers"], 5)
        self.assertNotIn("Price", [b["topic"] for b in pages["BBCA"]["blockers"]])  # type: ignore[attr-defined]
        html = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", (self.out / "BBCA.html").read_text()))
        self.assertIn("Sector peers 5 of at least 5 Financials", html)
        self.assertEqual(pages["BBCA"]["peer_reference"], "sector")

    def test_peers_need_usable_closes_on_the_same_dates(self) -> None:
        roster = ("BBCA", "BBNI", "BBRI", "BBTN", "BMRI", "BRIS")
        self.probe(roster)
        for symbol, change in (("BBNI", "no closes"), ("BBRI", "other dates"), ("BBTN", "negative closes")):
            for capture in (self.cache / "captures" / symbol / "daily_prices").glob("*.json"):
                record = json.loads(capture.read_text())
                for row in record["body"]:
                    if change == "no closes":
                        row["close"] = None
                    elif change == "negative closes":
                        row["close"] = -9000
                    else:
                        row["date"] = row["date"].replace("2026-", "2025-")
                capture.write_text(json.dumps(record))
        build_roster(self.cache, self.out, TEMPLATE_DIR, now=GENERATED, checks=self.checks)
        page = json.loads((self.out / "BBCA.json").read_text())
        self.assertEqual(page["price_peers"], 2)

    def test_without_a_freeze_calibratable_bands_are_not_published(self) -> None:
        roster = ("BBCA", "BBNI", "BBRI", "BBTN", "BMRI", "BRIS")
        fake = verified_fake_basis()["BBCA"]
        self.checks = {symbol: replace(fake, symbol=symbol) for symbol in roster}
        pages = self.build(roster)
        dimensions = pages["BBCA"]["dimensions"]
        assert isinstance(dimensions, dict)
        self.assertIsNone(dimensions["fundamentals"]["band"])
        self.assertIsNotNone(dimensions["fundamentals"]["value"])
        self.assertIsNone(pages["BBCA"]["state"])

    def freeze(self, bands: dict[str, Band | None]) -> None:
        research = self.cache.parent / "research"
        (research / "candidate_signals.yaml").write_text("version: test\n")
        write_freeze(bands, research / "candidate_signals.yaml", research / "bands_freeze.json", PROBED)

    def test_a_recorded_state_survives_rebuilds_and_data_revisions(self) -> None:
        roster = ("BBCA", "BBNI", "BBRI", "BBTN", "BMRI", "BRIS")
        self.checks = {symbol: replace(verified_fake_basis()["BBCA"], symbol=symbol) for symbol in roster}
        self.freeze({"fundamentals": Band(0.05, 6), "price": Band(0.01, 6), "flow": Band(0.0001, 6)})
        first = self.build(roster)["BBCA"]
        self.assertIsNotNone(first["state"])
        self.assertIsNone(first["previous_state"])
        page = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", (self.out / "BBCA.html").read_text()))
        self.assertIn("Earnings +8.8% against the same quarter a year earlier", page)
        self.assertIn("Revenue +15.4% on the same comparison, which supports the earnings direction", page)
        self.assertIn("Previous state: unavailable; no earlier quarter has a recorded state.", page)
        for capture in (self.cache / "captures" / "BBCA" / "daily_prices").glob("*.json"):
            record = json.loads(capture.read_text())
            for row in record["body"]:
                row["close"] = float(row["close"]) * (1.5 if row["date"] > "2026-08-01" else 1.0)
            capture.write_text(json.dumps(record))
        build_roster(self.cache, self.out, TEMPLATE_DIR, now=GENERATED, checks=self.checks)
        again = json.loads((self.out / "BBCA.json").read_text())
        self.assertEqual((again["state"], again["dimensions"]), (first["state"], first["dimensions"]))
        recorded = json.loads((self.cache.parent / "research" / "state_assignments.json").read_text())
        self.assertEqual(len(recorded), 6)

    def classified_roster(self) -> tuple[tuple[str, ...], dict[str, object]]:
        roster = ("BBCA", "BBNI", "BBRI", "BBTN", "BMRI", "BRIS")
        self.checks = {symbol: replace(verified_fake_basis()["BBCA"], symbol=symbol) for symbol in roster}
        self.freeze({"fundamentals": Band(0.05, 6), "price": Band(0.01, 6), "flow": Band(0.0001, 6)})
        return roster, self.build(roster)["BBCA"]

    def rebuild(self, now: datetime) -> dict[str, object]:
        build_roster(self.cache, self.out, TEMPLATE_DIR, now=now, checks=self.checks)
        page: dict[str, object] = json.loads((self.out / "BBCA.json").read_text())
        return page

    def test_a_classified_member_shows_its_pattern_update(self) -> None:
        _, first = self.classified_roster()
        update = first["pattern_update"]
        assert isinstance(update, dict)
        self.assertEqual(update["as_of"], "2026-10-06")
        self.assertTrue(update["available"])
        page = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", (self.out / "BBCA.html").read_text()))
        self.assertIn("Pattern Update since 2026-09-30", page)
        roster = json.loads((self.out / "roster.json").read_text())
        self.assertTrue(next(m for m in roster["members"] if m["symbol"] == "BBCA")["ranked"])

    def test_a_classified_member_says_nothing_blocks_it(self) -> None:
        _, first = self.classified_roster()
        self.assertEqual(first["blockers"], [])
        html = (self.out / "BBCA.html").read_text()
        self.assertIn('<ul class="checklist"><li><strong>None</strong><span>Every input classification needs was '
                      'available and passed its checks.</span></li></ul>', html)

    def test_an_update_needs_market_data_after_the_assignment(self) -> None:
        self.classified_roster()
        same_day = self.rebuild(datetime(2026, 9, 30, 12, 0, tzinfo=UTC))
        update = same_day["pattern_update"]
        assert isinstance(update, dict)
        self.assertEqual((update["available"], update["label"]), (False, None))

    def test_an_unusable_newer_report_keeps_the_dated_state_and_marks_it_stale(self) -> None:
        _, first = self.classified_roster()
        capture = next((self.cache / "captures" / "BBCA" / "quarterly_financials").glob("*.json"))
        record = json.loads(capture.read_text())
        record["body"].append({"symbol": "BBCA.JK", "date": "2026-09-30", "revenue": 1, "earnings": 1})
        capture.write_text(json.dumps(record))
        later = self.rebuild(datetime(2027, 1, 2, 3, 0, tzinfo=UTC))
        self.assertEqual((later["state"], later["state_period"], later["stale"]),
                         (first["state"], "2026-06-30", True))
        page = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", (self.out / "BBCA.html").read_text()))
        self.assertIn("Earnings +8.8% against the same quarter a year earlier (2026-06-30 vs 2025-06-30)", page)
        self.assertIn("over the 60 trading days to 2026-09-30", page)
        self.assertIn("Revenue +15.4% on the same comparison, which supports the earnings direction", page)
        roster = json.loads((self.out / "roster.json").read_text())
        member = next(m for m in roster["members"] if m["symbol"] == "BBCA")
        self.assertEqual((member["stale"], member["ranked"]), (True, False))
        assert isinstance(later["pattern_update"], dict)
        self.assertTrue(later["pattern_update"]["available"])
        index = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", (self.out / "index.html").read_text()))
        self.assertIn("stale", index)

    def test_a_recorded_state_is_not_shown_before_its_availability_date(self) -> None:
        self.classified_roster()
        early = self.rebuild(datetime(2026, 9, 29, 3, 0, tzinfo=UTC))
        self.assertIsNone(early["state"])

    def test_a_recorded_state_keeps_the_bands_it_was_assigned_under(self) -> None:
        _, first = self.classified_roster()
        self.freeze({"fundamentals": Band(0.9, 6), "price": Band(0.9, 6), "flow": Band(0.9, 6)})
        again = self.rebuild(GENERATED)
        self.assertEqual(again["dimensions"], first["dimensions"])
        self.assertEqual(again["pattern_update"], first["pattern_update"])

    def test_fewer_peers_or_peers_without_prices_keep_the_blocker(self) -> None:
        pages = self.build(("BBCA", "BBNI", "BBRI"))
        blockers = pages["BBCA"]["blockers"]
        assert isinstance(blockers, list)
        self.assertIn({"topic": "Price", "detail": "2 sector peers and 2 other roster members have usable closes on "
                       "the same dates; at least 5 are needed."}, blockers)

    def test_a_thin_sector_is_measured_and_recorded_against_the_roster(self) -> None:
        roster = ("BBCA", "BBNI", "BBRI", "BBTN", "BMRI", "BRIS")
        self.checks = {symbol: replace(verified_fake_basis()["BBCA"], symbol=symbol) for symbol in roster}
        self.freeze({"fundamentals": Band(0.05, 6), "price": Band(0.01, 6), "flow": Band(0.0001, 6)})
        self.probe(roster)
        for symbol in ("BMRI", "BRIS"):
            for capture in (self.cache / "captures" / symbol / "company_overview").glob("*.json"):
                record = json.loads(capture.read_text())
                record["body"]["overview"]["sector"] = "Energy"
                capture.write_text(json.dumps(record))
        build_roster(self.cache, self.out, TEMPLATE_DIR, now=GENERATED, checks=self.checks)
        page = json.loads((self.out / "BBCA.json").read_text())
        self.assertEqual((page["price_peers"], page["peer_reference"], page["price_reference"]), (5, "roster", "roster"))
        self.assertIsNotNone(page["state"])
        self.assertTrue(page["pattern_update"]["available"])
        recorded = json.loads((self.cache.parent / "research" / "state_assignments.json").read_text())
        self.assertEqual(next(a for a in recorded if a["symbol"] == "BBCA")["references"], {"price": "roster"})
        html = self.text("BBCA.html")
        self.assertIn("LQ45 peers 5 other LQ45 members, because Financials has fewer than 5 eligible sector peers",
                      html)
        self.assertIn("Price vs LQ45", html)
        self.assertIn("the LQ45 median", html)
        self.assertIn("Since then price relative to LQ45 moved", html)
        member = next(m for m in json.loads((self.out / "roster.json").read_text())["members"]
                      if m["symbol"] == "BBCA")
        self.assertEqual((member["eligible_peers"], member["peer_reference"]), (5, "roster"))
        self.assertIn("5 LQ45", self.text("index.html"))

    def test_index_lists_every_member_with_a_link_even_when_unavailable(self) -> None:
        self.build(("BBCA", "BBRI"), failures={"/daily/": 404})
        page = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", (self.out / "index.html").read_text()))
        self.assertIn('href="BBRI.html"', (self.out / "index.html").read_text())
        self.assertIn("BBCA PT BBCA Tbk", page.replace("PT Bank Central Asia Tbk.", "PT BBCA Tbk"))
        self.assertIn("+8.8% vs 2025-06-30", page)
        self.assertIn("1 source(s) unavailable", page)
        self.assertIn("Roster captured 2026-10-06 03:00 UTC · sectors from company overviews retrieved "
                      "2026-10-06 03:00 UTC", page)
        roster = json.loads((self.out / "roster.json").read_text())
        self.assertEqual(roster["roster_retrieved_at"], "2026-10-06T03:00:00+00:00")
        self.assertEqual([m["symbol"] for m in roster["members"]], ["BBCA", "BBRI"])

    def text(self, name: str) -> str:
        return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", (self.out / name).read_text()))

    def test_radar_leads_with_transitions_linked_to_company_views(self) -> None:
        _, first = self.classified_roster()
        html = (self.out / "index.html").read_text()
        page = self.text("index.html")
        self.assertIn("Snapshot generated", page)
        self.assertIn("6 of 6 members ranked", page)
        self.assertIn(f"BBCA {first['state']} First recorded state Public 2026-09-30 (estimated)", page)
        self.assertLess(html.index('id="radar-title"'), html.index('id="members-title"'))
        self.assertIn('href="BBCA.html"', html)

    def test_radar_counts_unclassified_members_with_their_reasons(self) -> None:
        self.build(("BBCA", "BBRI"))
        page = self.text("index.html")
        self.assertIn("0 of 2 members ranked", page)
        self.assertIn("Unclassified, 1: Accounting (BBRI) Unclassified, 1: Price (BBCA)", page)

    def test_methodology_publishes_frozen_bands_and_every_v5_topic(self) -> None:
        self.classified_roster()
        page = self.text("methodology.html")
        self.assertIn("Price ±1.00% from 6 roster values", page)
        self.assertIn("Foreign flow ±0.01% from 6 roster values", page)
        self.assertIn("Frozen 2026-10-06 03:00 UTC", page)
        self.assertIn("Retrospective research using available historical records; original availability and "
                      "revisions are not fully verified.", page)
        for topic in ("Source coverage", "Publication and vintage limits", "Current-universe selection",
                      "Accounting and return conventions", "Neutral bands", "State mappings",
                      "Pattern Update", "Split and freeze", "Completed outcomes", "Reference comparisons",
                      "Composition", "Uncertainty", "Signal log"):
            self.assertIn(f'<h2 id="', (self.out / "methodology.html").read_text())
            self.assertIn(topic, page)
        self.assertIn('href="methodology.html"', (self.out / "index.html").read_text())

    def test_no_page_recommends_and_statistics_stay_on_methodology(self) -> None:
        self.classified_roster()
        advice = re.compile(r"\b(buy|sell|attractive|avoid|recommend\w*|undervalued|opportunit\w*)\b", re.I)
        statistics = re.compile(r"\b(percentile|quantile|significan\w*|confidence|p-value|standard deviation)\b",
                                re.I)
        for path in self.out.glob("*.html"):
            text = self.text(path.name)
            self.assertIsNone(advice.search(text), path.name)
            if path.name != "methodology.html":
                self.assertIsNone(statistics.search(text), path.name)
        self.assertIsNotNone(statistics.search(self.text("methodology.html")))


if __name__ == "__main__":
    unittest.main()
