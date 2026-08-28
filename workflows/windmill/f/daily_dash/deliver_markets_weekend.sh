# shellcheck shell=bash
set -Eeuo pipefail

artifact_path="$1"
telegram_token="$2"
telegram_chat_id="$3"

export DAILY_DASH_TELEGRAM_TOKEN="$telegram_token"
export DAILY_DASH_TELEGRAM_CHAT_ID="$telegram_chat_id"

python_bin="${DAILY_DASH_HOME:-/opt/daily-dash}/.venv/bin/python"
config_dir="${DAILY_DASH_CONFIG_DIR:-/opt/daily-dash/config}"

"$python_bin" -m daily_dash.commands.markets_weekend deliver \
  --artifact "$artifact_path" \
  --config-dir "$config_dir" \
  > ./result.json
