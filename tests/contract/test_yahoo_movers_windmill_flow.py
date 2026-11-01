from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
FLOW = ROOT / "workflows/windmill/f/daily_dash/yahoo_movers__flow/flow.yaml"
RUN_SCRIPT = ROOT / "workflows/windmill/f/daily_dash/run_yahoo_movers.sh"
DELIVER_SCRIPT = ROOT / "workflows/windmill/f/daily_dash/deliver_yahoo_movers.sh"
SCHEDULE = ROOT / "workflows/windmill/f/daily_dash/yahoo_movers_1845.schedule.yaml"


def _modules() -> list[dict[str, object]]:
    payload = yaml.safe_load(FLOW.read_text(encoding="utf-8"))
    return payload["value"]["modules"]


def test_yahoo_movers_flow_persists_before_external_delivery() -> None:
    modules = _modules()

    assert [module["id"] for module in modules] == [
        "run_yahoo_movers",
        "persist_data",
        "deliver_yahoo_movers",
    ]

    assert set(modules[0]["value"]["input_transforms"]) == {"data_repo"}

    persist = modules[1]["value"]["input_transforms"]
    assert persist["data_path"]["value"] == "yahoo-movers/snapshots"
    assert persist["remote_url"] == {
        "type": "javascript",
        "expr": 'variable("f/daily_dash/data_repo_remote_url")',
    }
    assert persist["branch"] == {
        "type": "javascript",
        "expr": 'variable("f/daily_dash/data_repo_branch")',
    }

    deliver = modules[2]["value"]["input_transforms"]
    assert deliver["artifact_path"] == {
        "type": "javascript",
        "expr": "results.run_yahoo_movers.artifact_path",
    }


def test_yahoo_movers_run_has_no_delivery_credentials() -> None:
    script = RUN_SCRIPT.read_text(encoding="utf-8")

    assert "DAILY_DASH_TELEGRAM" not in script
    assert 'data_repo="${1:-/data/daily-dash-data}"' in script
    assert 'python_bin="$app_home/.venv/bin/python"' in script
    assert "daily_dash.commands.yahoo_movers run" in script


def test_yahoo_movers_delivery_is_artifact_based() -> None:
    script = DELIVER_SCRIPT.read_text(encoding="utf-8")

    assert 'artifact_path="$1"' in script
    assert 'python_bin="${DAILY_DASH_HOME:-/opt/daily-dash}/.venv/bin/python"' in script
    assert "daily_dash.commands.yahoo_movers deliver" in script


def test_yahoo_movers_schedule_matches_registry() -> None:
    schedule = yaml.safe_load(SCHEDULE.read_text(encoding="utf-8"))

    assert schedule["schedule"] == "0 45 18 * * MON,TUE,WED,THU,FRI"
    assert schedule["timezone"] == "Europe/Berlin"
    assert schedule["enabled"] is True
    assert schedule["script_path"] == "f/daily_dash/yahoo_movers"
    assert schedule["is_flow"] is True
