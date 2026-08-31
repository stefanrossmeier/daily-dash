# VPS deployment

This runbook takes a fresh Linux VPS from an empty host to a running DailyDash installation with
self-hosted Windmill, persistent Git-backed artifacts, scheduled reports, model-backed processing,
and Telegram delivery.

It is written for a **single-operator VPS** using Docker Compose. The deployment profile documented
here is the one that has been validated end to end in production-style smoke tests.

DailyDash keeps its source checkout, private data checkout, and generated runtime definition together
under one operator-owned root:

```text
/var/code/
├── daily-dash/                  # public Git checkout
├── daily-dash-data/             # private Git checkout used as the artifact sink
└── daily-dash-windmill-local/   # generated/private runtime; NOT a Git checkout
    ├── .env                     # Compose/runtime paths and infrastructure settings
    ├── docker-compose.yml
    ├── docker-compose.override.yml
    ├── Caddyfile
    └── secrets/                 # one-value local secret files
```

`daily-dash-windmill-local` is intentionally generated from deployment templates committed in
`daily-dash/deploy/local-windmill/`. It is private machine state, not a third repository.

Docker-managed volumes, including the Windmill PostgreSQL volume, remain in Docker's storage area,
normally under `/var/lib/docker`.

> [!IMPORTANT]
> This guide deliberately uses explicit `/var/code/...` paths. Do not rely on bootstrap
> sibling-directory defaults on a production host.

> [!IMPORTANT]
> The validated deployment keeps Windmill private on the VPS and accesses its UI through an SSH
> tunnel. Public HTTP/HTTPS exposure is **not required** for DailyDash to run scheduled reports.

---

## 1. Validated production state

The production-style deployment has been validated with the following invariant:

```text
run
→ persist_data
→ deliver
```

The following reports have completed end to end on the VPS:

```text
Markets
Top News
Futures
WSB
X Watchlist
Polymarket
Yields
German News
Alternative News
Smart News
Weekend Markets
```

The validated infrastructure path is:

```text
Windmill schedules
    |
    v
DailyDash dedicated Windmill worker
    |
    +--> external retrieval/data sources
    |
    +--> DailyDash model gateway when required
    |
    +--> /data/daily-dash-data
    |       |
    |       +--> Git commit
    |       +--> GitHub push
    |
    +--> Telegram delivery
```

The validated host bindings are:

```text
Windmill bundled Caddy:  127.0.0.1:80
DailyDash model gateway: 127.0.0.1:18080
PostgreSQL:               internal Docker network only
Windmill workers:         internal Docker network only
```

Human access to Windmill is through SSH port forwarding.

A reboot-recovery test is recommended but is not required to prove that the currently running
deployment is operational.

---

## 2. Before you start

You need:

- a VPS running a currently supported Ubuntu or Debian release;
- SSH access with a sudo-capable non-root operator account;
- a GitHub account with access to `daily-dash-data`;
- an OpenRouter API key;
- a Telegram bot token and target chat/channel ID;
- Reddit API credentials if the WSB report is enabled.

The current application/tooling requirements are:

- Git;
- Docker Engine and the Docker Compose plugin;
- `uv` matching the range declared in `pyproject.toml`;
- Node.js **>20** and npm, used for the pinned Windmill CLI;
- curl;
- OpenSSH client/server;
- `jq` is useful for diagnostics but not required by the core application.

Use the official installation instructions for your distribution:

- Docker Engine: <https://docs.docker.com/engine/install/>
- Docker Compose plugin: <https://docs.docker.com/compose/install/linux/>
- uv: <https://docs.astral.sh/uv/getting-started/installation/>
- Node.js: <https://nodejs.org/en/download>

Verify:

```bash
git --version
uv --version
node --version
npm --version
docker --version
docker compose version
curl --version
ssh -V
```

The operator user must be able to run Docker.

If the user is added to the `docker` group, remember that Docker access is effectively
root-equivalent host access.

---

## 3. SSH access and host preparation

### 3.1 Connect to the VPS

From the workstation:

```bash
ssh OPERATOR@VPS_HOST
```

Use key-based authentication.

For convenience, an SSH config entry may be used on the workstation:

```sshconfig
Host daily-dash-vps
    HostName VPS_HOST
    User OPERATOR
    IdentityFile ~/.ssh/YOUR_PRIVATE_KEY
```

Then connect with:

```bash
ssh daily-dash-vps
```

### 3.2 Prepare `/var/code`

On the VPS:

```bash
sudo mkdir -p /var/code
sudo chown "$USER":"$USER" /var/code
chmod 755 /var/code
```

The final layout should be:

```text
/var/code/daily-dash
/var/code/daily-dash-data
/var/code/daily-dash-windmill-local
```

### 3.3 Firewall

The validated private deployment requires only SSH to be publicly reachable.

Do **not** publicly expose:

```text
PostgreSQL
Windmill worker ports
DailyDash model gateway
Windmill bundled Caddy
```

A minimal UFW setup when SSH uses the standard OpenSSH profile is:

```bash
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow OpenSSH
sudo ufw enable
sudo ufw status verbose
```

If SSH uses a custom port, allow that port before enabling the firewall.

If public HTTPS access is intentionally added later, open ports 80 and 443 only after a reverse proxy
has been configured securely.

