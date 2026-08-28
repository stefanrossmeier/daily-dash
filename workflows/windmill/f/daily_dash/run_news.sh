# shellcheck shell=bash
set -Eeuo pipefail

# arguments of the form X="$I" are parsed as Windmill string parameters
profile="$1"

case "$profile" in
  news-top|news-alternative|news-german) ;;
  *) echo "invalid news profile: $profile" >&2; exit 2 ;;
esac

app_home="${DAILY_DASH_HOME:-/opt/daily-dash}"
python_bin="$app_home/.venv/bin/python"
config_dir="${DAILY_DASH_CONFIG_DIR:-$app_home/config}"
assets_dir="${DAILY_DASH_ASSETS_DIR:-$app_home/assets}"
data_repo="${DAILY_DASH_DATA_REPO:-/data/daily-dash-data}"
gateway_url="${DAILY_DASH_MODEL_GATEWAY_URL:-http://daily_dash_model_gateway:8080}"

export DAILY_DASH_HOME="$app_home"
export DAILY_DASH_CONFIG_DIR="$config_dir"
export DAILY_DASH_ASSETS_DIR="$assets_dir"
export DAILY_DASH_DATA_REPO="$data_repo"
export DAILY_DASH_MODEL_GATEWAY_URL="$gateway_url"

if [[ ! -d "$assets_dir/prompts" ]]; then
  echo "DailyDash prompt assets not found: $assets_dir" >&2
  exit 3
fi

if [[ ! -f "$config_dir/schedules.yaml" ]]; then
  echo "DailyDash schedule registry not found: $config_dir/schedules.yaml" >&2
  exit 4
fi

"$python_bin" -m daily_dash.commands.news run \
  --profile "$profile" \
  --config-dir "$config_dir" \
  --data-repo "$data_repo" \
  --gateway-url "$gateway_url" \
  > ./result.json
