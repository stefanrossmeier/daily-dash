#!/usr/bin/env bash
set -Eeuo pipefail

cd "$(dirname "$0")/.."

uv run ruff format .
uv run ruff check . --fix
