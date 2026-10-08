import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path

from sectors.freeze import load_freeze, write_freeze
from sectors.state import Band

NOW = datetime(2026, 10, 6, 9, 0, tzinfo=UTC)
BANDS: dict[str, Band | None] = {"fundamentals": Band(0.1, 20), "price": Band(0.02, 44), "flow": None}


class FreezeTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.definitions, self.freeze = root / "candidate_signals.yaml", root / "bands_freeze.json"
        self.definitions.write_text("version: 1\n")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_frozen_bands_round_trip_with_their_definitions(self) -> None:
        write_freeze(BANDS, self.definitions, self.freeze, NOW)
        self.assertEqual(load_freeze(self.freeze, self.definitions), BANDS)

    def test_no_freeze_means_bands_are_calibrated_live(self) -> None:
        self.assertIsNone(load_freeze(self.freeze, self.definitions))

    def test_a_freeze_of_other_definitions_is_refused(self) -> None:
        write_freeze(BANDS, self.definitions, self.freeze, NOW)
        self.definitions.write_text("version: 2\n")
        with self.assertRaises(ValueError):
            load_freeze(self.freeze, self.definitions)

    def test_unusable_stored_bands_block_their_dimension(self) -> None:
        for half_width, population in ((0.0, 20), (-0.1, 20), (float("nan"), 20), (float("inf"), 20), (0.1, 4)):
            with self.subTest(half_width=half_width, population=population):
                write_freeze({"price": Band(half_width, population)}, self.definitions, self.freeze, NOW)
                self.assertEqual(load_freeze(self.freeze, self.definitions), {"price": None})


if __name__ == "__main__":
    unittest.main()
