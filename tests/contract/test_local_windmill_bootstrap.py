from __future__ import annotations

import os
import stat
import subprocess
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
TEMPLATE = ROOT / "deploy/local-windmill"


def test_local_windmill_template_contains_dailydash_services() -> None:
    override = yaml.safe_load(
        (TEMPLATE / "docker-compose.override.yml").read_text(encoding="utf-8")
    )
    services = override["services"]

    worker = services["windmill_worker_dailydash"]
    gateway = services["daily_dash_model_gateway"]

    assert worker["build"]["dockerfile"] == "deploy/example/windmill-worker.Dockerfile"
    assert gateway["build"]["dockerfile"] == "deploy/example/model-gateway.Dockerfile"
    assert (
        "DAILY_DASH_MODEL_GATEWAY_URL=http://daily_dash_model_gateway:8080" in worker["environment"]
    )
    assert gateway["ports"] == ["127.0.0.1:18080:8080"]


def test_bootstrap_materializes_environment_without_secrets_in_git(
    tmp_path: Path,
) -> None:
    target = tmp_path / "windmill"
    data_repo = tmp_path / "data"

    subprocess.run(
        [
            str(ROOT / "scripts/bootstrap-local-windmill.sh"),
            "--target",
            str(target),
            "--data-repo",
            str(data_repo),
        ],
        check=True,
        cwd=ROOT,
        env=os.environ.copy(),
        capture_output=True,
        text=True,
    )

    for name in (
        "docker-compose.yml",
        "docker-compose.override.yml",
        "Caddyfile",
        ".env.example",
        ".gitignore",
    ):
        assert (target / name).read_bytes() == (TEMPLATE / name).read_bytes()

    env_text = (target / ".env").read_text(encoding="utf-8")
    assert f"DAILY_DASH_SOURCE={ROOT}" in env_text
    assert f"DAILY_DASH_DATA_SOURCE={data_repo}" in env_text
    assert "WM_IMAGE=ghcr.io/windmill-labs/windmill:1.775.1" in env_text

    secret_names = (
        "openrouter_api_key",
        "data_repo_deploy_key",
        "telegram_token",
        "telegram_chat_id",
        "reddit_client_id",
        "reddit_client_secret",
        "reddit_user_agent",
    )
    for name in secret_names:
        secret_file = target / "secrets" / name
        assert secret_file.is_file()
        assert secret_file.read_text(encoding="utf-8") == ""
        assert stat.S_IMODE(secret_file.stat().st_mode) == 0o600
    assert stat.S_IMODE((target / "secrets").stat().st_mode) == 0o700

    assert (data_repo / ".git").is_dir()
    branch = subprocess.run(
        ["git", "-C", str(data_repo), "branch", "--show-current"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    assert branch == "main"


def test_persistence_flow_has_no_author_specific_remote() -> None:
    flow_root = ROOT / "workflows/windmill/f/daily_dash"
    for flow in (
        flow_root / "markets__flow/flow.yaml",
        flow_root / "news_top__flow/flow.yaml",
        flow_root / "news_alternative__flow/flow.yaml",
        flow_root / "news_german__flow/flow.yaml",
        flow_root / "news_smart__flow/flow.yaml",
        flow_root / "wsb__flow/flow.yaml",
    ):
        text = flow.read_text(encoding="utf-8")
        assert "stefanrossmeier/daily-dash-data" not in text
        assert 'variable("f/daily_dash/data_repo_remote_url")' in text
        assert 'variable("f/daily_dash/data_repo_branch")' in text