### 3.4 Do not disturb unrelated Docker applications

If the VPS also hosts other applications, scope DailyDash Docker commands to:

```text
/var/code/daily-dash-windmill-local
```

Do not use broad host-wide cleanup commands such as:

```bash
docker system prune -a
```

unless you have separately verified their impact on every application on the host.

---

## 4. Clone DailyDash

Clone the public application repository:

```bash
git clone https://github.com/stefanrossmeier/daily-dash.git \
  /var/code/daily-dash

cd /var/code/daily-dash
```

Install the pinned Windmill CLI dependencies and run the repository checks:

```bash
npm ci
./scripts/check-tools.sh
./scripts/check.sh
```

Do not continue with a production deployment if the repository quality gate is red.

---

## 5. Prepare the private data repository

DailyDash persists immutable report artifacts to a separate Git repository before Telegram delivery.

Create `daily-dash-data` in GitHub first with a `main` branch, then clone it to:

```bash
git clone git@github.com:YOUR_ACCOUNT/daily-dash-data.git \
  /var/code/daily-dash-data
```

An HTTPS clone is also acceptable for the operator checkout if preferred:

```bash
git clone https://github.com/YOUR_ACCOUNT/daily-dash-data.git \
  /var/code/daily-dash-data
```

Verify:

```bash
git -C /var/code/daily-dash-data status -sb
git -C /var/code/daily-dash-data remote -v
```

The runtime persistence job uses its own dedicated SSH deploy key. It does **not** depend on the
operator checkout's authentication method.

---

## 6. Materialize or preserve the private Windmill runtime

### 6.1 Fresh VPS

From `/var/code/daily-dash`:

```bash
./scripts/bootstrap-local-windmill.sh \
  --target /var/code/daily-dash-windmill-local \
  --data-repo /var/code/daily-dash-data
```

Set the runtime path:

```bash
export DAILY_DASH_WINDMILL_DIR=/var/code/daily-dash-windmill-local
```

Inspect:

```bash
cat /var/code/daily-dash-windmill-local/.env
```

The important paths should be:

```text
DAILY_DASH_SOURCE=/var/code/daily-dash
DAILY_DASH_DATA_SOURCE=/var/code/daily-dash-data
DAILY_DASH_OPENROUTER_KEY_FILE=/var/code/daily-dash-windmill-local/secrets/openrouter_api_key
```

### 6.2 Existing VPS runtime

If `/var/code/daily-dash-windmill-local` already exists and contains real configuration or secrets:

**do not delete it and do not blindly bootstrap over it.**

Inspect first:

```bash
cd /var/code/daily-dash-windmill-local

ls -la
ls -la secrets
docker compose config >/dev/null
```

Avoid:

```bash
./scripts/bootstrap-local-windmill.sh --force
```

unless you intentionally want to refresh generated files and will reapply all VPS-specific runtime
changes documented below.

---

## 7. Canonical secrets

The runtime secrets directory is:

```text
/var/code/daily-dash-windmill-local/secrets/
├── openrouter_api_key
├── data_repo_deploy_key
├── telegram_token
├── telegram_chat_id
├── reddit_client_id
├── reddit_client_secret
└── reddit_user_agent
```

Protect it:

```bash
chmod 700 /var/code/daily-dash-windmill-local/secrets
chmod 600 /var/code/daily-dash-windmill-local/secrets/*
```

Application credentials belong here, not in the public Git checkout and not in a repository-root
`.env`.

### 7.1 OpenRouter

Enter the key interactively:

```bash
read -r -s -p 'OpenRouter API key: ' SECRET_VALUE
printf '\n'

printf '%s' "$SECRET_VALUE" > \
  /var/code/daily-dash-windmill-local/secrets/openrouter_api_key

unset SECRET_VALUE
chmod 600 /var/code/daily-dash-windmill-local/secrets/openrouter_api_key
```

Do not include shell assignments, quotes, spaces, or trailing newlines in the file.

### 7.2 Telegram

Enter the token without placing it in shell history:

```bash
read -r -s -p 'Telegram bot token: ' SECRET_VALUE
printf '\n'

printf '%s' "$SECRET_VALUE" > \
  /var/code/daily-dash-windmill-local/secrets/telegram_token

unset SECRET_VALUE
chmod 600 /var/code/daily-dash-windmill-local/secrets/telegram_token
```

Enter the chat/channel ID:

```bash
read -r -p 'Telegram chat/channel ID: ' SECRET_VALUE

printf '%s' "$SECRET_VALUE" > \
  /var/code/daily-dash-windmill-local/secrets/telegram_chat_id

unset SECRET_VALUE
chmod 600 /var/code/daily-dash-windmill-local/secrets/telegram_chat_id
```

Check the Telegram token for accidental whitespace without displaying it:

```bash
if grep -q '[[:space:]]' \
  /var/code/daily-dash-windmill-local/secrets/telegram_token
then
  echo 'ERROR: Telegram token contains whitespace'
else
  echo 'Telegram token format looks clean'
fi
```

Test the token directly:

```bash
TOKEN="$(
  cat /var/code/daily-dash-windmill-local/secrets/telegram_token
)"

curl --fail --silent --show-error \
  "https://api.telegram.org/bot${TOKEN}/getMe"

unset TOKEN
echo
```

