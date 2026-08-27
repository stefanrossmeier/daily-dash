#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
WMILL="$ROOT/node_modules/.bin/wmill"

if [[ ! -x "$WMILL" ]]; then
  echo "Windmill CLI is not installed." >&2
  echo "Run: npm ci" >&2
  exit 1
fi

exec "$WMILL" "$@"
