import json
import tempfile
import unittest
from pathlib import Path

from sectors.assignments import Assignment, load_assignments, previous_for, record_assignments

A = Assignment("PTBA", "2026-06-30", "2026-09-30", "Confirmed Strength",
               {"fundamentals": "Improving", "price": "Leading", "flow": "Accumulating"},
               {"fundamentals": 3.18, "price": 0.22, "flow": 0.007},
               {"fundamentals": {"half_width": 0.16, "population": 23}, "price": None, "flow": None},
               "2026-10-06T09:00:00+00:00", {"price": "roster"})


class AssignmentTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "research" / "state_assignments.json"

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_an_assignment_is_recorded_once_and_never_overwritten(self) -> None:
        self.assertEqual(record_assignments(self.path, [A]), [A])
        changed = Assignment(**{**A.__dict__, "state": "Neutral", "assigned_at": "2026-10-07T09:00:00+00:00"})
        self.assertEqual(record_assignments(self.path, [changed]), [A])
        self.assertEqual(load_assignments(self.path), [A])

    def test_the_previous_state_is_the_latest_earlier_period(self) -> None:
        older = Assignment(**{**A.__dict__, "period": "2025-12-31", "availability_date": "2026-03-31",
                              "state": "Neutral"})
        oldest = Assignment(**{**A.__dict__, "period": "2025-09-30", "availability_date": "2025-12-31"})
        record_assignments(self.path, [oldest, older, A])
        self.assertEqual(previous_for(load_assignments(self.path), "PTBA", "2026-06-30"), older)
        self.assertIsNone(previous_for(load_assignments(self.path), "PTBA", "2025-09-30"))

    def test_unusable_recorded_bands_load_as_missing(self) -> None:
        broken = Assignment(**{**A.__dict__, "bands": {"fundamentals": {"half_width": None, "population": 23},
                                                       "price": {"half_width": 0.02}, "flow": None}})
        record_assignments(self.path, [broken])
        self.assertEqual(load_assignments(self.path)[0].bands, {"fundamentals": None, "price": None, "flow": None})

    def test_an_assignment_recorded_before_references_loads_as_sector_relative(self) -> None:
        old = {k: v for k, v in A.__dict__.items() if k != "references"}
        self.path.parent.mkdir(parents=True)
        self.path.write_text(json.dumps([old]))
        self.assertEqual(load_assignments(self.path)[0].references, {"price": "sector"})


if __name__ == "__main__":
    unittest.main()