Expected result includes:

```json
{"ok":true}
```

> [!SECURITY]
> If a bot token is ever printed into logs, pasted into chat, committed, or otherwise disclosed,
> revoke/rotate it through BotFather and replace the secret file. Do not continue using an exposed
> token merely because it still works.

### 7.3 Reddit

The WSB report requires:

```text
reddit_client_id
reddit_client_secret
reddit_user_agent
```

Use a real descriptive User-Agent, for example:

```text
wsb-dashboard/1.0 (by u/YOUR_REDDIT_USERNAME)
```

Do not leave placeholder text such as:

```text
u/deinusername
```

---

## 8. Configure the data-repository deploy key

The Windmill persistence job needs a dedicated SSH key with write access to `daily-dash-data`.

Remove an empty bootstrap placeholder if necessary:

```bash
rm -f \
  /var/code/daily-dash-windmill-local/secrets/data_repo_deploy_key \
  /var/code/daily-dash-windmill-local/secrets/data_repo_deploy_key.pub
```

Generate:

```bash
ssh-keygen \
  -t ed25519 \
  -C 'daily-dash-data-vps' \
  -f /var/code/daily-dash-windmill-local/secrets/data_repo_deploy_key \
  -N ''
```

Set permissions:

```bash
chmod 600 \
  /var/code/daily-dash-windmill-local/secrets/data_repo_deploy_key

chmod 644 \
  /var/code/daily-dash-windmill-local/secrets/data_repo_deploy_key.pub
```

Display only the public key:

```bash
cat /var/code/daily-dash-windmill-local/secrets/data_repo_deploy_key.pub
```

In GitHub:

```text
daily-dash-data
→ Settings
→ Deploy keys
→ Add deploy key
→ Allow write access
```

The private key must remain only on the VPS.

Populate GitHub's host key for the operator account:

```bash
mkdir -p ~/.ssh
chmod 700 ~/.ssh

ssh-keyscan github.com >> ~/.ssh/known_hosts
chmod 600 ~/.ssh/known_hosts
```

Test read access through the dedicated key:

```bash
GIT_SSH_COMMAND="ssh \
  -i /var/code/daily-dash-windmill-local/secrets/data_repo_deploy_key \
  -o IdentitiesOnly=yes" \
git ls-remote \
  git@github.com:YOUR_ACCOUNT/daily-dash-data.git \
  HEAD
```

Test write authorization without pushing:

```bash
cd /var/code/daily-dash-data

GIT_SSH_COMMAND="ssh \
  -i /var/code/daily-dash-windmill-local/secrets/data_repo_deploy_key \
  -o IdentitiesOnly=yes" \
git push --dry-run \
  git@github.com:YOUR_ACCOUNT/daily-dash-data.git \
  HEAD:main
```

The Windmill variable for the remote should use the SSH URL:

```text
git@github.com:YOUR_ACCOUNT/daily-dash-data.git
```

---

## 9. Harden the generated runtime

### 9.1 Replace the default PostgreSQL password

If the generated template still uses `changeme`, replace it before production use.

```bash
RUNTIME=/var/code/daily-dash-windmill-local
DB_PASSWORD="$(openssl rand -hex 32)"

sed -i "s#postgres:changeme@db#postgres:${DB_PASSWORD}@db#" \
  "$RUNTIME/.env"

sed -i "s#POSTGRES_PASSWORD: changeme#POSTGRES_PASSWORD: ${DB_PASSWORD}#" \
  "$RUNTIME/docker-compose.yml"

unset DB_PASSWORD
chmod 600 "$RUNTIME/.env"
```

Verify without printing the password:

```bash
grep -q 'changeme' "$RUNTIME/.env" \
  && echo 'ERROR: default DB password remains' \
  || echo 'DB URL hardened'

grep -q 'POSTGRES_PASSWORD: changeme' "$RUNTIME/docker-compose.yml" \
  && echo 'ERROR: default DB password remains in Compose' \
  || echo 'Compose DB password hardened'
```

### 9.2 Do not publish Windmill SMTP

DailyDash does not require Windmill SMTP.

Do not expose:

```yaml
- 25:25
```

unless SMTP is deliberately configured and secured.

### 9.3 Bind the Windmill bundled Caddy to loopback port 80

The repository's Windmill workspace configuration uses:

```text
base URL: http://localhost
```

To make the Windmill CLI profile and checked-in `wmill.yaml` resolve consistently on the VPS, bind
the bundled Windmill Caddy to **loopback port 80**:

```yaml
ports:
  - 127.0.0.1:80:80
```

If the generated runtime currently contains:

```yaml
- 127.0.0.1:8080:80
```

change it:

```bash
cd /var/code/daily-dash-windmill-local

sed -i \
  's/127\.0\.0\.1:8080:80/127.0.0.1:80:80/' \
  docker-compose.yml
```

Verify:

```bash
grep -n -A4 'ports:' docker-compose.yml
docker compose config >/dev/null
```

Restart only the bundled Caddy when only this mapping changed:

```bash
docker compose up -d --force-recreate caddy
```

Verify:

```bash
curl --fail http://127.0.0.1/api/version
echo
```

Expected:

```text
CE v1.775.1
```

Port 8080 should no longer answer:

```bash
curl --fail http://127.0.0.1:8080/api/version
```

