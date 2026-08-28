from __future__ import annotations

from pathlib import Path

from daily_dash.config.loader import load_schedule_registry
from daily_dash.scheduling import render_windmill_schedule_files

ROOT = Path(__file__).resolve().parents[1]
registry = load_schedule_registry(ROOT / "config" / "schedules.yaml")
paths = render_windmill_schedule_files(
    registry,
    ROOT / "workflows" / "windmill" / "f" / "daily_dash",
)

for path in paths:
    print(path.relative_to(ROOT))
