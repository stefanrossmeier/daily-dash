#!/usr/bin/env bash
# Deterministic post-deployment smoke test for the local Daily Dash installation.
#
# Verifies, without sending Telegram messages or making paid model calls:
#   1. the source checkout is clean and on a recorded commit
#   2. all production containers are running, including daily-dash's dedicated
#      llm-gateway instance
#   3. Windmill and the model gateway answer on their loopback ports, and the
#      llm-gateway instance authenticates this project's principal
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
GATEWAY_VERSION="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["version"])' "$ROOT/deploy/llm-gateway-release.json")"
GATEWAY_VERSION_FRAGMENT="\"version\":\"$GATEWAY_VERSION\""

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

for service in windmill_server windmill_worker_dailydash; do
  if dc ps --status running --services 2>/dev/null | grep -qx "$service"; then
    ok "service running: $service"
  else
    fail "service not running: $service"
  fi
done

# Dedicated llm-gateway instance: its own container, joined to this stack's
# network, holding this project's config/secret/ledger. It serves every
# ranking chat and the native X retrieval, so a missing instance silently
# breaks both even while the rest of the stack looks healthy.
GATEWAY_TOKEN_SOURCE="${DAILY_DASH_GATEWAY_TOKEN_SOURCE:-/var/code/llm-gateway-deployments/daily-dash/tokens/gateway.token}"
# The instance is run as its own Compose project, so its container name carries
# a "-<n>" suffix; match the prefix rather than one exact name.
if docker ps --format '{{.Names}}' 2>/dev/null | grep -q '^daily-dash-llm-gateway'; then
  ok "service running: daily-dash-llm-gateway (dedicated instance)"
else
  fail "service not running: daily-dash-llm-gateway"
fi

# The worker reaches the instance over TCP with the token mounted into it;
# /ready must report THIS project's identity. The token directory belongs to
# the instance's own runtime user, so the operator account cannot necessarily
# read it on the host — that is a hardening choice, not a defect. Only note it;
# the in-worker probe below is the real gate.
if [[ ! -r "$GATEWAY_TOKEN_SOURCE" ]]; then
  echo "INFO: token file not readable by the operator account ($GATEWAY_TOKEN_SOURCE); verifying through the worker instead"
fi
instance_ready=""
deadline=$((SECONDS + GATEWAY_TIMEOUT))
while (( SECONDS < deadline )); do
  instance_ready="$(dc exec -T windmill_worker_dailydash /opt/daily-dash/.venv/bin/python -c "
import urllib.request
token = open('/run/daily-dash-secrets/gateway_token').read().strip()
request = urllib.request.Request('http://daily-dash-llm-gateway:8080/ready', headers={'Authorization': 'Bearer ' + token})
print(urllib.request.urlopen(request, timeout=10).read().decode())" 2>/dev/null || true)"
  [[ "$instance_ready" == *'"project_id":"daily-dash"'* && "$instance_ready" == *"$GATEWAY_VERSION_FRAGMENT"* ]] && break
  sleep 2
done
if [[ "$instance_ready" == *'"project_id":"daily-dash"'* && "$instance_ready" == *"$GATEWAY_VERSION_FRAGMENT"* ]]; then
  ok "llm-gateway $GATEWAY_VERSION ready and principal authenticated (project daily-dash)"
else
  fail "llm-gateway instance not ready from the worker after ${GATEWAY_TIMEOUT}s (last: '$instance_ready')"
fi

# ------------------------------------------------------------------ 3. HTTP
windmill_version="$(curl -fsS --max-time 10 http://127.0.0.1:80/api/version || true)"
if [[ "$windmill_version" =~ ^\"?CE ]]; then
  ok "Windmill API answering: $windmill_version"
else
  fail "Windmill API not answering on 127.0.0.1:80"
fi

deadline=$((SECONDS + GATEWAY_TIMEOUT))

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
