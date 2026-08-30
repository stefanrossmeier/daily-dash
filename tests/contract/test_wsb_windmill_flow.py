import os
import stat
import subprocess
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
FLOW_ROOT = ROOT / "workflows/windmill/f/daily_dash"


def _script_path(module: dict[str, object]) -> str:
    value = module["value"]
    assert isinstance(value, dict)
    path = value["path"]
    assert isinstance(path, str)
    return path


def test_wsb_flow_persists_before_delivery() -> None:
    flow = yaml.safe_load((FLOW_ROOT / "wsb__flow/flow.yaml").read_text(encoding="utf-8"))
    modules = flow["value"]["modules"]
    assert [_script_path(module) for module in modules] == [
        "f/daily_dash/run_wsb",
        "f/daily_dash/persist_data_repo",
        "f/daily_dash/deliver_wsb",
    ]
    run = modules[0]["value"]["input_transforms"]
    assert run["reddit_client_id"]["expr"] == 'variable("f/daily_dash/reddit_client_id")'
    assert run["reddit_client_secret"]["expr"] == 'variable("f/daily_dash/reddit_client_secret")'
    assert run["reddit_user_agent"]["expr"] == 'variable("f/daily_dash/reddit_user_agent")'
    persist = modules[1]["value"]["input_transforms"]
    assert persist["data_path"]["value"] == "wsb/snapshots"
    deliver = modules[2]["value"]["input_transforms"]
    assert deliver["artifact_path"]["expr"] == "results.run_wsb.artifact_path"


def test_wsb_schedule_is_daily_at_2035() -> None:
    schedule = yaml.safe_load((FLOW_ROOT / "wsb_2035.schedule.yaml").read_text(encoding="utf-8"))
    assert schedule["schedule"] == "0 35 20 * * *"
    assert schedule["timezone"] == "Europe/Berlin"
    assert schedule["script_path"] == "f/daily_dash/wsb"


def test_wsb_runner_executes_without_positional_args(tmp_path: Path) -> None:
    app_home = tmp_path / "app"
    python_bin = app_home / ".venv/bin/python"
    python_bin.parent.mkdir(parents=True)
    python_bin.write_text('#!/usr/bin/env bash\nprintf \'{"artifact_path":"ok"}\\n\'\n')
    python_bin.chmod(python_bin.stat().st_mode | stat.S_IXUSR)
    config_dir = tmp_path / "config"
    (config_dir / "profiles").mkdir(parents=True)
    (config_dir / "profiles/wsb.yaml").write_text("profile")
    assets_dir = tmp_path / "assets/prompts/wsb-ranking/v2"
    assets_dir.mkdir(parents=True)
    (assets_dir / "prompt.yaml").write_text("prompt")
    data_repo = tmp_path / "data"
    (data_repo / ".git").mkdir(parents=True)
    env = os.environ.copy()
    env.update(
        {
            "DAILY_DASH_HOME": str(app_home),
            "DAILY_DASH_CONFIG_DIR": str(config_dir),
            "DAILY_DASH_ASSETS_DIR": str(tmp_path / "assets"),
            "DAILY_DASH_DATA_REPO": str(data_repo),
            "DAILY_DASH_REDDIT_CLIENT_ID": "test-client",
            "DAILY_DASH_REDDIT_CLIENT_SECRET": "test-secret",
            "DAILY_DASH_REDDIT_USER_AGENT": "script:daily-dash:test (by /u/test)",
        }
    )

    subprocess.run(
        ["bash", str(FLOW_ROOT / "run_wsb.sh")],
        check=True,
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
    )
    assert (tmp_path / "result.json").read_text().strip() == '{"artifact_path":"ok"}'


def test_wsb_setup_uses_secret_files_not_root_env() -> None:
    configure = (ROOT / "scripts/configure-wsb-reddit.sh").read_text(encoding="utf-8")
    live_test = (ROOT / "scripts/run-wsb-live-test.sh").read_text(encoding="utf-8")
    assert 'SECRET_DIR="$WINDMILL_DIR/secrets"' in configure
    assert "reddit_client_secret" in configure
    assert "ROOT/.env" not in configure
    assert 'SECRET_DIR="$WINDMILL_DIR/secrets"' in live_test
    assert "ROOT/.env" not in live_test
