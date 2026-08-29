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


def test_smart_news_flow_runs_persists_then_delivers() -> None:
    flow = yaml.safe_load((FLOW_ROOT / "news_smart__flow/flow.yaml").read_text(encoding="utf-8"))
    modules = flow["value"]["modules"]

    assert [_script_path(module) for module in modules] == [
        "f/daily_dash/run_news_smart",
        "f/daily_dash/persist_data_repo",
        "f/daily_dash/deliver_news_smart",
    ]

    persist = modules[1]["value"]["input_transforms"]
    assert persist["data_path"]["value"] == "news/smart"
    assert persist["remote_url"] == {
        "type": "javascript",
        "expr": 'variable("f/daily_dash/data_repo_remote_url")',
    }
    assert persist["branch"] == {
        "type": "javascript",
        "expr": 'variable("f/daily_dash/data_repo_branch")',
    }

    deliver = modules[2]["value"]["input_transforms"]
    assert deliver["artifact_path"]["expr"] == "results.run_news_smart.artifact_path"


def test_smart_news_runner_has_safe_default_data_repo() -> None:
    text = (FLOW_ROOT / "run_news_smart.sh").read_text(encoding="utf-8")
    assert 'data_repo="${1:-${DAILY_DASH_DATA_REPO:-/data/daily-dash-data}}"' in text
    assert "daily_dash.commands.news_smart run" in text


def test_smart_news_runner_executes_without_positional_args(tmp_path: Path) -> None:
    app_home = tmp_path / "app"
    python_bin = app_home / ".venv/bin/python"
    python_bin.parent.mkdir(parents=True)
    python_bin.write_text(
        '#!/usr/bin/env bash\nprintf \'{"artifact_path":"ok"}\n\'\n',
        encoding="utf-8",
    )
    python_bin.chmod(python_bin.stat().st_mode | stat.S_IXUSR)

    config_dir = tmp_path / "config"
    (config_dir / "profiles").mkdir(parents=True)
    (config_dir / "profiles/news-smart.yaml").write_text("profile", encoding="utf-8")

    assets_dir = tmp_path / "assets/prompts/news-smart/v1"
    assets_dir.mkdir(parents=True)
    (assets_dir / "prompt.yaml").write_text("prompt", encoding="utf-8")

    data_repo = tmp_path / "data"
    (data_repo / ".git").mkdir(parents=True)

    env = os.environ.copy()
    env.update(
        {
            "DAILY_DASH_HOME": str(app_home),
            "DAILY_DASH_CONFIG_DIR": str(config_dir),
            "DAILY_DASH_ASSETS_DIR": str(tmp_path / "assets"),
            "DAILY_DASH_DATA_REPO": str(data_repo),
        }
    )

    subprocess.run(
        ["bash", str(FLOW_ROOT / "run_news_smart.sh")],
        check=True,
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
    )

    assert (tmp_path / "result.json").read_text(encoding="utf-8").strip() == (
        '{"artifact_path":"ok"}'
    )


def test_smart_news_schedule_preserves_legacy_slots() -> None:
    expected = {
        "news_smart_0715.schedule.yaml": "0 15 7 * * *",
        "news_smart_1215.schedule.yaml": "0 15 12 * * *",
        "news_smart_2100.schedule.yaml": "0 0 21 * * *",
    }

    for name, cron in expected.items():
        schedule = yaml.safe_load((FLOW_ROOT / name).read_text(encoding="utf-8"))
        assert schedule["schedule"] == cron
        assert schedule["timezone"] == "Europe/Berlin"
        assert schedule["script_path"] == "f/daily_dash/news_smart"
        assert schedule["no_flow_overlap"] is True
