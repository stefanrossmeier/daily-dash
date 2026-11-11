#!/usr/bin/env bash
# Deterministic post-deployment smoke test for the local Daily Dash installation.
#
# Verifies, without sending Telegram messages or making paid model calls:
#   1. the source checkout is clean and on a recorded commit
#   2. all three production containers are running
#   3. Windmill and the model gateway answer on their loopback ports
#   4. all known Windmill schedules exist and are enabled
#   5. git works against the mounted data repo from inside a job-like
#      sanitized environment (catches the 'dubious ownership' regression
#      that silently stopped all Telegram delivery after a rebuild)
#   6. no failed jobs are recorded in the worker log since its start
#
# Usage: ./scripts/smoke-test.sh
# Environment: DAILY_DASH_WINDMILL_DIR (default: ../daily-dash-windmill-local)
# Exit codes: 0 = all checks passed, 1 = at least one check failed.

set -Eeuo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DEPLOY_DIR="${DAILY_DASH_WINDMILL_DIR:-$ROOT/../daily-dash-windmill-local}"
MIN_SCHEDULES=30
GATEWAY_TIMEOUT=30

passages=0
failures=0

ok() {
  echo "PASS: $1"
  passages=$((passages + 1))
}

fail() {
  echo "FAIL: $1" >&2
  failures=$((failures + 1))
}

# ---------------------------------------------------------------- 1. source
cd "$ROOT"
if [[ -n "$(git status --porcelain)" ]]; then
  fail "source checkout is dirty: $(git status --porcelain | head -5 | tr '\n' ' ')"
else
  ok "source checkout clean at $(git rev-parse --short HEAD)"
fi

# ------------------------------------------------------------ 2. deployment
if [[ ! -f "$DEPLOY_DIR/docker-compose.yml" || ! -f "$DEPLOY_DIR/.env" ]]; then
  fail "deployment not bootstrapped: $DEPLOY_DIR"
  echo "     Run ./scripts/bootstrap-local-windmill.sh first." >&2
  exit 1
fi
dc() {
  ( cd "$DEPLOY_DIR" && docker compose "$@" )
}

for service in windmill_server windmill_worker_dailydash daily_dash_model_gateway; do
  if dc ps --status running --services 2>/dev/null | grep -qx "$service"; then
    ok "service running: $service"
  else
    fail "service not running: $service"
  fi
done

# ------------------------------------------------------------------ 3. HTTP
windmill_version="$(curl -fsS --max-time 10 http://127.0.0.1:80/api/version || true)"
if [[ "$windmill_version" =~ ^\"?CE ]]; then
  ok "Windmill API answering: $windmill_version"
else
  fail "Windmill API not answering on 127.0.0.1:80"
fi

deadline=$((SECONDS + GATEWAY_TIMEOUT))
gateway_health=""
while (( SECONDS < deadline )); do
  gateway_health="$(curl -fsS --max-time 5 http://127.0.0.1:18080/health 2>/dev/null || true)"
  [[ "$gateway_health" == '{"status":"ok"}' ]] && break
  sleep 2
done
if [[ "$gateway_health" == '{"status":"ok"}' ]]; then
  ok "model gateway healthy on 127.0.0.1:18080"
else
  fail "model gateway not healthy after ${GATEWAY_TIMEOUT}s (last: '$gateway_health')"
fi

# ------------------------------------------------------------- 4. schedules
schedules_json="$("$ROOT/scripts/wmill.sh" schedule list --json 2>/dev/null || echo '[]')"
schedule_count="$(printf '%s' "$schedules_json" | python3 -c 'import json,sys; print(len(json.load(sys.stdin)))')"
# Only daily-dash's own schedules are gated: other projects sharing the
# Windmill workspace (e.g. f/ai_dash) may legitimately keep disabled drafts.
disabled="$(printf '%s' "$schedules_json" | python3 -c 'import json,sys; print("\n".join(s["path"] for s in json.load(sys.stdin) if not s.get("enabled") and s["path"].startswith("f/daily_dash/")))')"
if (( schedule_count >= MIN_SCHEDULES )); then
  ok "schedules present: $schedule_count (minimum $MIN_SCHEDULES)"
else
  fail "too few schedules: $schedule_count (minimum $MIN_SCHEDULES)"
fi
if [[ -z "$disabled" ]]; then
  ok "all schedules enabled"
else
  fail "disabled schedules: $(echo "$disabled" | tr '\n' ' ')"
fi

# ------------------------------------------- 5. job-path git against data repo
# Windmill job processes run with a sanitized environment and their own HOME,
# so this check deliberately strips the environment the same way. If the
# system gitconfig safe.directory exception is missing from the worker image,
# this fails exactly the way persist_data_repo would.
worker_git="$(dc exec -T windmill_worker_dailydash \
  env -i /usr/bin/git -C /data/daily-dash-data rev-parse --abbrev-ref HEAD 2>/dev/null \
  | grep -x main || true)"
if [[ "$worker_git" == "main" ]]; then
  ok "worker can operate on /data/daily-dash-data from a sanitized environment (branch: main)"
else
  fail "worker git cannot read /data/daily-dash-data in a job-like environment: $worker_git"
fi

data_repo_path="$(grep -oP '^DAILY_DASH_DATA_SOURCE=\K.*' "$DEPLOY_DIR/.env" || echo /var/code/daily-dash-data)"
host_git="$(git -C "$data_repo_path" rev-parse --abbrev-ref HEAD 2>&1 || true)"
if [[ "$host_git" == "main" ]]; then
  ok "data repository on branch main"
else
  fail "data repository not on main: $host_git"
fi

# ------------------------------------------------- 6. failures since start
# Data-availability errors ("no news candidates available for ...") are
# legitimate transients caused by empty upstream feeds; everything else —
# persist failures, git errors, delivery errors — is an infrastructure
# problem the smoke test must catch.
worker_log="$(dc logs windmill_worker_dailydash 2>&1 || true)"
infra_failures="$(grep 'did not succeed' <<<"$worker_log" \
  | grep -v 'no news candidates available' \
  | grep -c . || true)"
data_warnings="$(grep 'did not succeed' <<<"$worker_log" \
  | grep -c 'no news candidates available' || true)"
if (( infra_failures == 0 )); then
  ok "no infrastructure job failures in worker log since container start"
else
  fail "$infra_failures infrastructure job failure(s) in worker log since container start"
  grep 'did not succeed' <<<"$worker_log" | grep -v 'no news candidates available' \
    | head -5 >&2
fi
if (( data_warnings > 0 )); then
  echo "WARN: $data_warnings data-availability failure(s) (empty upstream feeds; not infrastructure)"
fi

# ------------------------------------------------------------------ result
echo
echo "Smoke test: $passages passed, $failures failed"
if (( failures > 0 )); then
  exit 1
fi
exit 0
