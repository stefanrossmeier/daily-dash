from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
FLOW = ROOT / "workflows/windmill/f/daily_dash/markets__flow/flow.yaml"
RUN_SCRIPT = ROOT / "workflows/windmill/f/daily_dash/run_markets.sh"
DELIVER_SCRIPT = ROOT / "workflows/windmill/f/daily_dash/deliver_markets.sh"


def _modules() -> list[dict[str, object]]:
    payload = yaml.safe_load(FLOW.read_text(encoding="utf-8"))
    return payload["value"]["modules"]


def test_markets_flow_persists_before_external_delivery() -> None:
    modules = _modules()

    assert [module["id"] for module in modules] == [
        "run_markets",
        "persist_data",
        "deliver_markets",
    ]

    run_inputs = modules[0]["value"]["input_transforms"]
    assert set(run_inputs) == {"data_repo"}

    persist = modules[1]["value"]["input_transforms"]
    assert persist["data_path"]["value"] == "markets/snapshots"
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
        "expr": "results.run_markets.artifact_path",
    }


def test_markets_run_step_has_no_delivery_credentials() -> None:
    script = RUN_SCRIPT.read_text(encoding="utf-8")

    assert "DAILY_DASH_TELEGRAM" not in script
    assert "--delivery" not in script
    assert "daily_dash.commands.markets run" in script


def test_markets_delivery_is_a_separate_artifact_based_step() -> None:
    script = DELIVER_SCRIPT.read_text(encoding="utf-8")

    assert 'artifact_path="$1"' in script
    assert "daily_dash.commands.markets deliver" in script
