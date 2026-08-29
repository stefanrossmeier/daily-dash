from __future__ import annotations

import json
from pathlib import Path

from daily_dash.contracts.polymarket import PolymarketRunDocument


class JsonPolymarketRunStore:
    @staticmethod
    def read(path: Path) -> PolymarketRunDocument:
        return PolymarketRunDocument.model_validate_json(path.read_text(encoding="utf-8"))

    def __init__(self, data_repo: Path) -> None:
        self._data_repo = data_repo

    def write(self, document: PolymarketRunDocument) -> Path:
        output_dir = self._data_repo / "polymarket" / "snapshots"
        output_dir.mkdir(parents=True, exist_ok=True)
        stamp = document.retrieved_at.strftime("%Y%m%dT%H%M%SZ")
        output_path = output_dir / f"{stamp}_{document.run_id[:8]}.json"
        if output_path.exists():
            raise FileExistsError(f"Polymarket run artifact already exists: {output_path}")
        output_path.write_text(
            json.dumps(document.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        return output_path
