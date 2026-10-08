import json
import tempfile
import unittest
from pathlib import Path

from sectors.basis import (BasisCheck, Published, PublishedConverted, assess, assess_converted, common_rates,
                           implied_rates, load_checks, write_checks)

TN = 10**12


def quarters(q2_2025: float, q1: float, q2: float,
             minorities: tuple[float, float, float] | None = None) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = [{"date": "2025-06-30", "earnings": int(q2_2025 * TN)},
                                     {"date": "2026-03-31", "earnings": int(q1 * TN)},
                                     {"date": "2026-06-30", "earnings": int(q2 * TN)}]
    for row, value in zip(rows, minorities or ()):
        row["minorities"] = int(value * TN)
    return rows


def published(h1: float | None, h1_prior: float | None, currency: str = "IDR",
              source: str = "https://example.test/report") -> Published:
    return Published(currency, h1, h1_prior, source, "")


class AssessTest(unittest.TestCase):
    def test_standalone_quarters_matching_the_half_year_are_verified(self) -> None:
        check = assess("BBCA", quarters(14.88, 14.70, 14.86), published(29.5, 29.0))
        self.assertEqual(check.status, "verified")
        self.assertEqual(check.earnings, {"2025-06-30": 14_880_000_000_000, "2026-03-31": 14_700_000_000_000,
                                          "2026-06-30": 14_860_000_000_000})

    def test_a_half_year_more_than_one_percent_away_is_a_mismatch(self) -> None:
        check = assess("BMRI", quarters(13.4, 17.0, 15.8), published(30.4, 24.4))
        self.assertEqual(check, BasisCheck("BMRI", "mismatch", {}, "Q1 + Q2 2026 earnings of IDR 32.80 tn differ "
                         "from the published H1 2026 profit of IDR 30.40 tn by 7.89%.", "https://example.test/report"))

    def test_a_half_year_matching_earnings_less_minorities_is_verified_on_that_line(self) -> None:
        check = assess("BBRI", quarters(12.855, 15.775, 15.725, (0.126, 0.141, 0.176)), published(31.18, 26.54))
        self.assertEqual(check.status, "verified")
        self.assertEqual(check.earnings, {"2025-06-30": 12_855_000_000_000, "2026-03-31": 15_775_000_000_000,
                                          "2026-06-30": 15_725_000_000_000})
        self.assertEqual(check.reason, "Q1 + Q2 2026 earnings less minorities of IDR 31.18 tn are within 0.0% of "
                                       "the published H1 2026 profit of IDR 31.18 tn; Q2 2025 of IDR 12.86 tn is a "
                                       "standalone quarter against a published H1 2025 of IDR 26.54 tn.")

    def test_a_half_year_matching_earnings_plus_minorities_is_verified_on_that_line(self) -> None:
        check = assess("ANTM", quarters(2.565, 3.407, 2.982, (0.255, 0.257, 0.267)), published(6.91, 5.14))
        self.assertEqual(check.status, "verified")
        self.assertIn("earnings plus minorities of IDR 6.91 tn", check.reason)

    def test_no_line_within_one_percent_is_still_a_mismatch(self) -> None:
        check = assess("BMRI", quarters(13.383, 17.043, 15.799, (1.062, 0.829, 0.385)), published(30.4, 24.44))
        self.assertEqual((check.status, check.earnings), ("mismatch", {}))

    def test_cumulative_quarters_are_not_verified(self) -> None:
        cumulative = assess("XXXX", quarters(10.0, 10.0, 20.0), published(20.0, 20.0))
        self.assertEqual((cumulative.status, cumulative.earnings), ("mismatch", {}))
        near_zero_q1 = assess("XXXX", quarters(10.0, 0.1, 20.0), published(20.0, 20.0))
        self.assertEqual(near_zero_q1.reason, "A Q2 figure is close to its half-year total, so the quarters may be "
                                              "cumulative.")

    def test_other_reporting_currencies_and_missing_figures_are_named(self) -> None:
        self.assertEqual(assess("ADRO", quarters(1, 1, 1), published(None, None, "USD")).status,
                         "reporting_currency")
        self.assertEqual(assess("XXXX", quarters(1, 1, 1), None).status, "not_checked")
        self.assertEqual(assess("XXXX", quarters(1, 1, 1), published(None, None)).status, "no_published_figure")
        self.assertEqual(assess("XXXX", [], published(2.0, 2.0)).status, "quarters_missing")

    def test_invalid_published_totals_or_a_missing_source_never_verify(self) -> None:
        rows = quarters(5.0, 4.0, 6.0)
        for h1, h1_prior in ((float("nan"), 10.0), (10.0, float("nan")), (float("inf"), 10.0), (0.0, 10.0),
                             (10.0, 0.0), (1e308, 10.0), (10.0, 1e308)):
            with self.subTest(h1=h1, h1_prior=h1_prior):
                self.assertEqual(assess("XXXX", rows, published(h1, h1_prior)).status, "no_published_figure")
        self.assertEqual(assess("XXXX", rows, published(10.0, 10.0, source=" ")).status, "no_published_figure")

    def test_fractional_earnings_are_kept_exactly(self) -> None:
        rows = [{"date": "2025-06-30", "earnings": 5e12 + 0.5}, {"date": "2026-03-31", "earnings": 4e12 + 0.5},
                {"date": "2026-06-30", "earnings": 6e12 + 0.5}]
        self.assertEqual(assess("XXXX", rows, published(10.0, 10.0)).earnings,
                         {"2025-06-30": 5e12 + 0.5, "2026-03-31": 4e12 + 0.5, "2026-06-30": 6e12 + 0.5})

    def test_loss_making_companies_are_checked_by_magnitude(self) -> None:
        self.assertEqual(assess("EMTK", quarters(0.591, -0.336, 0.015), published(-0.3206, 4.23)).status,
                         "verified")

    def test_recorded_checks_round_trip_through_the_file(self) -> None:
        checks = [assess("BBCA", quarters(14.88, 14.70, 14.86), published(29.5, 29.0)),
                  assess("ADRO", [], published(None, None, "USD"))]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "earnings_basis.json"
            write_checks(checks, path)
            self.assertEqual(load_checks(path), {check.symbol: check for check in checks})
        self.assertEqual(load_checks(Path("/nonexistent/earnings_basis.json")), {})

    def test_stored_verified_entries_without_evidence_are_not_trusted(self) -> None:
        good = assess("BBCA", quarters(14.88, 14.70, 14.86), published(29.5, 29.0))
        for source, earnings in ((None, good.earnings), ("", good.earnings), ("  ", good.earnings),
                                 (good.source, {"2026-06-30": float("inf")}), (good.source, {})):
            with self.subTest(source=source, earnings=earnings), tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / "earnings_basis.json"
                path.write_text(json.dumps({"BBCA": {"status": "verified", "earnings": earnings,
                                                     "reason": good.reason, "source": source}}))
                loaded = load_checks(path)["BBCA"]
                self.assertEqual((loaded.status, loaded.earnings), ("no_published_figure", {}))


