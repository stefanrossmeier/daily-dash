from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml

from daily_dash.config.models import PipelineScheduleConfig, ScheduleRegistry
from daily_dash.contracts.news import NewsRetrievalWindow

_DAY_INDEX = {
    "MON": 0,
    "TUE": 1,
    "WED": 2,
    "THU": 3,
    "FRI": 4,
    "SAT": 5,
    "SUN": 6,
}


def _parse_local_time(value: str) -> time:
    hour_text, minute_text = value.split(":", 1)
    return time(hour=int(hour_text), minute=int(minute_text))


def _scheduled_instant(
    day: date,
    slot_local: str,
    timezone: ZoneInfo,
) -> datetime:
    local = datetime.combine(day, _parse_local_time(slot_local), tzinfo=timezone)
    round_trip = local.astimezone(UTC).astimezone(timezone)
    if round_trip.replace(tzinfo=None) != local.replace(tzinfo=None):
        raise ValueError(
            f"scheduled local time does not exist in timezone {timezone.key}: "
            f"{day.isoformat()} {slot_local}"
        )
    return local


def scheduled_slots_before_or_at(
    schedule: PipelineScheduleConfig,
    reference_time: datetime,
    *,
    count: int = 2,
) -> list[datetime]:
    if reference_time.tzinfo is None:
        raise ValueError("reference time must be timezone-aware")
    if count < 1:
        raise ValueError("slot count must be positive")

    timezone = ZoneInfo(schedule.timezone)
    reference_local = reference_time.astimezone(timezone)
    allowed_days = {_DAY_INDEX[value] for value in schedule.days}
    slots: list[datetime] = []

    # A valid schedule has at least one day and one slot. Looking back 21 days
    # safely covers the previous two eligible slots even for one-day-per-week jobs.
    for days_back in range(0, 22):
        current_date = reference_local.date() - timedelta(days=days_back)
        if current_date.weekday() not in allowed_days:
            continue

        for slot_local in schedule.slots_local:
            candidate = _scheduled_instant(current_date, slot_local, timezone)
            if candidate <= reference_local:
                slots.append(candidate)

        if len(slots) >= count + len(schedule.slots_local):
            break

    slots.sort(reverse=True)
    if len(slots) < count:
        raise ValueError(f"could not resolve {count} scheduled slots for {schedule.schedule_id}")

    return slots[:count]


def resolve_schedule_window(
    registry: ScheduleRegistry,
    schedule_id: str,
    reference_time: datetime,
    *,
    explicit_start: datetime | None = None,
    explicit_end: datetime | None = None,
) -> NewsRetrievalWindow:
    schedule = registry.schedules.get(schedule_id)
    if schedule is None:
        raise ValueError(f"unknown schedule: {schedule_id}")

    if (explicit_start is None) != (explicit_end is None):
        raise ValueError("explicit window start and end must be supplied together")

    if explicit_start is not None and explicit_end is not None:
        if explicit_start.tzinfo is None or explicit_end.tzinfo is None:
            raise ValueError("explicit window bounds must be timezone-aware")
        start = explicit_start.astimezone(UTC)
        end = explicit_end.astimezone(UTC)
        if start >= end:
            raise ValueError("explicit window start must be before end")
        return NewsRetrievalWindow(
            source="explicit",
            schedule_id=schedule_id,
            timezone=schedule.timezone,
            window_start=start,
            window_end=end,
            grace_minutes=0,
        )

    if schedule.window is None:
        raise ValueError(f"schedule does not define a retrieval window: {schedule_id}")

    current, previous = scheduled_slots_before_or_at(
        schedule,
        reference_time,
        count=2,
    )
    grace = timedelta(minutes=schedule.window.grace_minutes)

    return NewsRetrievalWindow(
        source="schedule",
        schedule_id=schedule_id,
        timezone=schedule.timezone,
        previous_scheduled_for=previous.astimezone(UTC),
        scheduled_for=current.astimezone(UTC),
        window_start=previous.astimezone(UTC) - grace,
        window_end=current.astimezone(UTC),
        grace_minutes=schedule.window.grace_minutes,
    )


