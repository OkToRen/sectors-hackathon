import unittest

from sectors.pattern import pattern_update, support_distance

BANDS = {"price": {"half_width": 0.02, "population": 21}, "flow": {"half_width": 0.002, "population": 23}}


class SupportDistanceTest(unittest.TestCase):
    def test_v5_formulas_for_each_allowed_range(self) -> None:
        self.assertAlmostEqual(support_distance("positive", 0.06, 0.02), 2.0)
        self.assertAlmostEqual(support_distance("neutral_or_positive", 0.0, 0.02), 1.0)
        self.assertAlmostEqual(support_distance("neutral_or_negative", -0.02, 0.02), 2.0)


class PatternUpdateTest(unittest.TestCase):
    def update(self, state: str, then: tuple[float, float], now: tuple[float, float]) -> str | None:
        return pattern_update(state, {"price": then[0], "flow": then[1]}, {"price": now[0], "flow": now[1]},
                              BANDS).label

    def test_labels_follow_the_v5_order(self) -> None:
        # Confirmed Strength needs price and flow both positive.
        self.assertEqual(self.update("Confirmed Strength", (0.06, 0.006), (0.01, 0.006)), "Contradicting")
        self.assertEqual(self.update("Confirmed Strength", (0.06, 0.006), (0.062, 0.0061)), "Stable")
        self.assertEqual(self.update("Confirmed Strength", (0.06, 0.006), (0.08, 0.008)), "Strengthening")
        self.assertEqual(self.update("Confirmed Strength", (0.06, 0.006), (0.04, 0.006)), "Weakening")
        self.assertEqual(self.update("Confirmed Strength", (0.06, 0.006), (0.04, 0.008)), "Mixed")

    def test_an_exact_tolerance_change_is_stable(self) -> None:
        self.assertEqual(self.update("Confirmed Strength", (0.06, 0.006), (0.065, 0.006)), "Stable")

    def test_unusable_recorded_bands_make_the_update_unavailable(self) -> None:
        for band in ({}, {"half_width": 0.0, "population": 21}, {"half_width": float("nan"), "population": 21},
                     {"half_width": -0.02, "population": 21}, {"half_width": None, "population": 21},
                     {"half_width": 0.02, "population": None}, {"half_width": "bad", "population": 21},
                     {"half_width": 0.02}):
            with self.subTest(band=band):
                update = pattern_update("Confirmed Strength", {"price": 0.06, "flow": 0.006},
                                        {"price": 0.06, "flow": 0.006}, {**BANDS, "price": band})
                self.assertEqual((update.available, update.label), (False, None))

    def test_every_named_label_is_explained(self) -> None:
        for now in ((0.01, 0.006), (0.062, 0.0061), (0.08, 0.008), (0.04, 0.006), (0.04, 0.008)):
            with self.subTest(now=now):
                update = pattern_update("Confirmed Strength", {"price": 0.06, "flow": 0.006},
                                        {"price": now[0], "flow": now[1]}, BANDS)
                self.assertTrue(update.note)
        contradicting = pattern_update("Ignored Improvement", {"price": 0.01, "flow": 0.006},
                                       {"price": 0.03, "flow": 0.008}, BANDS)
        self.assertEqual(contradicting.label, "Contradicting")
        self.assertNotIn("catching up", contradicting.note)

    def test_contradicting_agrees_with_how_many_dimensions_left_the_range(self) -> None:
        one = pattern_update("Confirmed Strength", {"price": 0.06, "flow": 0.006}, {"price": 0.06, "flow": 0.0},
                             BANDS)
        self.assertEqual(one.note, "Foreign flow now sits outside the range Confirmed Strength requires, so the market "
                                   "pattern no longer matches the state.")
        both = pattern_update("Confirmed Strength", {"price": 0.06, "flow": 0.006}, {"price": 0.0, "flow": 0.0},
                              BANDS)
        self.assertEqual(both.note, "Price and foreign flow now sit outside the range Confirmed Strength requires, so "
                                    "the market pattern no longer matches the state.")

    def test_mixed_explains_each_dimension_as_it_moved(self) -> None:
        update = pattern_update("Confirmed Strength", {"price": 0.06, "flow": 0.006}, {"price": 0.08, "flow": 0.0061},
                                BANDS)
        self.assertEqual(update.label, "Mixed")
        self.assertEqual(update.note, "Price moved further into the Confirmed Strength pattern while foreign flow held "
                                      "about steady.")

    def test_boundaries_are_inclusive_neutral(self) -> None:
        # Early Deterioration allows flat-or-leading price: exactly -b is still inside.
        self.assertNotEqual(self.update("Early Deterioration", (0.0, 0.0), (-0.02, 0.0)), "Contradicting")
        self.assertEqual(self.update("Early Deterioration", (0.0, 0.0), (-0.021, 0.0)), "Contradicting")

    def test_neutral_gets_raw_changes_and_missing_inputs_are_unavailable(self) -> None:
        neutral = pattern_update("Neutral", {"price": 0.01, "flow": 0.001}, {"price": 0.03, "flow": 0.0}, BANDS)
        self.assertIsNone(neutral.label)
        self.assertAlmostEqual(neutral.price_change or 0, 0.02)
        missing = pattern_update("Confirmed Strength", {"price": 0.06, "flow": 0.006}, {"price": None, "flow": 0.006},
                                 BANDS)
        self.assertEqual((missing.label, missing.available), (None, False))

    def test_ignored_improvement_names_price_catching_up(self) -> None:
        update = pattern_update("Ignored Improvement", {"price": -0.04, "flow": 0.0}, {"price": 0.0, "flow": 0.0},
                                BANDS)
        self.assertEqual(update.label, "Weakening")
        self.assertIn("price catching up", update.note)
        mixed = pattern_update("Ignored Improvement", {"price": -0.04, "flow": 0.0}, {"price": 0.0, "flow": 0.002},
                               BANDS)
        self.assertEqual(mixed.label, "Mixed")
        self.assertIn("price catching up", mixed.note)


if __name__ == "__main__":
    unittest.main()
