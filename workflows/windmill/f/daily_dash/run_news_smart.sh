#!/usr/bin/env bash
set -Eeuo pipefail

data_repo="${1:-${DAILY_DASH_DATA_REPO:-/data/daily-dash-data}}"

app_home="${DAILY_DASH_HOME:-/opt/daily-dash}"
python_bin="$app_home/.venv/bin/python"
config_dir="${DAILY_DASH_CONFIG_DIR:-$app_home/config}"
assets_dir="${DAILY_DASH_ASSETS_DIR:-$app_home/assets}"
gateway_url="${DAILY_DASH_GATEWAY_URL:-http://daily-dash-llm-gateway:8080}"
# Ranking chats AND native X search route to the dedicated llm-gateway
# instance; the model gateway is only the fallback. Windmill jobs run with a
# sanitized environment, so every variable the client needs is exported here
# with its default.
gateway_token_file="${DAILY_DASH_GATEWAY_TOKEN_FILE:-/run/daily-dash-secrets/gateway_token}"

export DAILY_DASH_HOME="$app_home"
export DAILY_DASH_CONFIG_DIR="$config_dir"
export DAILY_DASH_ASSETS_DIR="$assets_dir"
export DAILY_DASH_DATA_REPO="$data_repo"
export DAILY_DASH_GATEWAY_URL="$gateway_url"
export DAILY_DASH_RUN_ID="${DAILY_DASH_RUN_ID:-${WM_ROOT_FLOW_JOB_ID:-${WM_JOB_ID:?Set DAILY_DASH_RUN_ID}}}"
export DAILY_DASH_GATEWAY_TOKEN_FILE="$gateway_token_file"

if [[ ! -x "$python_bin" ]]; then
  echo "DailyDash Python not found: $python_bin" >&2
  exit 3
fi

if [[ ! -f "$config_dir/profiles/news-smart.yaml" ]]; then
  echo "Smart News profile not found: $config_dir/profiles/news-smart.yaml" >&2
  exit 4
fi

if [[ ! -f "$assets_dir/prompts/news-smart/v2/prompt.yaml" ]]; then
  echo "Smart News prompt asset not found: $assets_dir/prompts/news-smart/v2" >&2
  exit 5
fi
if [[ ! -f "$assets_dir/policies/news-smart-macro/v1/policy.yaml" ]]; then
  echo "Smart News policy asset not found: $assets_dir/policies/news-smart-macro/v1" >&2
  exit 6
fi

if [[ ! -d "$data_repo/.git" ]]; then
  echo "DailyDash data repository not found: $data_repo" >&2
  exit 7
fi

"$python_bin" -m daily_dash.commands.news_smart run \
  --config-dir "$config_dir" \
  --data-repo "$data_repo" \
  --gateway-url "$gateway_url" \
  > ./result.json
