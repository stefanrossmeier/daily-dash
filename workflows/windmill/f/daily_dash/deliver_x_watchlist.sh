# shellcheck shell=bash
set -Eeuo pipefail

artifact_path="$1"
telegram_token="$2"
telegram_chat_id="$3"

export DAILY_DASH_TELEGRAM_TOKEN="$telegram_token"
export DAILY_DASH_TELEGRAM_CHAT_ID="$telegram_chat_id"

app_home="${DAILY_DASH_HOME:-/opt/daily-dash}"
python_bin="$app_home/.venv/bin/python"

"$python_bin" -m daily_dash.commands.x_watchlist deliver \
  --artifact "$artifact_path" \
  > ./result.json
