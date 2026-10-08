import itertools
import unittest
from datetime import date, timedelta

from sectors.state import (Band, availability_date, band, categorize, corporate_action, flow_measure,
                           next_report_overdue, price_measure, state_for)


def closes(start: float, step: float, days: int = 61, first: date = date(2026, 6, 1),
           shares: float = 100.0) -> list[dict[str, object]]:
    return [{"date": (first + timedelta(days=i)).isoformat(), "close": start + step * i,
             "market_cap": (start + step * i) * shares} for i in range(days)]


class StateMappingTest(unittest.TestCase):
    def test_every_combination_maps_to_exactly_one_state(self) -> None:
        expected = {
            ("Improving", "Flat", "Neutral"): "Ignored Improvement",
            ("Improving", "Lagging", "Accumulating"): "Ignored Improvement",
            ("Improving", "Leading", "Accumulating"): "Confirmed Strength",
            ("Weakening", "Leading", "Accumulating"): "Crowded Optimism",
            ("Weakening", "Flat", "Distributing"): "Early Deterioration",
            ("Weakening", "Leading", "Neutral"): "Early Deterioration",
            ("Improving", "Leading", "Neutral"): "Neutral",
            ("Flat", "Leading", "Accumulating"): "Neutral",
            ("Weakening", "Lagging", "Distributing"): "Neutral",
        }
        for combo, name in expected.items():
            with self.subTest(combo=combo):
                self.assertEqual(state_for(*combo), name)
        names = {state_for(*combo) for combo in itertools.product(
            ("Improving", "Flat", "Weakening"), ("Leading", "Flat", "Lagging"),
            ("Accumulating", "Neutral", "Distributing"))}
        self.assertEqual(names, {"Ignored Improvement", "Confirmed Strength", "Crowded Optimism",
                                 "Early Deterioration", "Neutral"})


class BandTest(unittest.TestCase):
    def test_band_is_the_25th_percentile_of_absolute_values(self) -> None:
        self.assertEqual(band([-5.0, 1.0, -2.0, 3.0, 4.0]), Band(2.0, 5))

    def test_too_few_values_or_a_zero_band_block_the_dimension(self) -> None:
        self.assertIsNone(band([1.0, 2.0, 3.0, 4.0]))
        self.assertIsNone(band([0.0, 0.0, 0.0, 0.0, 5.0]))

    def test_boundaries_are_neutral(self) -> None:
        b = Band(0.1, 5)
        self.assertEqual([categorize(v, b) for v in (0.11, 0.1, 0.0, -0.1, -0.11)],
                         ["positive", "neutral", "neutral", "neutral", "negative"])


def calendar_of(rows: list[dict[str, object]]) -> list[str]:
    return sorted(str(r["date"]) for r in rows)


