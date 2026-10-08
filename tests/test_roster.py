import tempfile
import unittest
from datetime import UTC, date, datetime
from pathlib import Path

from sectors.api import COMPANIES
from sectors.probe import ProbeLimits
from sectors.roster import members, run_roster
from tests.fakes import API_KEY, FakeTransport

TODAY = date(2026, 10, 6)
NOW = datetime(2026, 10, 6, 3, 0, tzinfo=UTC)


class RosterTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.cache = Path(self.tmp.name) / "cache"

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def roster(self, transport: FakeTransport | None, run_cap: int = 40) -> list[tuple[str, str, str]]:
        report = run_roster(self.cache, transport, API_KEY, ProbeLimits(100, run_cap), clock=lambda: NOW)
        return [(r.owner, r.endpoint, r.status) for r in report.results]

    def test_dry_run_without_a_roster_plans_only_the_roster_lookup(self) -> None:
        self.assertEqual(self.roster(None), [("LQ45", "companies", "planned")])
        self.assertIsNone(members(self.cache))

    def test_live_run_captures_the_roster_then_every_member(self) -> None:
        transport = FakeTransport(TODAY)
        results = self.roster(transport)
        self.assertEqual(results[0], ("LQ45", "companies", "fetched"))
        self.assertEqual({owner for owner, _, status in results[1:] if status == "fetched"}, {"BBCA", "BBRI"})
        self.assertEqual(len(transport.calls), 9)
        self.assertEqual(members(self.cache), ["BBCA", "BBRI"])

    def test_dry_run_after_the_roster_plans_each_member_without_requests(self) -> None:
        self.roster(FakeTransport(TODAY, roster=("BBCA",)), run_cap=1)
        results = self.roster(None)
        self.assertEqual(results[0], ("LQ45", "companies", "reused"))
        self.assertEqual([status for owner, _, status in results if owner == "BBCA"], ["planned"] * 4)

    def test_members_beyond_the_run_cap_stay_listed_as_skipped(self) -> None:
        results = self.roster(FakeTransport(TODAY), run_cap=9)
        self.assertEqual([status for owner, _, status in results if owner == "BBRI"], ["skipped"] * 4)

    def test_members_stay_listed_when_the_roster_lookup_uses_the_whole_cap(self) -> None:
        results = self.roster(FakeTransport(TODAY), run_cap=1)
        self.assertEqual({owner for owner, _, status in results if status == "skipped"}, {"BBCA", "BBRI"})

    def test_dry_run_totals_include_the_planned_roster_refresh(self) -> None:
        self.roster(FakeTransport(TODAY, roster=("BBCA",)))
        later = datetime(2026, 10, 7, 3, 0, tzinfo=UTC)
        report = run_roster(self.cache, None, API_KEY, ProbeLimits(100, 40), clock=lambda: later)
        self.assertEqual(report.counted_this_run, 9)
        self.assertEqual(report.counted_total, 9 + 9)

    def test_a_rate_limited_roster_lookup_stops_the_member_probes(self) -> None:
        self.roster(FakeTransport(TODAY, roster=("BBCA",)))
        limited = FakeTransport(date(2026, 10, 7), failures={"/v2/companies/": 429})
        report = run_roster(self.cache, limited, API_KEY, ProbeLimits(100, 40),
                            clock=lambda: datetime(2026, 10, 7, 3, 0, tzinfo=UTC))
        self.assertEqual(len(limited.calls), 1)
        self.assertEqual({r.status for r in report.results[1:]}, {"skipped"})

    def test_incomplete_or_malformed_rosters_are_unusable(self) -> None:
        bodies = [
            {"pagination": {"has_next": True, "total_count": 45}, "results": [{"symbol": "BBCA.JK"}]},
            {"pagination": {"has_next": False, "total_count": 1}, "results": [{"symbol": "../oops"}]},
            {"pagination": {"has_next": False, "total_count": 2}, "results": [{"symbol": "BBCA"}, {"symbol": "BBCA.JK"}]},
            {"results": [{"symbol": "BBCA.JK"}]},
        ]
        for body in bodies:
            with self.subTest(body=body):
                self.assertFalse(COMPANIES.shape_ok(body))
        self.assertTrue(COMPANIES.shape_ok(
            {"pagination": {"has_next": False, "total_count": 2}, "results": [{"symbol": "BBCA.JK"}, {"symbol": "BBRI.JK"}]}))


if __name__ == "__main__":
    unittest.main()
