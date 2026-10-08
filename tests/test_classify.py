import unittest
from datetime import date, timedelta

from sectors.classify import CompanyInputs, classify_roster, snapshot_measures
from sectors.earnings import ComparableEarnings
from sectors.state import Band

FIRST = date(2026, 6, 1)
CALENDAR = [(FIRST + timedelta(days=i)).isoformat() for i in range(130)]


def rows(step: float, flow: float, days: int = 130) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    prices = [{"date": (FIRST + timedelta(days=i)).isoformat(), "close": 100 + step * i,
               "market_cap": (100 + step * i) * 1000} for i in range(days)]
    flows = [{"date": r["date"], "net_foreign_inflow": flow} for r in prices]
    return prices, flows


def company(growth: float | None, step: float, flow: float, sector: str = "Energy") -> CompanyInputs:
    earnings = ComparableEarnings("growth" if growth is not None else "basis_unverified", "2026-06-30",
                                  "2025-06-30", 1, 1, growth)
    prices, flows = rows(step, flow)
    return CompanyInputs(sector, earnings, prices, flows)


class ClassifyRosterTest(unittest.TestCase):
    def roster(self) -> dict[str, CompanyInputs]:
        return {"AAAA": company(0.50, 0.10, 0.0), "BBBB": company(0.02, 0.05, 50.0),
                "CCCC": company(-0.40, 0.30, 500.0), "DDDD": company(0.10, 0.05, -20.0),
                "EEEE": company(-0.05, 0.02, 5.0), "FFFF": company(0.30, 0.00, 1.0),
                "GGGG": company(None, 0.04, 10.0)}

    def test_states_use_bands_calibrated_across_the_roster(self) -> None:
        result = classify_roster(self.roster(), date(2026, 10, 6), calendar=CALENDAR)
        self.assertEqual([b.population if b else None for b in (result.bands["fundamentals"], result.bands["price"])],
                         [6, 7])
        crowded = result.companies["CCCC"]
        self.assertEqual((crowded.labels, crowded.state),
                         ({"fundamentals": "Weakening", "price": "Leading", "flow": "Accumulating"},
                          "Crowded Optimism"))
        self.assertEqual(crowded.availability_date, "2026-09-30")
        self.assertFalse(crowded.overdue)

    def test_a_missing_dimension_is_unclassified_with_usable_dimensions_kept(self) -> None:
        unverified = classify_roster(self.roster(), date(2026, 10, 6), calendar=CALENDAR).companies["GGGG"]
        self.assertIsNone(unverified.state)
        self.assertIsNone(unverified.labels["fundamentals"])
        self.assertIsNotNone(unverified.labels["price"])
        self.assertIn("fundamentals", " ".join(unverified.reasons).lower())

    def test_a_sector_with_five_eligible_peers_is_its_own_reference(self) -> None:
        roster = self.roster()
        roster["HHHH"] = company(0.20, 0.10, 0.0, sector="Financials")
        energy = classify_roster(roster, date(2026, 10, 6), calendar=CALENDAR).companies["AAAA"]
        self.assertEqual((energy.price.peers, energy.price.reference), (6, "sector"))

    def test_a_sector_with_too_few_eligible_peers_is_measured_against_the_roster(self) -> None:
        roster = self.roster()
        roster["HHHH"] = company(0.20, 0.10, 0.0, sector="Financials")
        lonely = classify_roster(roster, date(2026, 10, 6), calendar=CALENDAR).companies["HHHH"]
        self.assertEqual((lonely.price.peers, lonely.price.reference), (7, "roster"))
        self.assertAlmostEqual(lonely.price.value or 0, 0.0274383426)

    def test_pattern_update_measures_price_against_the_recorded_reference_only(self) -> None:
        roster = self.roster()
        roster["HHHH"] = company(0.20, 0.10, 0.0, sector="Financials")
        now = snapshot_measures(roster, date(2026, 9, 30), CALENDAR, {"HHHH": "roster", "AAAA": "roster"})
        self.assertEqual(set(now), {"HHHH", "AAAA"})
        self.assertEqual((now["HHHH"]["price"].reference, now["AAAA"]["price"].reference), ("roster", "roster"))
        self.assertAlmostEqual(now["AAAA"]["price"].value or 0, 0.0274383426)
        pinned = snapshot_measures(roster, date(2026, 9, 30), CALENDAR, {"HHHH": "sector"})["HHHH"]["price"]
        self.assertEqual((pinned.value, pinned.reference), (None, None))

    def test_an_overdue_next_report_is_flagged_separately(self) -> None:
        roster = self.roster()
        old = roster["AAAA"]
        roster["AAAA"] = CompanyInputs(old.sector, ComparableEarnings("growth", "2026-03-31", "2025-03-31", 1, 1, 0.5),
                                       old.prices, old.flows)
        self.assertTrue(classify_roster(roster, date(2026, 10, 6), calendar=CALENDAR).companies["AAAA"].overdue)

    def test_frozen_bands_are_used_instead_of_recalibrating(self) -> None:
        frozen = {"fundamentals": Band(0.9, 30), "price": Band(0.9, 30), "flow": Band(0.9, 30)}
        result = classify_roster(self.roster(), date(2026, 10, 6), frozen, CALENDAR)
        self.assertEqual(result.bands, frozen)
        self.assertEqual(result.companies["CCCC"].labels, {"fundamentals": "Flat", "price": "Flat", "flow": "Neutral"})

    def test_a_report_is_not_classified_before_its_estimated_availability(self) -> None:
        early = classify_roster(self.roster(), date(2026, 9, 29), calendar=CALENDAR).companies["CCCC"]
        self.assertEqual((early.state, early.labels["price"]), (None, None))
        self.assertIn("not yet available", " ".join(early.reasons))

    def test_a_trading_day_missing_for_every_member_blocks_the_windows(self) -> None:
        roster = {symbol: CompanyInputs(c.sector, c.earnings, [r for r in c.prices if r["date"] != "2026-09-10"],
                                        [r for r in c.flows if r["date"] != "2026-09-10"])
                  for symbol, c in self.roster().items()}
        crowded = classify_roster(roster, date(2026, 10, 6), calendar=CALENDAR).companies["CCCC"]
        self.assertIsNone(crowded.state)
        self.assertIn("2026-09-10", " ".join(crowded.reasons))

    def test_a_window_in_a_year_without_a_holiday_list_is_blocked(self) -> None:
        roster = {symbol: CompanyInputs(c.sector, ComparableEarnings("growth", "2026-12-31", "2025-12-31", 1, 1,
                                                                     c.earnings.growth), c.prices, c.flows)
                  for symbol, c in self.roster().items()}
        late = classify_roster(roster, date(2027, 4, 1), calendar=CALENDAR).companies["CCCC"]
        self.assertIsNone(late.state)
        self.assertIn("2027", " ".join(late.reasons))


if __name__ == "__main__":
    unittest.main()