class MeasureTest(unittest.TestCase):
    def test_availability_is_three_calendar_months_after_period_end(self) -> None:
        self.assertEqual(availability_date("2026-06-30"), date(2026, 9, 30))
        self.assertEqual(availability_date("2025-12-31"), date(2026, 3, 31))
        self.assertEqual(availability_date("2026-03-31"), date(2026, 6, 30))

    def test_next_report_is_overdue_after_its_estimated_availability(self) -> None:
        self.assertTrue(next_report_overdue("2026-03-31", date(2026, 10, 6)))
        self.assertFalse(next_report_overdue("2026-06-30", date(2026, 10, 6)))

    def test_price_is_return_less_the_median_peer_return_over_the_same_dates(self) -> None:
        subject = closes(100, 0.5)  # 100 -> 130
        peers = {f"P{i}": closes(100, 0.1 * i) for i in range(1, 6)}  # medians at P3: 100 -> 118
        others = {f"Q{i}": closes(100, 0.9) for i in range(1, 6)}
        measure = price_measure(subject, peers, peers | others, date(2026, 7, 31), calendar_of(subject))
        self.assertEqual(measure.reason, "")
        self.assertAlmostEqual(measure.value or 0, 0.30 - 0.18)
        self.assertEqual((measure.peers, measure.reference), (5, "sector"))

    def test_fewer_than_five_sector_peers_fall_back_to_the_roster_median(self) -> None:
        subject = closes(100, 0.5)  # 100 -> 130
        sector = {f"P{i}": closes(100, 0.1 * i) for i in range(1, 5)}  # 6%, 12%, 18%, 24%
        roster = sector | {f"Q{i}": closes(100, 0.1 * i) for i in range(6, 9)}  # 36%, 42%, 48%
        measure = price_measure(subject, sector, roster, date(2026, 7, 31), calendar_of(subject))
        self.assertAlmostEqual(measure.value or 0, 0.30 - 0.24)
        self.assertEqual((measure.reason, measure.peers, measure.reference), ("", 7, "roster"))

    def test_fewer_than_five_peers_in_sector_and_roster_block_price(self) -> None:
        subject = closes(100, 0.5)
        sector = {f"P{i}": closes(100, 0.1) for i in range(1, 3)}
        roster = sector | {f"Q{i}": closes(100, 0.1) for i in range(1, 3)}
        measure = price_measure(subject, sector, roster, date(2026, 7, 31), calendar_of(subject))
        self.assertEqual((measure.value, measure.peers, measure.reference), (None, 2, None))
        self.assertEqual(measure.reason, "2 sector peers and 4 other roster members have usable closes on the same "
                                         "dates; at least 5 are needed.")

    def test_price_needs_61_closes_and_five_aligned_peers(self) -> None:
        peers = {f"P{i}": closes(100, 0.1) for i in range(1, 6)}
        calendar = calendar_of(closes(100, 0.5))
        self.assertIsNone(price_measure(closes(100, 0.5, days=60), peers, {}, date(2026, 7, 31), calendar).value)
        shifted = {name: closes(100, 0.1, first=date(2026, 6, 2)) for name in peers}
        short = price_measure(closes(100, 0.5), shifted, {}, date(2026, 7, 31), calendar)
        self.assertEqual((short.value, short.peers), (None, 0))

    def test_a_corporate_action_in_the_window_blocks_price(self) -> None:
        split = closes(100, 0.0)
        for row in split[30:]:
            row["close"], row["market_cap"] = 50.0, 50.0 * 100
        self.assertEqual(corporate_action(split), split[30]["date"])
        issue = closes(100, 0.0)
        for i, row in enumerate(issue[40:]):
            row["close"], row["market_cap"] = 99.0, 99.0 * 120
        self.assertEqual(corporate_action(issue), issue[40]["date"])
        self.assertIsNone(corporate_action(closes(100, 0.5)))
        flat_day = closes(100, 0.0)
        for row in flat_day[40:]:
            row["market_cap"] = 100.0 * 80  # a share change on a flat day could hide a consolidation
        self.assertEqual(corporate_action(flat_day), flat_day[40]["date"])
        peers = {f"P{i}": closes(100, 0.1) for i in range(1, 6)}
        self.assertIn("corporate action", price_measure(split, peers, {}, date(2026, 7, 31), calendar_of(split)).reason)
        consolidated = closes(100, 0.0)
        for row in consolidated[30:]:
            row["close"], row["market_cap"] = 125.0, 100.0 * 100  # five shares into four: price up, cap unchanged
        self.assertEqual(corporate_action(consolidated), consolidated[30]["date"])
        small = closes(100, 0.0)
        for row in small[30:]:
            row["close"], row["market_cap"] = 100 * 25 / 24, 100.0 * 100  # 25 into 24
        self.assertEqual(corporate_action(small), small[30]["date"])
        tiny = closes(100, 0.0)
        for row in tiny[30:]:
            row["close"], row["market_cap"] = 100.5, 100.0 * 100  # 201 into 200
        self.assertEqual(corporate_action(tiny), tiny[30]["date"])
        rounding = closes(100, 0.0)
        for row in rounding[30:]:
            row["close"], row["market_cap"] = 101.0, 101.0 * 100 * (1 + 1e-9)  # float rounding only
        self.assertIsNone(corporate_action(rounding))
        exact = closes(100, 0.0)
        exact[30:] = [{**row, "close": 135.0, "market_cap": 135.0 * 100} for row in exact[30:]]
        self.assertIsNone(corporate_action(exact))
        no_cap = closes(100, 0.0)
        no_cap[30]["market_cap"] = None
        self.assertEqual(corporate_action(no_cap), no_cap[30]["date"])

    def test_flow_is_the_60_day_sum_over_market_cap_at_the_availability_date(self) -> None:
        prices = closes(100, 0.0)
        flows = [{"date": row["date"], "net_foreign_inflow": 10.0} for row in prices]
        calendar = calendar_of(prices)
        measure = flow_measure(flows, prices, date(2026, 7, 31), calendar)
        self.assertAlmostEqual(measure.value or 0, 600.0 / 10000.0)
        flows[-5]["net_foreign_inflow"] = None
        self.assertIsNone(flow_measure(flows, prices, date(2026, 7, 31), calendar).value)

    def test_a_missing_trading_day_blocks_the_window_instead_of_reaching_back(self) -> None:
        prices = closes(100, 0.5, days=62)
        calendar = calendar_of(prices)
        peers = {f"P{i}": closes(100, 0.1, days=62) for i in range(1, 6)}
        gap = [row for i, row in enumerate(prices) if i != 40]
        self.assertIn("no usable close", price_measure(gap, peers, {}, date(2026, 8, 1), calendar).reason)
        flows = [{"date": row["date"], "net_foreign_inflow": 10.0} for i, row in enumerate(prices) if i != 40]
        self.assertIn("no flow", flow_measure(flows, prices, date(2026, 8, 1), calendar).reason)

    def test_a_window_spanning_an_uncovered_year_is_blocked(self) -> None:
        days = [d for d in (date(2024, 12, 1) + timedelta(days=i) for i in range(500)) if d.weekday() < 5]
        calendar = [d.isoformat() for d in days if d.year != 2025]
        prices = [{"date": day, "close": 100.0, "market_cap": 10000.0} for day in calendar]
        peers = {f"P{i}": prices for i in range(5)}
        self.assertIn("2025", price_measure(prices, peers, {}, date(2026, 1, 30), calendar).reason)
        flows = [{"date": day, "net_foreign_inflow": 1.0} for day in calendar]
        self.assertIn("2025", flow_measure(flows, prices, date(2026, 1, 30), calendar).reason)

    def test_flow_needs_market_cap_at_the_latest_close(self) -> None:
        prices = closes(100, 0.0)
        prices[-1]["market_cap"] = None
        flows = [{"date": row["date"], "net_foreign_inflow": 10.0} for row in prices]
        self.assertIn("market cap", flow_measure(flows, prices, date(2026, 7, 31), calendar_of(prices)).reason)


if __name__ == "__main__":
    unittest.main()
