#!/usr/bin/env bash
set -Eeuo pipefail

data_repo="${1:-${DAILY_DASH_DATA_REPO:-/data/daily-dash-data}}"
reddit_client_id="${2:-${DAILY_DASH_REDDIT_CLIENT_ID:-}}"
reddit_client_secret="${3:-${DAILY_DASH_REDDIT_CLIENT_SECRET:-}}"
reddit_user_agent="${4:-${DAILY_DASH_REDDIT_USER_AGENT:-}}"
app_home="${DAILY_DASH_HOME:-/opt/daily-dash}"
python_bin="$app_home/.venv/bin/python"
config_dir="${DAILY_DASH_CONFIG_DIR:-$app_home/config}"
assets_dir="${DAILY_DASH_ASSETS_DIR:-$app_home/assets}"
gateway_url="${DAILY_DASH_MODEL_GATEWAY_URL:-http://daily_dash_model_gateway:8080}"

export DAILY_DASH_HOME="$app_home"
export DAILY_DASH_CONFIG_DIR="$config_dir"
export DAILY_DASH_ASSETS_DIR="$assets_dir"
export DAILY_DASH_DATA_REPO="$data_repo"
export DAILY_DASH_MODEL_GATEWAY_URL="$gateway_url"
export DAILY_DASH_REDDIT_CLIENT_ID="$reddit_client_id"
export DAILY_DASH_REDDIT_CLIENT_SECRET="$reddit_client_secret"
export DAILY_DASH_REDDIT_USER_AGENT="$reddit_user_agent"

if [[ ! -x "$python_bin" ]]; then
  echo "DailyDash Python not found: $python_bin" >&2
  exit 3
fi
if [[ ! -f "$config_dir/profiles/wsb.yaml" ]]; then
  echo "WSB profile not found: $config_dir/profiles/wsb.yaml" >&2
  exit 4
fi
if [[ ! -f "$assets_dir/prompts/wsb-ranking/v1/prompt.yaml" ]]; then
  echo "WSB prompt asset not found: $assets_dir/prompts/wsb-ranking/v1" >&2
  exit 5
fi
if [[ ! -d "$data_repo/.git" ]]; then
  echo "DailyDash data repository not found: $data_repo" >&2
  exit 6
fi
for name in DAILY_DASH_REDDIT_CLIENT_ID DAILY_DASH_REDDIT_CLIENT_SECRET DAILY_DASH_REDDIT_USER_AGENT; do
  if [[ -z "${!name:-}" ]]; then
    echo "WSB Reddit configuration is missing: $name" >&2
    exit 7
  fi
done

"$python_bin" -m daily_dash.commands.wsb run \
  --config-dir "$config_dir" \
  --data-repo "$data_repo" \
  --gateway-url "$gateway_url" \
  > ./result.json
