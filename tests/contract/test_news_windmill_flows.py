from pathlib import Path

import yaml

ROOT = Path("workflows/windmill/f/daily_dash")

EXPECTED = {
    "news_top": ("news-top", "news/top"),
    "news_alternative": ("news-alternative", "news/alternative"),
    "news_german": ("news-german", "news/german"),
}


def _script_path(module: dict[str, object]) -> str:
    value = module["value"]
    assert isinstance(value, dict)
    path = value["path"]
    assert isinstance(path, str)
    return path


def test_news_flows_run_persist_then_deliver() -> None:
    for flow_name, (profile, subtree) in EXPECTED.items():
        path = ROOT / f"{flow_name}__flow/flow.yaml"
        assert path.is_file()

        flow = yaml.safe_load(path.read_text(encoding="utf-8"))
        modules = flow["value"]["modules"]

        assert [_script_path(module) for module in modules] == [
            "f/daily_dash/run_news",
            "f/daily_dash/persist_data_repo",
            "f/daily_dash/deliver_news",
        ]

        run_transforms = modules[0]["value"]["input_transforms"]
        assert run_transforms["profile"]["value"] == profile

        persist = modules[1]["value"]["input_transforms"]
        persist_text = str(persist)
        assert subtree in persist_text
        assert persist["remote_url"] == {
            "type": "javascript",
            "expr": 'variable("f/daily_dash/data_repo_remote_url")',
        }
        assert persist["branch"] == {
            "type": "javascript",
            "expr": 'variable("f/daily_dash/data_repo_branch")',
        }

        deliver = modules[2]["value"]["input_transforms"]
        assert deliver["artifact_path"]["expr"] == ("results.run_news.artifact_path")
        assert "telegram_token" in deliver
        assert "telegram_chat_id" in deliver