def resolve_daily_cycle_window(
    registry: ScheduleRegistry,
    schedule_id: str,
    reference_time: datetime,
    *,
    explicit_start: datetime | None = None,
    explicit_end: datetime | None = None,
) -> NewsRetrievalWindow:
    """Resolve a once-daily window against the current local calendar cycle.

    Before today's scheduled slot, an ad-hoc run covers from the previous
    day's slot (minus grace) through the current reference time. At or after
    today's slot, the window ends at the scheduled slot. This keeps manual
    runs useful without extending past the production cutoff.
    """
    if (explicit_start is None) != (explicit_end is None):
        raise ValueError("explicit window start and end must be supplied together")
    if explicit_start is not None and explicit_end is not None:
        return resolve_schedule_window(
            registry,
            schedule_id,
            reference_time,
            explicit_start=explicit_start,
            explicit_end=explicit_end,
        )

    schedule = registry.schedules.get(schedule_id)
    if schedule is None:
        raise ValueError(f"unknown schedule: {schedule_id}")
    if schedule.window is None:
        raise ValueError(f"schedule does not define a retrieval window: {schedule_id}")
    if set(schedule.days) != set(_DAY_INDEX) or len(schedule.slots_local) != 1:
        raise ValueError(f"daily-cycle window requires one slot on every day: {schedule_id}")
    if reference_time.tzinfo is None:
        raise ValueError("reference time must be timezone-aware")

    timezone = ZoneInfo(schedule.timezone)
    reference_local = reference_time.astimezone(timezone)
    slot_local = schedule.slots_local[0]
    scheduled_local = _scheduled_instant(reference_local.date(), slot_local, timezone)
    previous_local = _scheduled_instant(
        reference_local.date() - timedelta(days=1),
        slot_local,
        timezone,
    )
    grace = timedelta(minutes=schedule.window.grace_minutes)
    effective_end = min(reference_local, scheduled_local)

    return NewsRetrievalWindow(
        source="schedule",
        schedule_id=schedule_id,
        timezone=schedule.timezone,
        previous_scheduled_for=previous_local.astimezone(UTC),
        scheduled_for=scheduled_local.astimezone(UTC),
        window_start=previous_local.astimezone(UTC) - grace,
        window_end=effective_end.astimezone(UTC),
        grace_minutes=schedule.window.grace_minutes,
    )


def windmill_cron_expression(schedule: PipelineScheduleConfig, slot_local: str) -> str:
    slot = _parse_local_time(slot_local)
    if set(schedule.days) == set(_DAY_INDEX):
        day_expression = "*"
    else:
        day_expression = ",".join(schedule.days)
    return f"0 {slot.minute} {slot.hour} * * {day_expression}"


def windmill_schedule_specs(registry: ScheduleRegistry) -> dict[str, dict[str, object]]:
    specs: dict[str, dict[str, object]] = {}

    for schedule_id, schedule in registry.schedules.items():
        if not schedule.enabled:
            continue

        for slot_local in schedule.slots_local:
            suffix = slot_local.replace(":", "")
            path = f"{schedule_id.replace('-', '_')}_{suffix}"
            specs[path] = {
                "summary": f"DailyDash {schedule_id} {slot_local}",
                "schedule": windmill_cron_expression(schedule, slot_local),
                "timezone": schedule.timezone,
                "enabled": True,
                "script_path": schedule.flow_path,
                "is_flow": True,
                "args": {},
                "no_flow_overlap": True,
            }

    return specs


def render_windmill_schedule_files(
    registry: ScheduleRegistry,
    output_dir: Path,
) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    expected: list[Path] = []

    for name, spec in windmill_schedule_specs(registry).items():
        path = output_dir / f"{name}.schedule.yaml"
        path.write_text(
            yaml.safe_dump(spec, sort_keys=False, allow_unicode=True),
            encoding="utf-8",
        )
        expected.append(path)

    expected_set = set(expected)
    for existing in output_dir.glob("*.schedule.yaml"):
        if existing not in expected_set:
            existing.unlink()

    return sorted(expected)
