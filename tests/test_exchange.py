import tempfile
import unittest
from datetime import date
from pathlib import Path

from sectors.exchange import trading_calendar

REAL = Path(__file__).resolve().parents[1] / "research" / "idx_holidays_2026.csv"


class TradingCalendarTest(unittest.TestCase):
    def test_2026_has_239_trading_days(self) -> None:
        self.assertEqual(len(trading_calendar(REAL, date(2026, 12, 31))), 239)

    def test_weekends_and_holidays_are_not_trading_days(self) -> None:
        days = trading_calendar(REAL, date(2026, 8, 31))
        for closed in ("2026-08-17", "2026-08-25", "2026-06-01", "2026-08-15"):
            self.assertNotIn(closed, days)
        self.assertIn("2026-08-18", days)
        self.assertEqual(days[-1], "2026-08-31")

    def test_years_without_a_holiday_list_are_not_covered(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(trading_calendar(Path(tmp) / "missing.csv", date(2026, 12, 31)), [])
        self.assertTrue(all(day.startswith("2026") for day in trading_calendar(REAL, date(2027, 3, 1))))


if __name__ == "__main__":
    unittest.main()
