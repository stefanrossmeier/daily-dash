#!/usr/bin/env bash
set -Eeuo pipefail

# Windmill parameters.
data_repo="${1:-/data/daily-dash-data}"

app_home="${DAILY_DASH_HOME:-/opt/daily-dash}"
python_bin="$app_home/.venv/bin/python"
config_dir="${DAILY_DASH_CONFIG_DIR:-$app_home/config}"

if [[ ! -x "$python_bin" ]]; then
  echo "DailyDash Python not found: $python_bin" >&2
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

"$python_bin" -m daily_dash.commands.markets run \
  --profile markets \
  --config-dir "$config_dir" \
  --data-repo "$data_repo" \
  > ./result.json
