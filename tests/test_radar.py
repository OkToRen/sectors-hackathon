import unittest
from typing import Any

from sectors.radar import radar, radar_fields


def page(symbol: str, state: str | None = "Neutral", observed: str | None = "2026-09-30", label: str | None = None,
         stale: bool = False, previous: str | None = None, blockers: list[str] | None = None,
         available: bool = True) -> dict[str, Any]:
    return {"symbol": symbol, "company_name": f"{symbol} Tbk", "sector": "Energy", "state": state,
            "state_availability_date": observed, "stale": stale,
            "previous_state": None if previous is None else {"state": previous, "period": "2026-03-31"},
            "pattern_update": None if state is None else {"available": available, "label": label},
            "availability": {"date": observed, "estimated": True, "next_report_overdue": stale},
            "blockers": [{"topic": topic, "detail": f"{topic} detail"} for topic in blockers or []]}


class RadarTest(unittest.TestCase):
    def test_orders_by_observation_date_then_pattern_movement_then_ticker(self) -> None:
        result = radar([
            page("BBBB", observed="2026-09-30", label="Stable"),
            page("AAAA", observed="2026-09-30", label="Stable"),
            page("CCCC", observed="2026-09-30", label="Contradicting"),
            page("DDDD", observed="2026-10-31", label=None),
            page("EEEE", observed="2026-09-30", label="Mixed"),
        ])
        self.assertEqual([row.symbol for row in result.ranked], ["DDDD", "CCCC", "EEEE", "AAAA", "BBBB"])

    def test_stale_and_unclassified_are_excluded_and_counted_with_reasons(self) -> None:
        result = radar([
            page("AAAA"),
            page("BBBB", stale=True),
            page("CCCC", state=None, observed=None, blockers=["Accounting", "Price"]),
            page("DDDD", state=None, observed=None, blockers=["Accounting"]),
            page("EEEE", state=None, observed=None, blockers=["Flow"]),
        ])
        self.assertEqual([row.symbol for row in result.ranked], ["AAAA"])
        self.assertEqual(result.stale, ["BBBB"])
        self.assertEqual(result.unclassified, {"Accounting": ["CCCC", "DDDD"], "Flow": ["EEEE"]})

    def test_a_first_recorded_state_is_a_transition_from_nothing(self) -> None:
        first, changed = radar([page("AAAA", state="Confirmed Strength"),
                                page("BBBB", state="Early Deterioration", previous="Neutral")]).ranked
        self.assertEqual((first.previous_state, first.state), (None, "Confirmed Strength"))
        self.assertEqual((changed.previous_state, changed.state), ("Neutral", "Early Deterioration"))

    def test_cards_mark_estimated_dates_and_unavailable_updates(self) -> None:
        html = radar_fields(radar([page("AAAA"), page("BBBB", available=False), page("CCCC", stale=True)]), 3)
        self.assertIn("Public 2026-09-30 (estimated) · raw changes only", html["radar_rows"])
        self.assertIn("Public 2026-09-30 (estimated) · Pattern Update unavailable", html["radar_rows"])
        self.assertIn("Stale, 1: next report overdue, estimated (CCCC)", html["radar_excluded"])


if __name__ == "__main__":
    unittest.main()
