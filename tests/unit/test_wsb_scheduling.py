from datetime import UTC, datetime
from pathlib import Path

from daily_dash.config.loader import load_schedule_registry
from daily_dash.scheduling import resolve_daily_cycle_window

ROOT = Path(__file__).resolve().parents[2]


def test_wsb_saturday_scheduled_window_uses_previous_daily_slot_across_date_boundary() -> None:
    registry = load_schedule_registry(ROOT / "config/schedules.yaml")
    reference = datetime(2026, 8, 29, 18, 35, tzinfo=UTC)  # Saturday 20:35 Berlin

    window = resolve_daily_cycle_window(registry, "wsb", reference)

    assert window.scheduled_for == datetime(2026, 8, 29, 18, 35, tzinfo=UTC)
    assert window.previous_scheduled_for == datetime(2026, 8, 28, 18, 35, tzinfo=UTC)
    assert window.window_start == datetime(2026, 8, 28, 17, 35, tzinfo=UTC)
    assert window.window_end == datetime(2026, 8, 29, 18, 35, tzinfo=UTC)


def test_wsb_saturday_manual_run_before_slot_uses_current_daily_cycle() -> None:
    registry = load_schedule_registry(ROOT / "config/schedules.yaml")
    reference = datetime(2026, 8, 29, 9, 24, tzinfo=UTC)  # Saturday 11:24 Berlin

    window = resolve_daily_cycle_window(registry, "wsb", reference)

    assert window.scheduled_for == datetime(2026, 8, 29, 18, 35, tzinfo=UTC)
    assert window.previous_scheduled_for == datetime(2026, 8, 28, 18, 35, tzinfo=UTC)
    assert window.window_start == datetime(2026, 8, 28, 17, 35, tzinfo=UTC)
    assert window.window_end == reference


def test_wsb_manual_run_after_slot_does_not_extend_past_daily_cutoff() -> None:
    registry = load_schedule_registry(ROOT / "config/schedules.yaml")
    reference = datetime(2026, 8, 29, 19, 5, tzinfo=UTC)  # Saturday 21:05 Berlin

    window = resolve_daily_cycle_window(registry, "wsb", reference)

    assert window.window_start == datetime(2026, 8, 28, 17, 35, tzinfo=UTC)
    assert window.window_end == datetime(2026, 8, 29, 18, 35, tzinfo=UTC)


def test_wsb_monday_window_uses_previous_sunday_slot() -> None:
    registry = load_schedule_registry(ROOT / "config/schedules.yaml")
    reference = datetime(2026, 8, 31, 18, 35, tzinfo=UTC)  # Monday 20:35 Berlin

    window = resolve_daily_cycle_window(registry, "wsb", reference)

    assert window.scheduled_for == datetime(2026, 8, 31, 18, 35, tzinfo=UTC)
    assert window.previous_scheduled_for == datetime(2026, 8, 30, 18, 35, tzinfo=UTC)
    assert window.window_start == datetime(2026, 8, 30, 17, 35, tzinfo=UTC)
    assert window.window_end == datetime(2026, 8, 31, 18, 35, tzinfo=UTC)
