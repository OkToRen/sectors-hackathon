import json
import tempfile
import unittest
from pathlib import Path

from sectors.methodology import methodology_fields


class MethodologyTest(unittest.TestCase):
    def fields(self, bands: dict[str, object], log: str, pages: list[dict[str, object]] | None = None
               ) -> dict[str, str]:
        with tempfile.TemporaryDirectory() as tmp:
            research = Path(tmp)
            (research / "freeze.json").write_text(json.dumps({
                "frozen_at": "2026-10-06T03:00:00+00:00", "definitions": "d.yaml", "definitions_sha256": "ab" * 32,
                "bands": bands}))
            (research / "log.csv").write_text(log)
            return methodology_fields(pages or [], research, "freeze.json", "log.csv")

    def test_unusable_stored_bands_are_named_not_published(self) -> None:
        fields = self.fields({"price": {"half_width": None, "population": 6},
                              "flow": {"half_width": 0.0, "population": 6},
                              "fundamentals": {"half_width": 0.05, "population": 6}}, "date,decision,finding\n")
        self.assertEqual(fields["band_rows"], "<li>Price: no usable band</li><li>Foreign flow: no usable band</li>"
                                              "<li>Fundamentals ±5.00% from 6 roster values</li>")

    def test_empty_tables_span_their_own_columns(self) -> None:
        fields = self.fields({}, "date,decision,finding\n")
        self.assertEqual(fields["composition_rows"], '<tr><td colspan="2">None recorded.</td></tr>')
        self.assertEqual(fields["log_rows"], '<tr><td colspan="3">None recorded.</td></tr>')

    def test_states_kept_from_an_earlier_freeze_are_counted_with_its_time(self) -> None:
        current = {"half_width": 0.05, "population": 6}

        def page(symbol: str, assigned_at: str, width: float) -> dict[str, object]:
            return {"symbol": symbol, "state": "Neutral", "assigned_at": assigned_at, "basis_check": None,
                    "price_reference": "sector", "blockers": [], "evidence_strength": "Insufficient",
                    "sector": "Energy", "dimensions": {dim: {"band": {"half_width": width, "population": 6}}
                                                       for dim in ("fundamentals", "price", "flow")}}

        fields = self.fields({dim: current for dim in ("fundamentals", "price", "flow")}, "date,decision,finding\n",
                             [page("AAAA", "2026-10-06T01:00:00+00:00", 0.04),
                              page("BBBB", "2026-10-06T03:00:00+00:00", 0.05)])
        self.assertEqual(fields["freeze_text"], "Frozen 2026-10-06 03:00 UTC against d.yaml (SHA-256 abababababab). "
                                                "1 of 2 states was recorded at 2026-10-06 01:00 UTC under an earlier "
                                                "freeze and keeps its bands, because a state is recorded once per "
                                                "report period and never rewritten. Each Company view shows the bands "
                                                "its state used.")

    def test_a_dimension_missing_from_the_freeze_still_counts_as_a_kept_band(self) -> None:
        page: dict[str, object] = {
            "symbol": "AAAA", "state": "Neutral", "assigned_at": "2026-10-06T01:00:00+00:00", "basis_check": None,
            "price_reference": "sector", "blockers": [], "evidence_strength": "Insufficient", "sector": "Energy",
            "dimensions": {dim: {"band": {"half_width": 0.05, "population": 6}} for dim in ("fundamentals", "price", "flow")}}
        fields = self.fields({"fundamentals": {"half_width": 0.05, "population": 6}}, "date,decision,finding\n",
                             [page])
        self.assertIn("1 of 1 states was recorded at 2026-10-06 01:00 UTC under an earlier freeze", fields["freeze_text"])

    def test_a_log_row_with_an_unquoted_comma_is_refused(self) -> None:
        with self.assertRaisesRegex(ValueError, "log.csv line 2"):
            self.fields({}, "date,decision,finding\n2026-10-06,kept,one, two\n")


if __name__ == "__main__":
    unittest.main()
