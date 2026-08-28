from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RUN_NEWS_SCRIPT = ROOT / "workflows/windmill/f/daily_dash/run_news.sh"


def test_news_job_establishes_non_secret_runtime_contract() -> None:
    script = RUN_NEWS_SCRIPT.read_text(encoding="utf-8")

    assert 'app_home="${DAILY_DASH_HOME:-/opt/daily-dash}"' in script
    assert 'assets_dir="${DAILY_DASH_ASSETS_DIR:-$app_home/assets}"' in script
    assert (
        'gateway_url="${DAILY_DASH_MODEL_GATEWAY_URL:-http://daily_dash_model_gateway:8080}"'
        in script
    )
    assert 'export DAILY_DASH_ASSETS_DIR="$assets_dir"' in script
    assert 'export DAILY_DASH_MODEL_GATEWAY_URL="$gateway_url"' in script
    assert '--gateway-url "$gateway_url"' in script
