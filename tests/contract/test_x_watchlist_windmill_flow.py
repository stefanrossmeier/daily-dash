from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
FLOW = ROOT / "workflows/windmill/f/daily_dash/x_watchlist__flow/flow.yaml"
RUN = ROOT / "workflows/windmill/f/daily_dash/run_x_watchlist.sh"


def test_x_watchlist_flow_is_run_persist_deliver() -> None:
    flow = yaml.safe_load(FLOW.read_text(encoding="utf-8"))
    modules = flow["value"]["modules"]
    assert [module["id"] for module in modules] == [
        "run_x_watchlist",
        "persist_data",
        "deliver_x_watchlist",
    ]
    assert modules[1]["value"]["input_transforms"]["data_path"]["value"] == "x-watchlist/snapshots"
    assert (
        modules[2]["value"]["input_transforms"]["artifact_path"]["expr"]
        == "results.run_x_watchlist.artifact_path"
    )


def test_x_watchlist_run_script_has_no_openrouter_or_x_secret_access() -> None:
    script = RUN.read_text(encoding="utf-8")
    assert "OPENROUTER_API_KEY" not in script
    assert "openrouter_api_key" not in script
    assert "cookie" not in script.lower()
    assert "playwright" not in script.lower()
    assert "DAILY_DASH_MODEL_GATEWAY_URL" in script