A connection failure there is expected in this deployment profile.

The Windmill endpoint remains private because it is bound only to `127.0.0.1`.

---

## 10. Build/start the DailyDash stack

From the public checkout:

```bash
cd /var/code/daily-dash

export DAILY_DASH_WINDMILL_DIR=/var/code/daily-dash-windmill-local
```

For a fresh start:

```bash
./scripts/local-windmill.sh up
```

After application/dependency changes, or before first validation of a newly copied checkout, rebuild
the custom DailyDash worker and model gateway:

```bash
./scripts/local-windmill.sh rebuild
```

Check status:

```bash
./scripts/local-windmill.sh status
```

If needed, inspect directly:

```bash
cd /var/code/daily-dash-windmill-local
docker compose ps
```

Expected critical components include:

```text
db
windmill_server
windmill_worker
windmill_worker_native
windmill_worker_dailydash
daily_dash_model_gateway
caddy
```

Verify Windmill:

```bash
curl --fail http://127.0.0.1/api/version
echo
```

Verify the model gateway:

```bash
curl --fail http://127.0.0.1:18080/health
echo
```

Expected:

```text
CE v1.775.1
{"status":"ok"}
```

The Compose warning:

```text
the attribute `version` is obsolete
```

is informational and does not prevent the stack from running.

---

## 11. Access Windmill over SSH

The validated setup does not expose Windmill publicly.

### 11.1 Start the tunnel from the workstation

Keep this command running in a dedicated terminal on the workstation:

```bash
ssh -N \
  -L 19080:127.0.0.1:80 \
  OPERATOR@VPS_HOST
```

If using an SSH config alias:

```bash
ssh -N \
  -L 19080:127.0.0.1:80 \
  daily-dash-vps
```

### 11.2 Open Windmill locally

On the workstation, browse to:

```text
http://127.0.0.1:19080
```

The browser talks to local port `19080`; SSH forwards it securely to the VPS loopback interface on
port `80`.

No Windmill port needs to be exposed on the public Internet.

### 11.3 Initial Windmill bootstrap

On a fresh Windmill instance:

1. complete the initial administrator setup;
2. replace bootstrap/default administrator credentials immediately;
3. create a workspace with ID `daily-dash-workspace`;
4. create a Windmill API token from Account settings;
5. keep that token only in the operator's Windmill CLI configuration.

Treat the CLI token like a password.

---

## 12. Configure the Windmill CLI workspace

The canonical CLI profile is:

```text
profile:      daily-dash-local
workspace id: daily-dash-workspace
base URL:     http://localhost
```

From `/var/code/daily-dash`:

```bash
./scripts/wmill.sh workspace add \
  daily-dash-local \
  daily-dash-workspace \
  http://localhost
```

Choose token authentication and paste the Windmill API token when prompted.

Verify:

```bash
./scripts/wmill.sh workspace
./scripts/wmill.sh workspace list
```

Expected shape:

```text
name              remote             workspace id
daily-dash-local  http://localhost/  daily-dash-workspace

Active: daily-dash-local
```

### 12.1 Recover from an incorrect profile

A common failure is having a profile that points to:

```text
http://127.0.0.1:8080/
```

while `wmill.yaml` expects:

```text
http://localhost/
```

Symptoms during sync:

```text
No profile found for workspace 'daily-dash-local'
No workspace profile found for branch 'daily-dash-local'
Network error: Could not connect to Windmill server at http://localhost/
```

Remove incorrect profiles:

```bash
cd /var/code/daily-dash

./scripts/wmill.sh workspace remove daily-dash-workspace
./scripts/wmill.sh workspace remove daily-dash-local
```

Recreate the canonical profile:

```bash
./scripts/wmill.sh workspace add \
  daily-dash-local \
  daily-dash-workspace \
  http://localhost
```

Verify again:

```bash
./scripts/wmill.sh workspace
```

Do not solve this by changing the checked-in workspace definition to an installation-specific port.

---

## 13. Configure DailyDash Windmill variables and secrets

Set the installation-specific runtime values:

```bash
cd /var/code/daily-dash

export DAILY_DASH_WINDMILL_DIR=/var/code/daily-dash-windmill-local
export DAILY_DASH_DATA_REPO_REMOTE_URL="git@github.com:YOUR_ACCOUNT/daily-dash-data.git"
export DAILY_DASH_DATA_REPO_BRANCH=main
```

Upload persistence and Telegram values:

```bash
./scripts/configure-windmill-workspace.sh
```

This creates or updates:

```text
f/daily_dash/data_repo_remote_url     variable
f/daily_dash/data_repo_branch         variable
f/daily_dash/data_repo_deploy_key     secret
f/daily_dash/telegram_token           secret
f/daily_dash/telegram_chat_id         secret
```

The OpenRouter root API key is not uploaded through this helper. It remains mounted into the model
gateway from the private secret file.

---

## 14. Configure and validate Reddit / WSB

Configure Reddit and upload it to Windmill:

```bash
cd /var/code/daily-dash

./scripts/configure-wsb-reddit.sh \
  --windmill-dir /var/code/daily-dash-windmill-local \
  --windmill
```

A successful credential check should include:

```json
{"status":"ok","provider":"reddit-oauth"}
```

The helper uploads:

```text
f/daily_dash/reddit_client_id
f/daily_dash/reddit_client_secret
f/daily_dash/reddit_user_agent
```

### Reddit `401 Unauthorized`

If the OAuth token request returns `401 Unauthorized`, the failure occurs before subreddit access.

Check:

- client ID;
- client secret;
- Reddit application type/configuration;
- accidental whitespace;
- whether the credential pair is the same known-good pair used elsewhere.

Also replace placeholder User-Agent text with a real value.

Do not troubleshoot model-gateway/OpenRouter configuration for a Reddit OAuth `401`; they are
independent systems.

---

## 15. Validate the model gateway

Check health:

```bash
curl --fail --silent --show-error \
  http://127.0.0.1:18080/health

echo
```

Then execute a real inexpensive ranking smoke test:

```bash
cd /var/code/daily-dash

./scripts/smoke-model-gateway.sh rank-cheap
```

A successful result proves:

```text
gateway process is healthy
OpenRouter secret is mounted/readable
provider request succeeds
configured rank-cheap alias works
```

---

## 16. Synchronize Windmill flows and schedules

From the public repository:

```bash
cd /var/code/daily-dash

./scripts/sync-windmill-workspace.sh
```

The helper:

- regenerates derived News flows/schedules;
- runs focused Windmill contract tests;
- matches the active `daily-dash-local` workspace profile;
- pushes versioned scripts, flows, and schedules to Windmill.

Successful startup output should contain:

```text
Using workspace profile 'daily-dash-local'
for workspace 'daily-dash-local'
(daily-dash-workspace on http://localhost/)
```

The first sync to a fresh workspace can create a large number of assets. That is expected.

Warnings about stale generated script metadata do not necessarily prevent the sync; the final
`Done! ... pushed` message is the important result.

Secrets and installation-specific variables are not sourced from Git synchronization.

---

## 17. Configure Git safe-directory handling for the mounted data repository

The host checkout is owned by the non-root operator, while the dedicated DailyDash worker currently
runs as root inside the container.

Example:

```text
host owner:      1000:1000
container user:  root
mount:           /var/code/daily-dash-data -> /data/daily-dash-data
```

Modern Git can reject the repository with:

```text
fatal: detected dubious ownership in repository at '/data/daily-dash-data'
```

Apply the worker-side trust entry:

```bash
cd /var/code/daily-dash-windmill-local

docker compose exec -T windmill_worker_dailydash \
  git config --global --add \
  safe.directory /data/daily-dash-data
```

Verify:

```bash
docker compose exec -T windmill_worker_dailydash \
  git config --global --get-all safe.directory
```

Expected:

```text
/data/daily-dash-data
```

Then:

```bash
docker compose exec -T windmill_worker_dailydash \
  git -C /data/daily-dash-data status --short
```

It should run without a `dubious ownership` error.

> [!WARNING]
> This setting is stored inside the running worker container. It survives an ordinary stop/start of
> that same container, but may be lost when `windmill_worker_dailydash` is recreated or rebuilt.
> Until the worker image/runtime template configures this durably, recheck this setting after
> `./scripts/local-windmill.sh rebuild`.

Do **not** recursively `chown` the host data repository to root as a first response. The host operator
should continue to own `/var/code/daily-dash-data`.

---

## 18. End-to-end production smoke tests

The most important acceptance rule for every production flow is:

```text
run
→ persist_data
→ deliver
```

Run the flows from:

```bash
cd /var/code/daily-dash/workflows/windmill
```

### 18.1 Markets

```bash
../../scripts/wmill.sh flow run f/daily_dash/markets
```

Validates:

```text
deterministic market retrieval
worker execution
Git persistence
deploy-key push
Telegram delivery
```

### 18.2 Top News

```bash
../../scripts/wmill.sh flow run f/daily_dash/news_top
```

Validates:

```text
news retrieval
model gateway
ranking/processing
Git persistence
Telegram delivery
```

### 18.3 Futures

```bash
../../scripts/wmill.sh flow run f/daily_dash/futures
```

Validates:

```text
TradingView/tvDatafeed WebSocket path
custom protocol compatibility
deterministic processing
Git persistence
Telegram delivery
```

No TradingView credential is required by the current adapter; it uses anonymous access.

### 18.4 WSB

```bash
../../scripts/wmill.sh flow run f/daily_dash/wsb
```

Validates Reddit OAuth plus the normal model/persistence/delivery path.

### 18.5 X Watchlist

```bash
../../scripts/wmill.sh flow run f/daily_dash/x_watchlist
```

Validates the Grok/OpenRouter X retrieval path and downstream ranking.

### 18.6 Polymarket

```bash
../../scripts/wmill.sh flow run f/daily_dash/polymarket
```

### 18.7 Yields

```bash
../../scripts/wmill.sh flow run f/daily_dash/yields
```

### 18.8 German News

```bash
../../scripts/wmill.sh flow run f/daily_dash/news_german
```

### 18.9 Alternative News

```bash
../../scripts/wmill.sh flow run f/daily_dash/news_alternative
```

### 18.10 Smart News

```bash
../../scripts/wmill.sh flow run f/daily_dash/news_smart
```

### 18.11 Weekend Markets

```bash
../../scripts/wmill.sh flow run f/daily_dash/markets_weekend
```

For every flow confirm:

