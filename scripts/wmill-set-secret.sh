#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"

if [[ $# -lt 2 || $# -gt 3 ]]; then
  echo "Usage: $0 <environment-variable-name> <windmill-path> [description]" >&2
  exit 2
fi

env_name="$1"
remote_path="$2"
description="${3:-DailyDash secret}"

if [[ -z "${!env_name:-}" ]]; then
  echo "ERROR: environment variable '$env_name' is empty or unset" >&2
  exit 3
fi

tmp_dir="$ROOT/.windmill-tmp"
tmp_file="$tmp_dir/secret.variable.json"

mkdir -p "$tmp_dir"
chmod 700 "$tmp_dir"

cleanup() {
  rm -f "$tmp_file"
}
trap cleanup EXIT

ENV_NAME="$env_name" \
DESCRIPTION="$description" \
TMP_FILE="$tmp_file" \
uv run python - <<'PY'
import json
import os
from pathlib import Path

value = os.environ[os.environ["ENV_NAME"]]

payload = {
    "value": value,
    "is_secret": True,
    "description": os.environ["DESCRIPTION"],
    "extra_perms": {},
    "account": None,
    "is_oauth": False,
    "is_expired": False,
}

target = Path(os.environ["TMP_FILE"])
target.write_text(json.dumps(payload) + "\n", encoding="utf-8")
target.chmod(0o600)
PY

"$ROOT/scripts/wmill.sh" variable push \
  "$tmp_file" \
  "$remote_path" \
  --plain-secrets

echo "Secret uploaded: $remote_path"