def usd(q1_2025: float, h1_2025: float, q1_2026: float, h1_2026: float) -> PublishedConverted:
    return PublishedConverted("USD", "attributable", q1_2025, h1_2025, q1_2026, h1_2026, "https://example.test/q1",
                              "https://example.test/h1", "")


RATES = {"2025-06-30": 16230.0, "2026-03-31": 17000.0, "2026-06-30": 17900.0}


class ConvertedTest(unittest.TestCase):
    def test_implied_rates_divide_sectors_rupiah_by_published_standalone_quarters(self) -> None:
        rows = quarters(16230 * 232.68e6 / TN, 17000 * 143.03e6 / TN, 17900 * 330.74e6 / TN)
        rates = implied_rates(rows, usd(196.0, 428.68, 143.03, 473.77))
        self.assertEqual({period: round(rate) for period, rate in (rates or {}).items()},
                         {"2025-06-30": 16230, "2026-03-31": 17000, "2026-06-30": 17900})

    def test_common_rates_are_the_median_of_enough_reporters(self) -> None:
        implied = [{"2026-06-30": r} for r in (17899.0, 17898.0, 17815.0, 29525.0, 17902.0)]
        self.assertEqual(common_rates(implied), {"2026-06-30": 17899.0})
        self.assertEqual(common_rates(implied[:4]), {})

    def test_quarters_at_the_common_rates_are_verified_and_keep_sectors_values(self) -> None:
        rows = quarters(16230 * 232.68e6 / TN, 17000 * 143.03e6 / TN, 17900 * 330.74e6 / TN)
        check = assess_converted("AADI", rows, usd(196.0, 428.68, 143.03, 473.77), RATES)
        self.assertEqual(check.status, "verified")
        self.assertEqual(check.rates, RATES)
        self.assertEqual(check.earnings, {"2025-06-30": rows[0]["earnings"], "2026-03-31": rows[1]["earnings"],
                                          "2026-06-30": rows[2]["earnings"]})
        self.assertEqual(check.reason, "Reports in USD. Sectors' rupiah quarters divided by the published USD "
                                       "standalone quarters give 16,230, 17,000 and 17,900 rupiah per USD for "
                                       "Q2 2025, Q1 2026 and Q2 2026, each within 1% of the rate shared by other "
                                       "USD reporters, so growth is measured in USD at those rates.")

    def test_a_quarter_off_the_common_rate_is_a_mismatch(self) -> None:
        rows = quarters(16724 * 0.23e6 / TN, 17000 * 5.70e6 / TN, 17900 * 14.08e6 / TN)
        check = assess_converted("CUAN", rows, usd(1.71, 1.94, 5.70, 19.78), RATES)
        self.assertEqual((check.status, check.earnings, check.rates), ("mismatch", {}, {}))
        self.assertEqual(check.reason, "Reports in USD. Q2 2025 converts at 16,724 rupiah per USD against the "
                                       "shared 16,230 (3.04% apart), so the published USD quarters and Sectors' "
                                       "rupiah quarters do not line up.")

    def test_without_published_quarters_or_common_rates_a_converted_reporter_stays_blocked(self) -> None:
        rows = quarters(1.0, 1.0, 1.0)
        self.assertEqual(assess_converted("XXXX", rows, None, RATES).status, "reporting_currency")
        self.assertEqual(assess_converted("XXXX", rows, usd(1, 2, 1, 2), {}).status, "reporting_currency")

    def test_stored_rates_round_trip_and_bad_rates_are_not_trusted(self) -> None:
        rows = quarters(16230 * 232.68e6 / TN, 17000 * 143.03e6 / TN, 17900 * 330.74e6 / TN)
        good = assess_converted("AADI", rows, usd(196.0, 428.68, 143.03, 473.77), RATES)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "earnings_basis.json"
            write_checks([good], path)
            self.assertEqual(load_checks(path)["AADI"], good)
            entry = json.loads(path.read_text())
            entry["AADI"]["rates"] = {"2025-06-30": 0, "2026-03-31": 17000.0, "2026-06-30": 17900.0}
            path.write_text(json.dumps(entry))
            self.assertEqual(load_checks(path)["AADI"].status, "no_published_figure")


if __name__ == "__main__":
    unittest.main()