1. the `run_*` stage succeeds;
2. the persistence stage succeeds;
3. a commit is pushed to `daily-dash-data`;
4. the delivery stage succeeds;
5. the Telegram report is received;
6. user-facing text does not expose internal ranking/model/debug metadata.

---

## 19. Verify data-repository persistence

After smoke tests:

```bash
git -C /var/code/daily-dash-data status -sb
git -C /var/code/daily-dash-data log -15 --oneline
```

The worker may have pushed commits while the host checkout's `origin/main` reference remains stale.

This can make status temporarily show something like:

```text
## main...origin/main [ahead N]
```

Refresh the remote-tracking reference:

```bash
git -C /var/code/daily-dash-data fetch origin
```

Then compare:

```bash
printf 'local:  '
git -C /var/code/daily-dash-data rev-parse HEAD

printf 'remote: '
git -C /var/code/daily-dash-data rev-parse origin/main
```

For the normal synchronized state, the hashes should match.

Do not reset or force-push merely because the local remote-tracking reference was stale.

---

## 20. Telegram delivery troubleshooting

### Symptom: Telegram `404 Not Found`

If a delivery URL contains:

```text
%20/sendMessage
```

then the token contains a trailing space.

Example diagnostic only:

```text
https://api.telegram.org/bot<TOKEN>%20/sendMessage
```

Rewrite the local secret using `printf '%s'`, not a copied value containing whitespace:

```bash
read -r -s -p 'Telegram bot token: ' TELEGRAM_TOKEN
printf '\n'

printf '%s' "$TELEGRAM_TOKEN" > \
  /var/code/daily-dash-windmill-local/secrets/telegram_token

unset TELEGRAM_TOKEN
```

Check:

```bash
if grep -q '[[:space:]]' \
  /var/code/daily-dash-windmill-local/secrets/telegram_token
then
  echo 'ERROR: Telegram token contains whitespace'
else
  echo 'Telegram token format looks clean'
fi
```

Re-upload the corrected secret:

```bash
cd /var/code/daily-dash

export DAILY_DASH_WINDMILL_DIR=/var/code/daily-dash-windmill-local
export DAILY_DASH_DATA_REPO_REMOTE_URL="git@github.com:YOUR_ACCOUNT/daily-dash-data.git"
export DAILY_DASH_DATA_REPO_BRANCH=main

./scripts/configure-windmill-workspace.sh
```

No Windmill workspace sync is required for a secret-only change.

If the token was exposed while diagnosing the problem, rotate it before continuing.

---

## 21. Futures-specific worker rebuild note

When new application modules are added, an old dedicated worker image can remain stale.

A symptom previously seen is:

```text
/opt/daily-dash/.venv/bin/python:
No module named daily_dash.commands.futures
```

The fix is to rebuild the custom DailyDash containers from the current checkout:

```bash
cd /var/code/daily-dash

export DAILY_DASH_WINDMILL_DIR=/var/code/daily-dash-windmill-local

./scripts/local-windmill.sh rebuild
```

Then verify:

```bash
./scripts/local-windmill.sh status

curl --fail http://127.0.0.1/api/version
echo

curl --fail http://127.0.0.1:18080/health
echo
```

After a worker rebuild, also re-check:

```bash
cd /var/code/daily-dash-windmill-local

docker compose exec -T windmill_worker_dailydash \
  git config --global --get-all safe.directory
```

and reapply `/data/daily-dash-data` if necessary.

---

## 22. Schedules and continuous operation

All production schedules are versioned under:

```text
workflows/windmill/f/daily_dash/
```

and use `Europe/Berlin` where configured.

Once:

```text
workspace sync succeeds
manual flows succeed
schedules are enabled
Windmill is running
```

no additional cron process is required. Windmill executes the schedules itself.

The repository is authoritative for cadence; see [`SCHEDULING.md`](SCHEDULING.md).

Before leaving the system unattended, verify schedules in the Windmill UI through the SSH tunnel.

Expected production reports include schedules for:

```text
Markets
Weekend Markets
Futures
Top News
German News
Alternative News
Smart News
Yields
WSB
Polymarket
X Watchlist
```

### Docker restart policy

Check:

```bash
cd /var/code/daily-dash-windmill-local

docker compose config | grep -n 'restart:'
```

The relevant services should use:

```text
restart: unless-stopped
```

Check the current stack:

```bash
docker compose ps
```

A reboot test is useful later, but the deployment is already operational while the current Docker
stack remains running.

---

## 23. Routine "is DailyDash alive?" check

Use:

```bash
cd /var/code/daily-dash-windmill-local

docker compose ps
```

Then:

```bash
curl --fail http://127.0.0.1/api/version
echo

curl --fail http://127.0.0.1:18080/health
echo
```

Expected:

```text
CE v1.775.1
{"status":"ok"}
```

This checks the infrastructure itself.

For application-level confidence, also inspect recent Windmill jobs through the UI and confirm recent
Telegram reports/data-repository commits.

---

## 24. Optional reboot validation

A reboot test is recommended as a final infrastructure acceptance test, but it can be postponed.

When ready:

```bash
sudo reboot
```

Reconnect:

```bash
ssh OPERATOR@VPS_HOST
```

Then:

