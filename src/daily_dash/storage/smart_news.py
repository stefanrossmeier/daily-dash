from __future__ import annotations

import json
from pathlib import Path

from daily_dash.contracts.smart_news import SmartNewsRunDocument


class JsonSmartNewsRunStore:
    @staticmethod
    def read(path: Path) -> SmartNewsRunDocument:
        return SmartNewsRunDocument.model_validate_json(path.read_text(encoding="utf-8"))

    def __init__(self, data_repo: Path) -> None:
        self._data_repo = data_repo

    def write(self, document: SmartNewsRunDocument) -> Path:
        output_dir = self._data_repo / "news" / "smart"
        output_dir.mkdir(parents=True, exist_ok=True)

        stamp = document.retrieved_at.strftime("%Y%m%dT%H%M%SZ")
        output_path = output_dir / f"{stamp}_{document.run_id[:8]}.json"

        if output_path.exists():
            raise FileExistsError(f"Smart News run artifact already exists: {output_path}")

        output_path.write_text(
            json.dumps(
                document.model_dump(mode="json"),
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        return output_path
