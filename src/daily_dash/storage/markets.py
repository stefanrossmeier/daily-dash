from __future__ import annotations

from datetime import UTC
from pathlib import Path
from typing import Protocol

from daily_dash.contracts.market import MarketSnapshotDocument


class MarketSnapshotStore(Protocol):
    """Persistence boundary for market snapshots."""

    def save(self, snapshot: MarketSnapshotDocument) -> Path:
        """Persist one immutable market snapshot."""


class JsonFileMarketSnapshotStore:
    """Persist market snapshots as readable JSON files."""

    def __init__(self, data_repo: Path) -> None:
        self._snapshot_dir = data_repo / "markets" / "snapshots"

    def save(self, snapshot: MarketSnapshotDocument) -> Path:
        self._snapshot_dir.mkdir(parents=True, exist_ok=True)

        timestamp = snapshot.raw.retrieved_at.astimezone(UTC).strftime("%Y%m%dT%H%M%SZ")
        run_suffix = snapshot.raw.run_id[:8]

        path = self._snapshot_dir / f"{timestamp}_{run_suffix}.json"

        if path.exists():
            raise FileExistsError(f"market snapshot already exists: {path}")

        path.write_text(
            snapshot.model_dump_json(indent=2) + "\n",
            encoding="utf-8",
        )

        return path
