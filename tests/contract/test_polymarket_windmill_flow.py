from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
FLOW_ROOT = ROOT / "workflows/windmill/f/daily_dash"


def _path(module: dict[str, object]) -> str:
    value = module["value"]
    assert isinstance(value, dict)
    path = value["path"]
    assert isinstance(path, str)
    return path


def test_polymarket_flow_persists_before_delivery() -> None:
    flow = yaml.safe_load((FLOW_ROOT / "polymarket__flow/flow.yaml").read_text())
    modules = flow["value"]["modules"]
    assert [_path(module) for module in modules] == [
        "f/daily_dash/run_polymarket",
        "f/daily_dash/persist_data_repo",
        "f/daily_dash/deliver_polymarket",
    ]
    assert modules[1]["value"]["input_transforms"]["data_path"]["value"] == ("polymarket/snapshots")
    assert modules[2]["value"]["input_transforms"]["artifact_path"]["expr"] == (
        "results.run_polymarket.artifact_path"
    )


def test_polymarket_schedule_is_daily_at_2045() -> None:
    schedule = yaml.safe_load((FLOW_ROOT / "polymarket_2045.schedule.yaml").read_text())
    assert schedule["schedule"] == "0 45 20 * * *"
    assert schedule["timezone"] == "Europe/Berlin"
    assert schedule["script_path"] == "f/daily_dash/polymarket"
