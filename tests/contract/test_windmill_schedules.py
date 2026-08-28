from pathlib import Path

import yaml

from daily_dash.config.loader import load_schedule_registry
from daily_dash.scheduling import windmill_schedule_specs

ROOT = Path(__file__).resolve().parents[2]
WINDMILL_ROOT = ROOT / "workflows" / "windmill"
DAILY_DASH_ROOT = WINDMILL_ROOT / "f" / "daily_dash"


def test_checked_in_windmill_schedules_match_registry() -> None:
    registry = load_schedule_registry(ROOT / "config" / "schedules.yaml")
    expected = windmill_schedule_specs(registry)
    actual_paths = sorted(DAILY_DASH_ROOT.glob("*.schedule.yaml"))

    assert {path.stem.removesuffix(".schedule") for path in actual_paths} == set(expected)

    for path in actual_paths:
        name = path.stem.removesuffix(".schedule")
        actual = yaml.safe_load(path.read_text(encoding="utf-8"))
        assert actual == expected[name]


def test_windmill_sync_includes_schedules() -> None:
    config = yaml.safe_load((WINDMILL_ROOT / "wmill.yaml").read_text(encoding="utf-8"))
    assert config["includeSchedules"] is True
