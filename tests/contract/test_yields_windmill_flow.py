from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
FLOW = ROOT / "workflows/windmill/f/daily_dash/yields__flow/flow.yaml"
RUN_SCRIPT = ROOT / "workflows/windmill/f/daily_dash/run_yields.sh"
DELIVER_SCRIPT = ROOT / "workflows/windmill/f/daily_dash/deliver_yields.sh"


def _modules() -> list[dict[str, object]]:
    payload = yaml.safe_load(FLOW.read_text(encoding="utf-8"))
    return payload["value"]["modules"]


def test_yields_flow_persists_before_external_delivery() -> None:
    modules = _modules()

    assert [module["id"] for module in modules] == [
        "run_yields",
        "persist_data",
        "deliver_yields",
    ]

    assert set(modules[0]["value"]["input_transforms"]) == {"data_repo"}

    persist = modules[1]["value"]["input_transforms"]
    assert persist["data_path"]["value"] == "yields/snapshots"
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
        "expr": "results.run_yields.artifact_path",
    }


def test_yields_run_has_no_delivery_credentials() -> None:
    script = RUN_SCRIPT.read_text(encoding="utf-8")

    assert "DAILY_DASH_TELEGRAM" not in script
    assert 'data_repo="${1:-/data/daily-dash-data}"' in script
    assert 'python_bin="$app_home/.venv/bin/python"' in script
    assert "daily_dash.commands.yields run" in script


def test_yields_delivery_is_artifact_based() -> None:
    script = DELIVER_SCRIPT.read_text(encoding="utf-8")

    assert 'artifact_path="$1"' in script
    assert 'python_bin="${DAILY_DASH_HOME:-/opt/daily-dash}/.venv/bin/python"' in script
    assert "daily_dash.commands.yields deliver" in script
