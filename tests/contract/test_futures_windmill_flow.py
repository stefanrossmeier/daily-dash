from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
FLOW = ROOT / "workflows/windmill/f/daily_dash/futures__flow/flow.yaml"
RUN_SCRIPT = ROOT / "workflows/windmill/f/daily_dash/run_futures.sh"
DELIVER_SCRIPT = ROOT / "workflows/windmill/f/daily_dash/deliver_futures.sh"
SCHEDULES = ROOT / "config/schedules.yaml"


def _modules() -> list[dict[str, object]]:
    payload = yaml.safe_load(FLOW.read_text(encoding="utf-8"))
    return payload["value"]["modules"]


def test_futures_flow_persists_before_external_delivery() -> None:
    modules = _modules()
    assert [module["id"] for module in modules] == [
        "run_futures",
        "persist_data",
        "deliver_futures",
    ]
    persist = modules[1]["value"]["input_transforms"]
    assert persist["data_path"]["value"] == "futures/snapshots"
    deliver = modules[2]["value"]["input_transforms"]
    assert deliver["artifact_path"] == {
        "type": "javascript",
        "expr": "results.run_futures.artifact_path",
    }


def test_futures_run_step_is_anonymous_and_has_no_delivery_or_llm_credentials() -> None:
    modules = _modules()
    run_inputs = modules[0]["value"]["input_transforms"]
    assert set(run_inputs) == {"data_repo"}

    script = RUN_SCRIPT.read_text(encoding="utf-8")
    assert "TRADINGVIEW_USERNAME" not in script
    assert "TRADINGVIEW_PASSWORD" not in script
    assert "DAILY_DASH_TELEGRAM" not in script
    assert "OPENROUTER" not in script
    assert "daily_dash.commands.futures run" in script


def test_futures_delivery_is_separate_and_artifact_based() -> None:
    script = DELIVER_SCRIPT.read_text(encoding="utf-8")
    assert 'artifact_path="$1"' in script
    assert "daily_dash.commands.futures deliver" in script


def test_futures_schedule_preserves_legacy_weekday_slots() -> None:
    payload = yaml.safe_load(SCHEDULES.read_text(encoding="utf-8"))
    schedule = payload["schedules"]["futures"]
    assert schedule["timezone"] == "Europe/Berlin"
    assert schedule["days"] == ["MON", "TUE", "WED", "THU", "FRI"]
    assert schedule["slots_local"] == ["05:00", "07:15", "12:30", "23:00"]
