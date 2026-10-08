"""Capture store keyed by endpoint and parameters, plus an append-only credit ledger."""

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sectors.api import ENDPOINT_BY_NAME, is_success

Params = tuple[tuple[str, str], ...]


def is_usable(record: dict[str, Any]) -> bool:
    """A success whose body has the endpoint's shape, rechecked so older captures meet current rules."""
    endpoint = ENDPOINT_BY_NAME.get(record["endpoint"])
    return (is_success(record["status"]) and record["error"] is None
            and endpoint is not None and endpoint.shape_ok(record["body"]))


@dataclass(frozen=True)
class CaptureStore:
    root: Path
    secret: str = ""

    def capture_path(self, symbol: str, endpoint: str, path: str, params: Params, vintage: str) -> Path:
        """Captures are reused within one vintage (the Jakarta date) so new reports are picked up later."""
        key = hashlib.sha256(json.dumps([path, list(params), vintage]).encode()).hexdigest()[:16]
        return self.root / "captures" / symbol / endpoint / f"{key}.json"

    def load(self, path: Path) -> dict[str, Any] | None:
        if not path.exists():
            return None
        record: dict[str, Any] = json.loads(path.read_text())
        return record

    def save(self, path: Path, record: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self._redact(json.dumps(record, indent=2, sort_keys=True)) + "\n")

    def latest(self, symbol: str, endpoint: str) -> dict[str, Any] | None:
        """The newest successful capture, else the newest failed attempt."""
        records = [r for path in (self.root / "captures" / symbol / endpoint).glob("*.json")
                   if (r := self.load(path))]
        return max(records, key=lambda r: (is_usable(r), str(r["retrieved_at"])), default=None)

    def usable(self, symbol: str, endpoint: str) -> list[dict[str, Any]]:
        """Every usable capture, oldest retrieval first."""
        records = [r for path in (self.root / "captures" / symbol / endpoint).glob("*.json")
                   if (r := self.load(path)) and is_usable(r)]
        return sorted(records, key=lambda r: str(r["retrieved_at"]))

    def append_ledger(self, entry: dict[str, Any]) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        with (self.root / "ledger.jsonl").open("a") as ledger:
            ledger.write(self._redact(json.dumps(entry, sort_keys=True)) + "\n")

    def ledger(self) -> list[dict[str, Any]]:
        path = self.root / "ledger.jsonl"
        if not path.exists():
            return []
        return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]

    def _redact(self, text: str) -> str:
        return text.replace(self.secret, "[redacted]") if self.secret else text
