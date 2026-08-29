#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

./scripts/check.sh

uv run python -m daily_dash.experiments.grok_x_search "$@"
