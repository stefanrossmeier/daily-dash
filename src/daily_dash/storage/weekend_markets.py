from __future__ import annotations

from datetime import UTC
from pathlib import Path
from typing import Protocol

from daily_dash.contracts import WeekendMarketSnapshotDocument


class WeekendMarketSnapshotStore(Protocol):
    def save(self, snapshot: WeekendMarketSnapshotDocument) -> Path:
        """Persist one immutable weekend market snapshot."""


class JsonFileWeekendMarketSnapshotStore:
    @staticmethod
    def read(path: Path) -> WeekendMarketSnapshotDocument:
        return WeekendMarketSnapshotDocument.model_validate_json(path.read_text(encoding="utf-8"))

    def __init__(self, data_repo: Path) -> None:
        self._snapshot_dir = data_repo / "markets" / "weekend" / "snapshots"

    def save(self, snapshot: WeekendMarketSnapshotDocument) -> Path:
        self._snapshot_dir.mkdir(parents=True, exist_ok=True)
        timestamp = snapshot.raw.retrieved_at.astimezone(UTC).strftime("%Y%m%dT%H%M%SZ")
        run_suffix = snapshot.raw.run_id[:8]
        path = self._snapshot_dir / f"{timestamp}_{run_suffix}.json"
        if path.exists():
            raise FileExistsError(f"weekend market snapshot already exists: {path}")
        path.write_text(snapshot.model_dump_json(indent=2) + "\n", encoding="utf-8")
        return path
