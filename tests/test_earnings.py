import unittest

from sectors.earnings import ComparableEarnings, comparable_earnings


def quarters(latest: object, prior: object) -> list[dict[str, object]]:
    return [{"date": "2025-06-30", "earnings": prior}, {"date": "2025-09-30", "earnings": 5},
            {"date": "2026-06-30", "earnings": latest}]


VERIFIED = {"2025-06-30": 100, "2026-06-30": 110}


class ComparableEarningsTest(unittest.TestCase):
    def condition(self, latest: object, prior: object) -> str:
        return comparable_earnings(quarters(latest, prior), {}).condition

    def test_growth_needs_both_quarters_positive(self) -> None:
        self.assertEqual(comparable_earnings(quarters(110, 100), VERIFIED),
                         ComparableEarnings("growth", "2026-06-30", "2025-06-30", 110, 100, 0.1))

    def test_sign_changes_and_losses_are_named_not_computed(self) -> None:
        self.assertEqual(self.condition(10, -5), "loss_to_profit")
        self.assertEqual(self.condition(-10, 5), "profit_to_loss")
        self.assertEqual(self.condition(-10, -5), "persistent_loss")
        self.assertEqual(self.condition(0, 5), "zero_boundary")
        self.assertEqual(self.condition(5, 0), "zero_boundary")
        self.assertIsNone(comparable_earnings(quarters(10, -5), VERIFIED).growth)

    def test_missing_values_stay_missing(self) -> None:
        self.assertEqual(self.condition(None, 5), "earnings_missing")
        self.assertEqual(self.condition(5, None), "earnings_missing")
        self.assertEqual(comparable_earnings([], VERIFIED).condition, "no_reports")
        only_latest = [{"date": "2026-06-30", "earnings": 5}]
        self.assertEqual(comparable_earnings(only_latest, VERIFIED),
                         ComparableEarnings("prior_not_returned", "2026-06-30", "2025-06-30", 5, None, None))

    def test_growth_needs_both_periods_verified(self) -> None:
        self.assertEqual(comparable_earnings(quarters(110, 100), {"2026-06-30": 110}),
                         ComparableEarnings("basis_unverified", "2026-06-30", "2025-06-30", 110, 100, None))

    def test_sub_rupiah_amounts_are_not_plausible(self) -> None:
        self.assertEqual(comparable_earnings(quarters(10**18, 5e-324), VERIFIED).condition, "earnings_missing")

    def test_verification_binds_the_values_not_just_the_periods(self) -> None:
        self.assertEqual(comparable_earnings(quarters(220, 100), VERIFIED).condition, "basis_unverified")

    def test_growth_for_a_converted_reporter_is_measured_in_its_reporting_currency(self) -> None:
        rates = {"2025-06-30": 16000.0, "2026-06-30": 18000.0}
        self.assertEqual(comparable_earnings(quarters(180_000, 160_000), {"2025-06-30": 160_000,
                                                                          "2026-06-30": 180_000}, rates),
                         ComparableEarnings("growth", "2026-06-30", "2025-06-30", 180_000, 160_000, 0.0))

    def test_a_conversion_rate_must_cover_both_periods(self) -> None:
        self.assertEqual(comparable_earnings(quarters(110, 100), VERIFIED, {"2026-06-30": 18000.0}).condition,
                         "basis_unverified")


if __name__ == "__main__":
    unittest.main()
