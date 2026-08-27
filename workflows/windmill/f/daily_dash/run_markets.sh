#!/usr/bin/env bash
set -Eeuo pipefail

# Windmill parameters.
telegram_token="$1"
telegram_chat_id="$2"
data_repo="${3:-/data/daily-dash-data}"
delivery="${4:-telegram}"

# Stable paths inside the dedicated DailyDash worker.
app_home="${DAILY_DASH_HOME:-/opt/daily-dash}"
app_bin="${DAILY_DASH_BIN:-$app_home/.venv/bin/daily-dash}"
config_dir="${DAILY_DASH_CONFIG_DIR:-$app_home/config}"

case "$delivery" in
  stdout|telegram)
    ;;
  *)
    echo "Unsupported delivery mode: $delivery" >&2
    exit 2
    ;;
esac

if [[ ! -x "$app_bin" ]]; then
  echo "DailyDash executable not found: $app_bin" >&2
  exit 3
fi

if [[ ! -d "$config_dir/profiles" ]]; then
  echo "DailyDash configuration not found: $config_dir" >&2
  exit 4
fi

if [[ ! -d "$data_repo/.git" ]]; then
  echo "DailyDash data repository not found: $data_repo" >&2
  exit 5
fi

export DAILY_DASH_TELEGRAM_TOKEN="$telegram_token"
export DAILY_DASH_TELEGRAM_CHAT_ID="$telegram_chat_id"

exec "$app_bin" \
  markets \
  --config-dir "$config_dir" \
  --data-repo "$data_repo" \
  --delivery "$delivery"
