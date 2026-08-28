from datetime import UTC, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from daily_dash.config.loader import load_schedule_registry
from daily_dash.scheduling import (
    resolve_schedule_window,
    scheduled_slots_before_or_at,
    windmill_schedule_specs,
)

ROOT = Path(__file__).resolve().parents[2]
REGISTRY = load_schedule_registry(ROOT / "config" / "schedules.yaml")
BERLIN = ZoneInfo("Europe/Berlin")


def test_top_news_window_uses_previous_slot_plus_one_hour_grace() -> None:
    window = resolve_schedule_window(
        REGISTRY,
        "news-top",
        datetime(2026, 8, 28, 12, 3, tzinfo=BERLIN),
    )

    assert window.source == "schedule"
    assert window.scheduled_for == datetime(2026, 8, 28, 10, 0, tzinfo=UTC)
    assert window.previous_scheduled_for == datetime(2026, 8, 28, 4, 0, tzinfo=UTC)
    assert window.window_start == datetime(2026, 8, 28, 3, 0, tzinfo=UTC)
    assert window.window_end == datetime(2026, 8, 28, 10, 0, tzinfo=UTC)
    assert window.grace_minutes == 60


def test_explicit_window_override_is_reproducible() -> None:
    start = datetime(2026, 8, 28, 4, 0, tzinfo=UTC)
    end = datetime(2026, 8, 28, 8, 0, tzinfo=UTC)
    window = resolve_schedule_window(
        REGISTRY,
        "news-top",
        datetime(2026, 8, 28, 9, 0, tzinfo=UTC),
        explicit_start=start,
        explicit_end=end,
    )

    assert window.source == "explicit"
    assert window.window_start == start
    assert window.window_end == end
    assert window.scheduled_for is None
    assert window.grace_minutes == 0


def test_weekday_market_schedule_skips_weekend() -> None:
    schedule = REGISTRY.schedules["markets"]
    current, previous = scheduled_slots_before_or_at(
        schedule,
        datetime(2026, 8, 31, 8, 6, tzinfo=BERLIN),
    )

    assert current == datetime(2026, 8, 31, 8, 5, tzinfo=BERLIN)
    assert previous == datetime(2026, 8, 28, 22, 0, tzinfo=BERLIN)


def test_weekend_market_schedule_contains_only_weekend_slots() -> None:
    schedule = REGISTRY.schedules["markets-weekend"]
    current, previous = scheduled_slots_before_or_at(
        schedule,
        datetime(2026, 8, 30, 20, 31, tzinfo=BERLIN),
    )

    assert current == datetime(2026, 8, 30, 20, 30, tzinfo=BERLIN)
    assert previous == datetime(2026, 8, 30, 10, 30, tzinfo=BERLIN)


def test_windmill_specs_come_from_registry_and_skip_disabled_future_pipeline() -> None:
    specs = windmill_schedule_specs(REGISTRY)

    assert specs["news_top_0600"]["schedule"] == "0 0 6 * * *"
    assert specs["markets_0805"]["schedule"] == "0 5 8 * * MON,TUE,WED,THU,FRI"
    assert specs["markets_0805"]["script_path"] == "f/daily_dash/markets"
    assert not any(name.startswith("markets_weekend_") for name in specs)
