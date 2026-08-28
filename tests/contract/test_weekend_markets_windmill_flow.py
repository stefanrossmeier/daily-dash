from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
FLOW = ROOT / "workflows/windmill/f/daily_dash/markets_weekend__flow/flow.yaml"
RUN_SCRIPT = ROOT / "workflows/windmill/f/daily_dash/run_markets_weekend.sh"
DELIVER_SCRIPT = ROOT / "workflows/windmill/f/daily_dash/deliver_markets_weekend.sh"


def test_weekend_markets_flow_persists_before_delivery() -> None:
    payload = yaml.safe_load(FLOW.read_text(encoding="utf-8"))
    modules = payload["value"]["modules"]
    assert [module["id"] for module in modules] == [
        "run_markets_weekend",
        "persist_data",
        "deliver_markets_weekend",
    ]
    persist = modules[1]["value"]["input_transforms"]
    assert persist["data_path"]["value"] == "markets/weekend/snapshots"
    deliver = modules[2]["value"]["input_transforms"]
    assert deliver["artifact_path"]["expr"] == "results.run_markets_weekend.artifact_path"


def test_weekend_markets_scripts_have_separate_delivery() -> None:
    run_script = RUN_SCRIPT.read_text(encoding="utf-8")
    deliver_script = DELIVER_SCRIPT.read_text(encoding="utf-8")
    assert "DAILY_DASH_TELEGRAM" not in run_script
    assert "daily_dash.commands.markets_weekend run" in run_script
    assert "daily_dash.commands.markets_weekend deliver" in deliver_script
