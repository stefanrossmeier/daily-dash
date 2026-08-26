#!/usr/bin/env bash
set -Eeuo pipefail

cd "$(dirname "$0")/.."

echo
echo "==> Syncing locked environment"
uv sync --locked

echo
echo "==> Checking formatting"
uv run ruff format --check .

echo
echo "==> Running Ruff"
uv run ruff check .

echo
echo "==> Running mypy"
uv run mypy src

echo
echo "==> Running tests with coverage"
uv run pytest \
  --strict-config \
  --strict-markers \
  --cov=daily_dash \
  --cov-report=term-missing

echo
echo "==> Validating configuration"
uv run daily-dash validate-config

echo
echo "==> Checking package build"
rm -rf dist
uv build
rm -rf dist

echo
echo "==> DailyDash checks passed"
