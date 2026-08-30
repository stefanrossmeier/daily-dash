#!/usr/bin/env bash
set -Eeuo pipefail

data_repo="${1:-${DAILY_DASH_DATA_REPO:-/data/daily-dash-data}}"
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

if [[ ! -x "$python_bin" ]]; then
  echo "DailyDash Python not found: $python_bin" >&2
  exit 3
fi
if [[ ! -f "$config_dir/profiles/x-watchlist.yaml" ]]; then
  echo "X Watchlist profile not found: $config_dir/profiles/x-watchlist.yaml" >&2
  exit 4
fi
if [[ ! -f "$assets_dir/prompts/x-watchlist-retrieval/v4/prompt.yaml" ]]; then
  echo "X Watchlist retrieval prompt not found" >&2
  exit 5
fi
if [[ ! -f "$assets_dir/prompts/x-watchlist-ranking/v4/prompt.yaml" ]]; then
  echo "X Watchlist ranking prompt not found" >&2
  exit 6
fi
if [[ ! -d "$data_repo/.git" ]]; then
  echo "DailyDash data repository not found: $data_repo" >&2
  exit 7
fi

"$python_bin" -m daily_dash.commands.x_watchlist run \
  --config-dir "$config_dir" \
  --data-repo "$data_repo" \
  --gateway-url "$gateway_url" \
  > ./result.json