```bash
cd /var/code/daily-dash-windmill-local

docker compose ps

curl --fail http://127.0.0.1/api/version
echo

curl --fail http://127.0.0.1:18080/health
echo
```

Also verify the mounted Git repository:

```bash
docker compose exec -T windmill_worker_dailydash \
  git -C /data/daily-dash-data status --short
```

If that again reports `dubious ownership`, reapply the `safe.directory` configuration.

---

## 25. Backups

There are three distinct backup responsibilities.

### 25.1 DailyDash data artifacts

`/var/code/daily-dash-data` is Git-backed.

Verify regularly:

```bash
git -C /var/code/daily-dash-data fetch origin
git -C /var/code/daily-dash-data status -sb
git -C /var/code/daily-dash-data log -5 --oneline
```

### 25.2 Windmill PostgreSQL

Windmill state lives in PostgreSQL.

Back up the whole PostgreSQL cluster rather than only one database.

For a quiescent backup window:

```bash
BACKUP_DIR=/var/backups/daily-dash
RUNTIME=/var/code/daily-dash-windmill-local
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"

sudo mkdir -p "$BACKUP_DIR"
sudo chown "$USER":"$USER" "$BACKUP_DIR"

cd "$RUNTIME"

docker compose stop \
  windmill_server \
  windmill_worker \
  windmill_worker_native \
  windmill_worker_dailydash

docker compose exec -T db \
  pg_dumpall -U postgres \
  | gzip > "$BACKUP_DIR/windmill-cluster-${STAMP}.sql.gz"

docker compose start \
  windmill_server \
  windmill_worker \
  windmill_worker_native \
  windmill_worker_dailydash
```

Check:

```bash
gzip -t "$BACKUP_DIR/windmill-cluster-${STAMP}.sql.gz"
ls -lh "$BACKUP_DIR/windmill-cluster-${STAMP}.sql.gz"
```

Keep an off-host backup as well.

### 25.3 Runtime configuration and secrets

Back up these encrypted/off-host:

```text
/var/code/daily-dash-windmill-local/.env
/var/code/daily-dash-windmill-local/secrets/
```

Also preserve the operator's Windmill CLI token state securely.

Never commit these files to either repository.

---

## 26. Logs and routine operations

From `/var/code/daily-dash`:

```bash
export DAILY_DASH_WINDMILL_DIR=/var/code/daily-dash-windmill-local

./scripts/local-windmill.sh status
./scripts/local-windmill.sh logs
./scripts/local-windmill.sh rebuild
./scripts/local-windmill.sh down
```

The generated Compose stack uses Docker `json-file` log rotation.

Typical configured values are:

```text
LOG_MAX_SIZE=20m
LOG_MAX_FILE=10
```

Monitor at least:

- disk usage under `/var/lib/docker`;
- disk usage under `/var/code`;
- PostgreSQL backup freshness;
- failed Windmill jobs;
- model-gateway failures;
- model cost anomalies;
- data-repository push failures;
- Telegram delivery failures;
- unexpectedly missing scheduled reports.

---

## 27. Updating DailyDash

Before an update:

```bash
cd /var/code/daily-dash
git status --short
```

Update:

```bash
git fetch origin
git pull --ff-only origin main
npm ci
./scripts/check.sh
```

### Application/config/dependency changes

Rebuild:

```bash
export DAILY_DASH_WINDMILL_DIR=/var/code/daily-dash-windmill-local

./scripts/local-windmill.sh rebuild
```

After rebuild, re-check:

```bash
curl --fail http://127.0.0.1/api/version
echo

curl --fail http://127.0.0.1:18080/health
echo
```

and:

```bash
cd /var/code/daily-dash-windmill-local

docker compose exec -T windmill_worker_dailydash \
  git config --global --get-all safe.directory
```

### Windmill flow/schedule changes

Sync:

```bash
cd /var/code/daily-dash

./scripts/sync-windmill-workspace.sh
```

Do not sync merely because application code changed if no Windmill workspace definitions changed.

### Deployment-template changes

Do not blindly run:

```bash
./scripts/bootstrap-local-windmill.sh --force
```

The generated runtime contains host-specific settings.

Review template changes and preserve/reapply at least:

```text
PostgreSQL password
loopback Caddy mapping 127.0.0.1:80:80
runtime paths
secret files
model gateway binding
data-repo mount
SMTP exposure policy
```

### Windmill/PostgreSQL image changes

Treat these as infrastructure upgrades.

Take a PostgreSQL cluster backup and read upstream upgrade guidance before changing major versions.

---

## 28. Rollback

Application rollback is Git-based:

```bash
cd /var/code/daily-dash
git log --oneline -10
```

Move back to the known-good application revision according to your Git policy, then rebuild:

```bash
export DAILY_DASH_WINDMILL_DIR=/var/code/daily-dash-windmill-local

./scripts/local-windmill.sh rebuild
```

If the failed change included Windmill workspace definitions, synchronize from the known-good checkout:

```bash
./scripts/sync-windmill-workspace.sh
```

Database rollback is separate. Restore a tested PostgreSQL cluster backup into a deliberate recovery
environment rather than treating Git rollback as database recovery.

---

## 29. Security checklist

Before leaving DailyDash unattended:

- [ ] SSH uses key-based authentication.
- [ ] Only intended public ports are exposed.
- [ ] Windmill is private behind `127.0.0.1:80` unless public access was deliberately added.
- [ ] Windmill UI access over SSH uses local port forwarding.
- [ ] PostgreSQL is not published on a host port.
- [ ] DailyDash model gateway remains bound to `127.0.0.1:18080`.
- [ ] Windmill SMTP port 25 is not exposed unless deliberately required.
- [ ] The default PostgreSQL `changeme` password has been replaced.
- [ ] Bootstrap/default Windmill administrator credentials are no longer in use.
- [ ] `/var/code/daily-dash-windmill-local/secrets/` is protected.
- [ ] No application credentials are stored in the public checkout.
- [ ] `daily-dash-data` uses a repository-scoped deploy key with write access only to that repo.
- [ ] Telegram token contains no whitespace.
- [ ] Any accidentally exposed Telegram token has been rotated.
- [ ] Reddit credentials pass the OAuth validation helper.
- [ ] OpenRouter/model-gateway smoke test succeeds.
- [ ] Git `safe.directory` is configured for `/data/daily-dash-data`.
- [ ] All production flow smoke tests succeed.
- [ ] Telegram reports arrive successfully.
- [ ] Data artifacts reach the remote data repository.
- [ ] Schedules are enabled intentionally.
- [ ] PostgreSQL/runtime-secret backup procedures are documented.

---

## 30. Troubleshooting summary from the validated deployment

### Windmill CLI cannot find the workspace profile

Symptom:

```text
No profile found for workspace 'daily-dash-local'
```

Cause:

```text
wmill.yaml: http://localhost
CLI profile: http://127.0.0.1:8080
```

Fix:

```text
bind Windmill to 127.0.0.1:80
recreate daily-dash-local CLI profile with http://localhost
```

### Persistence fails with dubious ownership

Symptom:

```text
fatal: detected dubious ownership in repository at '/data/daily-dash-data'
```

Fix:

```bash
docker compose exec -T windmill_worker_dailydash \
  git config --global --add \
  safe.directory /data/daily-dash-data
```

### Telegram returns 404 and URL contains `%20`

Cause: whitespace in the token.

Fix: rewrite the token with `printf '%s'`, validate it with `/getMe`, rotate if exposed, and rerun
`configure-windmill-workspace.sh`.

### Reddit returns OAuth 401

Cause: Reddit client credentials/application setup, not OpenRouter.

Fix: verify client ID/secret/application configuration and rerun
`configure-wsb-reddit.sh --windmill`.

### Futures fails with missing Python module

Cause: stale custom worker image.

Fix:

```bash
./scripts/local-windmill.sh rebuild
```

### Host data repo says `ahead N` after successful persistence

Cause: host checkout's `origin/main` remote-tracking reference has not fetched the worker's pushed
commits yet.

Fix:

```bash
git -C /var/code/daily-dash-data fetch origin
```

Then compare `HEAD` with `origin/main`.

---

## 31. Final expected state

The validated private deployment looks like:

```text
Workstation
    |
    | SSH
    | -L 19080:127.0.0.1:80
    v
VPS
    |
    +--> 127.0.0.1:80
    |       |
    |       v
    |   Windmill bundled Caddy
    |       |
    |       +--> Windmill server
    |       +--> Windmill workers
    |       +--> PostgreSQL (Docker-internal)
    |
    +--> 127.0.0.1:18080
    |       |
    |       v
    |   DailyDash model gateway
    |       |
    |       +--> OpenRouter
    |
    +--> DailyDash dedicated worker
            |
            +--> external data/retrieval sources
            |
            +--> /data/daily-dash-data
            |       |
            |       +--> Git commit
            |       +--> private Git remote
            |
            +--> Telegram

Windmill workspace: daily-dash-workspace
CLI profile:        daily-dash-local
CLI base URL:       http://localhost

Production invariant:

run
→ persist_data
→ deliver
```

The public Git repository remains the source of truth for:

- application code;
- prompts;
- configuration;
- tests;
- flows;
- schedules;
- deployment templates;
- documentation.

Private installation state remains outside the public repository:

- `/var/code/daily-dash-windmill-local`;
- `.env`;
- secret files;
- data-repository deploy key;
- Windmill database;
- Windmill CLI token;
- generated report artifacts.

---

## Related documentation

- [`../QUICKSTART.md`](../QUICKSTART.md) — shortest clean-machine setup path
- [`09_LOCAL_WINDMILL_BOOTSTRAP.md`](09_LOCAL_WINDMILL_BOOTSTRAP.md) — generated runtime mechanics
- [`15_DEPLOYMENT_CHECKLIST.md`](15_DEPLOYMENT_CHECKLIST.md) — deployment acceptance checklist
- [`05_WINDMILL_ORCHESTRATION.md`](05_WINDMILL_ORCHESTRATION.md) — Windmill architecture
- [`07_GIT_DATA_PERSISTENCE.md`](07_GIT_DATA_PERSISTENCE.md) — private artifact Git persistence
- [`SCHEDULING.md`](SCHEDULING.md) — schedules and retrieval windows
- Windmill self-hosting: <https://www.windmill.dev/docs/advanced/self_host>
- Windmill PostgreSQL migration guidance:
  <https://www.windmill.dev/docs/advanced/self_host/postgres_18_upgrade>
