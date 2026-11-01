from __future__ import annotations

from datetime import UTC
from pathlib import Path
from typing import Protocol

from daily_dash.contracts import MoversSnapshotDocument


class YahooMoversSnapshotStore(Protocol):
    def save(self, snapshot: MoversSnapshotDocument) -> Path:
        """Persist one immutable Yahoo Movers snapshot."""


class JsonFileYahooMoversSnapshotStore:
    @staticmethod
    def read(path: Path) -> MoversSnapshotDocument:
        return MoversSnapshotDocument.model_validate_json(path.read_text(encoding="utf-8"))

    def __init__(self, data_repo: Path) -> None:
        self._snapshot_dir = data_repo / "yahoo-movers" / "snapshots"

    def save(self, snapshot: MoversSnapshotDocument) -> Path:
        self._snapshot_dir.mkdir(parents=True, exist_ok=True)
        timestamp = snapshot.raw.retrieved_at.astimezone(UTC).strftime("%Y%m%dT%H%M%SZ")
        run_suffix = snapshot.raw.run_id[:8]
        path = self._snapshot_dir / f"{timestamp}_{run_suffix}.json"
        if path.exists():
            raise FileExistsError(f"yahoo movers snapshot already exists: {path}")
        path.write_text(snapshot.model_dump_json(indent=2) + "\n", encoding="utf-8")
        return path
