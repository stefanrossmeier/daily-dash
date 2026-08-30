# VPS deployment

This runbook takes a fresh Linux VPS from an empty host to a running DailyDash installation with
self-hosted Windmill, persistent artifacts, scheduled reports, and Telegram delivery.

It is written for a **single-operator VPS** using Docker Compose. Windmill itself documents Docker
Compose as a practical option for small/self-hosted installations; larger or highly available
installations should use a more production-oriented platform such as Kubernetes and an external
PostgreSQL service.

DailyDash keeps its source checkout, private data checkout, and generated runtime definition together under one operator-owned root:

```text
/var/code/
├── daily-dash/                  # public Git checkout
├── daily-dash-data/             # private Git checkout used as the artifact sink
└── daily-dash-windmill-local/   # generated runtime state; NOT a Git checkout
    ├── .env                     # Compose/runtime paths and infrastructure settings
    ├── docker-compose.yml
    ├── docker-compose.override.yml
    ├── Caddyfile
    └── secrets/                 # one-value local secret files
```

`daily-dash-windmill-local` is intentionally generated from the deployment templates committed in
`daily-dash/deploy/local-windmill/`. It is private machine state, not a third repository. Docker-managed
volumes (including the Windmill PostgreSQL volume) still live in Docker's storage area, normally under
`/var/lib/docker`; host firewall/TLS configuration likewise remains host infrastructure rather than
application checkout content.

> [!IMPORTANT]
> This guide deliberately uses explicit `/var/code/...` paths. Do not rely on the bootstrap
> script's sibling-directory defaults on a production host.

## 1. Before you start

You need:

- a VPS running a currently supported Ubuntu or Debian release;
- SSH access with a sudo-capable operator account;
- a DNS name such as `dash.example.com` pointing to the VPS;
- a GitHub account with access to a private `daily-dash-data` repository;
- an OpenRouter API key;
- a Telegram bot token and target chat/channel ID;
- Reddit API credentials if the WSB report is enabled.

The current application/tooling requirements are:

- Git;
- Docker Engine and the Docker Compose plugin;
- `uv` matching the range declared in `pyproject.toml`;
- Node.js **>20** and npm, used only for the pinned Windmill CLI;
- curl.

Use the official installation instructions for your distribution:

- Docker Engine: <https://docs.docker.com/engine/install/>
- Docker Compose plugin: <https://docs.docker.com/compose/install/linux/>
- uv: <https://docs.astral.sh/uv/getting-started/installation/>
- Node.js: <https://nodejs.org/en/download>

After installation, verify:

```bash
git --version
uv --version
node --version
npm --version
docker --version
docker compose version
curl --version
```

The operator user must be able to run Docker. If you add the user to the `docker` group, remember
that membership is effectively root-equivalent access to the host.

## 2. Basic host preparation

This guide assumes the application is operated by the current non-root SSH user. Create the common
root and make it operator-owned:

```bash
sudo mkdir -p /var/code
sudo chown "$USER":"$USER" /var/code
chmod 755 /var/code
```

Keep SSH key authentication working before changing firewall or SSH settings. At minimum, allow
only the ports the final deployment needs:

```text
SSH       your configured SSH port
HTTP      80/tcp   (certificate issuance / redirect)
HTTPS     443/tcp
```

Do **not** expose PostgreSQL, the DailyDash model gateway, or Windmill worker ports publicly.

A typical UFW baseline, when SSH really uses the standard `OpenSSH` profile, is:

```bash
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow OpenSSH
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
sudo ufw status verbose
```

If SSH uses a custom port, allow that port before enabling the firewall.

## 3. Clone DailyDash

Clone the public application repository:

```bash
git clone https://github.com/stefanrossmeier/daily-dash.git /var/code/daily-dash
cd /var/code/daily-dash
```

Install the pinned Windmill CLI and run the repository checks:

```bash
npm ci
./scripts/check-tools.sh
./scripts/check.sh
```

Do not continue with a production deployment if the repository quality gate is red.

## 4. Prepare the private data repository

DailyDash persists immutable JSON artifacts to a separate Git repository before Telegram delivery.
The repository should be private and dedicated to generated DailyDash data.

Create `daily-dash-data` in your Git provider first with a `main` branch (an initial README commit is
enough), then clone it to the canonical VPS path using whatever operator-level Git authentication you
normally use:

```bash
git clone git@github.com:YOUR_ACCOUNT/daily-dash-data.git \
  /var/code/daily-dash-data
```

Verify:

```bash
git -C /var/code/daily-dash-data status -sb
git -C /var/code/daily-dash-data remote -v
```

The branch used by DailyDash defaults to `main`.

The **runtime persistence deploy key configured later is separate from the operator credentials used
to perform this initial clone**.

## 5. Materialize the private Windmill runtime

From `/var/code/daily-dash`:

```bash
./scripts/bootstrap-local-windmill.sh \
  --target /var/code/daily-dash-windmill-local \
  --data-repo /var/code/daily-dash-data
```

Set the explicit runtime path for the rest of the session:

```bash
export DAILY_DASH_WINDMILL_DIR=/var/code/daily-dash-windmill-local
```

Inspect the generated runtime settings:

```bash
cat /var/code/daily-dash-windmill-local/.env
```

The important paths must be exactly:

```text
DAILY_DASH_SOURCE=/var/code/daily-dash
DAILY_DASH_DATA_SOURCE=/var/code/daily-dash-data
DAILY_DASH_OPENROUTER_KEY_FILE=/var/code/daily-dash-windmill-local/secrets/openrouter_api_key
```

`daily-dash-windmill-local/.env` is Docker Compose runtime configuration. Application credentials
belong in `daily-dash-windmill-local/secrets/`, not in the public checkout.

## 6. Populate the canonical secrets directory

The generated directory should contain:

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

The directory should be mode `0700` and secret files mode `0600`:

```bash
chmod 700 /var/code/daily-dash-windmill-local/secrets
chmod 600 /var/code/daily-dash-windmill-local/secrets/*
```

### OpenRouter

Write the OpenRouter key as one raw value with no shell assignment or quotes. For example, use an
interactive prompt so the value does not appear in the command itself:

```bash
read -r -s -p 'OpenRouter API key: ' SECRET_VALUE; echo
printf '%s' "$SECRET_VALUE" > \
  /var/code/daily-dash-windmill-local/secrets/openrouter_api_key
unset SECRET_VALUE
```

### Telegram

```bash
read -r -s -p 'Telegram bot token: ' SECRET_VALUE; echo
printf '%s' "$SECRET_VALUE" > \
  /var/code/daily-dash-windmill-local/secrets/telegram_token
unset SECRET_VALUE

read -r -p 'Telegram chat/channel ID: ' SECRET_VALUE
printf '%s' "$SECRET_VALUE" > \
  /var/code/daily-dash-windmill-local/secrets/telegram_chat_id
unset SECRET_VALUE
```

### Data-repository deploy key

The Windmill persistence job uses its own SSH deploy key and does not rely on the operator's SSH
agent. The bootstrap creates an empty placeholder, so replace it before generating the key:

```bash
rm -f \
  /var/code/daily-dash-windmill-local/secrets/data_repo_deploy_key \
  /var/code/daily-dash-windmill-local/secrets/data_repo_deploy_key.pub

ssh-keygen -t ed25519 \
  -C 'daily-dash-data@vps' \
  -N '' \
  -f /var/code/daily-dash-windmill-local/secrets/data_repo_deploy_key

chmod 600 /var/code/daily-dash-windmill-local/secrets/data_repo_deploy_key
```

Add the `.pub` key to the **private `daily-dash-data` repository** as a deploy key with write
access. Keep the private key only on the VPS.

Test the key before continuing:

```bash
GIT_SSH_COMMAND='ssh -i /var/code/daily-dash-windmill-local/secrets/data_repo_deploy_key -o IdentitiesOnly=yes' \
  git ls-remote git@github.com:YOUR_ACCOUNT/daily-dash-data.git HEAD
```

## 7. Harden the generated runtime before first public start

The checked-in Compose files are intentionally local-first. The generated runtime must be hardened
for an Internet-connected VPS.

### 7.1 Replace the default PostgreSQL password

The generated template initially uses `changeme` for the internal PostgreSQL credential. Replace it
**before the first production start**. Because the current Compose template passes Windmill a full
`DATABASE_URL`, the infrastructure database credential is stored in the private runtime `.env`.
Application secrets remain in `secrets/`.

Generate a URL-safe random value and update both sides consistently:

```bash
RUNTIME=/var/code/daily-dash-windmill-local
DB_PASSWORD="$(openssl rand -hex 32)"

sed -i "s#postgres:changeme@db#postgres:${DB_PASSWORD}@db#" "$RUNTIME/.env"
sed -i "s#POSTGRES_PASSWORD: changeme#POSTGRES_PASSWORD: ${DB_PASSWORD}#" \
  "$RUNTIME/docker-compose.yml"

unset DB_PASSWORD
chmod 600 "$RUNTIME/.env"
```

Verify without printing the password:

```bash
grep -q 'changeme' "$RUNTIME/.env" && echo 'ERROR: default DB password remains' || echo 'DB URL hardened'
grep -q 'POSTGRES_PASSWORD: changeme' "$RUNTIME/docker-compose.yml" \
  && echo 'ERROR: default DB password remains in Compose' \
  || echo 'Compose DB password hardened'
```

> [!WARNING]
> `bootstrap-local-windmill.sh --force` refreshes generated infrastructure files. If you later use
> it on this VPS, review/reapply the VPS-specific database/network hardening before recreating the
> stack.

### 7.2 Do not publish Windmill SMTP

DailyDash does not need Windmill's SMTP listener. In the generated
`docker-compose.yml`, remove or comment the host mapping:

```yaml
- 25:25
```

The internal Windmill listener can remain unexposed.

### 7.3 Put the bundled Windmill proxy on loopback

For a public VPS, keep the generated Windmill/Caddy stack behind a host-level HTTPS reverse proxy.
Change the generated Caddy mapping from:

```yaml
- 80:80
```

to:

```yaml
- 127.0.0.1:8080:80
```

Keep its existing `BASE_URL=":80"`. The internal stack then remains accessible only from the VPS
at `http://127.0.0.1:8080`.

After editing, confirm the rendered Compose configuration:

```bash
cd /var/code/daily-dash-windmill-local
docker compose config >/dev/null
```

## 8. Configure public HTTPS

Use a host-level reverse proxy for TLS. Caddy is a convenient option because it can obtain and
renew Let's Encrypt certificates automatically, but nginx, Traefik, or your provider's reverse
proxy are also valid.

Install Caddy using its official package instructions:

<https://caddyserver.com/docs/install>

Assume:

```bash
export DAILY_DASH_DOMAIN=dash.example.com
```

Ensure the DNS A/AAAA record already resolves to the VPS. Then configure host Caddy, for example in
`/etc/caddy/Caddyfile`:

```caddyfile
http://localhost {
    reverse_proxy 127.0.0.1:8080
}

dash.example.com {
    reverse_proxy 127.0.0.1:8080
}
```

Replace `dash.example.com` with the real hostname, validate, and reload:

```bash
sudo caddy validate --config /etc/caddy/Caddyfile
sudo systemctl reload caddy
sudo systemctl status caddy --no-pager
```

The `http://localhost` block intentionally keeps DailyDash's existing local CLI and health checks
working on the VPS, while the public hostname receives HTTPS.

## 9. Start the Windmill/DailyDash stack

From the public checkout:

```bash
cd /var/code/daily-dash
export DAILY_DASH_WINDMILL_DIR=/var/code/daily-dash-windmill-local

./scripts/local-windmill.sh up
./scripts/local-windmill.sh status
```

Because the internal proxy now listens on loopback port `8080`, verify it directly:

```bash
curl --fail --silent --show-error http://127.0.0.1:8080/ >/dev/null
echo 'internal Windmill proxy: ok'
```

Verify the DailyDash model gateway, which is intentionally loopback-only:

```bash
curl --fail --silent --show-error http://127.0.0.1:18080/health
echo
```

Then verify the public HTTPS endpoint:

```bash
curl --fail --silent --show-error "https://${DAILY_DASH_DOMAIN}/" >/dev/null
echo 'public Windmill HTTPS: ok'
```

Useful logs:

```bash
./scripts/local-windmill.sh logs
```

## 10. Complete the initial Windmill bootstrap

Open:

```text
https://dash.example.com
```

On a fresh instance:

1. complete the initial administrator setup;
2. replace any bootstrap/default administrator credentials immediately;
3. create a dedicated workspace with ID `daily-dash-workspace`;
4. create a Windmill API token for the operator/CLI and store it only in the operator's Windmill
   CLI configuration.

Windmill tokens can be created from Account settings. Treat the token like a password and do not
commit it.

The repository's CLI profile is intentionally local to the VPS:

```text
profile:      daily-dash-local
workspace id: daily-dash-workspace
base URL:     http://localhost
```

The host Caddy `http://localhost` route forwards that local API traffic to the internal stack, while
human access uses the public HTTPS hostname.

Register the workspace from `/var/code/daily-dash`:

```bash
./scripts/wmill.sh workspace add \
  daily-dash-local \
  daily-dash-workspace \
  http://localhost
```

Follow the pinned CLI's authentication prompt/token flow, then verify:

```bash
./scripts/wmill.sh workspace whoami
./scripts/wmill.sh workspace list
```

## 11. Configure DailyDash variables and Windmill secrets

Base persistence and Telegram configuration use the one-value files already stored in the canonical
runtime secrets directory.

Set the installation-specific data remote:

```bash
export DAILY_DASH_DATA_REPO_REMOTE_URL='git@github.com:YOUR_ACCOUNT/daily-dash-data.git'
export DAILY_DASH_DATA_REPO_BRANCH='main'
export DAILY_DASH_WINDMILL_DIR=/var/code/daily-dash-windmill-local
```

Provision the base values into Windmill:

```bash
cd /var/code/daily-dash
./scripts/configure-windmill-workspace.sh
```

This creates/updates:

```text
f/daily_dash/data_repo_remote_url     variable
f/daily_dash/data_repo_branch         variable
f/daily_dash/data_repo_deploy_key     secret
f/daily_dash/telegram_token           secret
f/daily_dash/telegram_chat_id         secret
```

### WSB / Reddit

If WSB is enabled, configure its approved Reddit API credentials interactively and upload them:

```bash
DAILY_DASH_WINDMILL_DIR=/var/code/daily-dash-windmill-local \
  ./scripts/configure-wsb-reddit.sh --windmill
```

This stores the local inputs under the same `secrets/` directory and creates the corresponding
Windmill values.

No additional TradingView credential is required for the Futures report; its current adapter uses
anonymous TradingView/tvDatafeed access.

## 12. Synchronize flows and schedules

The public repository is the source of truth for Windmill workspace definitions. Push them only
after the workspace and secrets/variables are configured:

```bash
cd /var/code/daily-dash
./scripts/sync-windmill-workspace.sh
```

The sync helper regenerates derived News flows/schedules, runs the Windmill contract tests, and
pushes the checked-in `f/**` definitions. Secrets, variables, resources, users, groups, and instance
settings are deliberately excluded from Git synchronization.

Verify that the workspace contains the DailyDash flows and enabled schedules.

## 13. Validate the complete installation

### 13.1 Repository and infrastructure

```bash
cd /var/code/daily-dash
./scripts/check.sh
./scripts/smoke-model-gateway.sh rank-cheap
```

Confirm Docker state:

```bash
cd /var/code/daily-dash-windmill-local
docker compose ps
```

The expected critical components are:

```text
PostgreSQL
Windmill server
Windmill workers
windmill_worker_dailydash
DailyDash model gateway
internal Caddy proxy
```

### 13.2 Verify mounts and secret boundaries

Check that the DailyDash worker uses the correct data checkout:

```bash
WORKER_ID="$(docker ps -q --filter label=com.docker.compose.service=windmill_worker_dailydash | head -n1)"

docker inspect "$WORKER_ID" \
  --format '{{range .Mounts}}{{println .Source "->" .Destination}}{{end}}'
```

You should see:

```text
/var/code/daily-dash-data -> /data/daily-dash-data
```

Verify the OpenRouter file is present inside the gateway without printing it:

```bash
cd /var/code/daily-dash-windmill-local

docker compose exec -T daily_dash_model_gateway sh -lc '
  test -s "$OPENROUTER_API_KEY_FILE" && echo "OpenRouter key: present" || exit 1
'
```

### 13.3 Run end-to-end flows

From `/var/code/daily-dash/workflows/windmill`:

```bash
../../scripts/wmill.sh flow run f/daily_dash/news_top
../../scripts/wmill.sh flow run f/daily_dash/markets
../../scripts/wmill.sh flow run f/daily_dash/futures
../../scripts/wmill.sh flow run f/daily_dash/yields
../../scripts/wmill.sh flow run f/daily_dash/wsb
../../scripts/wmill.sh flow run f/daily_dash/polymarket
../../scripts/wmill.sh flow run f/daily_dash/x_watchlist
```

Smart News and the other News profiles can then be smoke-tested as needed:

```bash
../../scripts/wmill.sh flow run f/daily_dash/news_german
../../scripts/wmill.sh flow run f/daily_dash/news_alternative
../../scripts/wmill.sh flow run f/daily_dash/news_smart
../../scripts/wmill.sh flow run f/daily_dash/markets_weekend
```

For each production-style flow verify:

```text
run
→ persist_data_repo (or equivalent persistence step)
→ deliver
```

and confirm:

1. the flow succeeds;
2. a new immutable artifact appears in `/var/code/daily-dash-data`;
3. the data repository commit reaches its private remote;
4. Telegram delivery succeeds;
5. user-facing messages do not contain internal ranking/debug information.

## 14. Verify schedules before leaving the host unattended

All production schedules are versioned under `workflows/windmill/f/daily_dash/` and use
`Europe/Berlin` where configured. After sync, inspect the schedules in the Windmill UI and verify
that the expected ones are enabled.

The repository is authoritative for cadence; see [`SCHEDULING.md`](SCHEDULING.md).

Because scheduled reports can incur model cost, leave schedules disabled until the relevant manual
flow smoke tests are green if you are doing a staged rollout.

## 15. Reboot test

A deployment is not complete until it survives a host reboot.

```bash
sudo reboot
```

After reconnecting:

```bash
cd /var/code/daily-dash
export DAILY_DASH_WINDMILL_DIR=/var/code/daily-dash-windmill-local

./scripts/local-windmill.sh status
curl --fail --silent --show-error http://127.0.0.1:18080/health
echo
curl --fail --silent --show-error "https://${DAILY_DASH_DOMAIN}/" >/dev/null
```

The Compose services use `restart: unless-stopped`; the host Caddy service should also be enabled at
boot by its package installation.

## 16. Backups

There are three distinct backup responsibilities.

### 16.1 DailyDash data artifacts

`/var/code/daily-dash-data` is already Git-backed. Verify regularly that the working tree is clean
outside active jobs and that commits reach the private remote:

```bash
git -C /var/code/daily-dash-data status -sb
git -C /var/code/daily-dash-data log -1 --oneline
```

### 16.2 Windmill PostgreSQL

Windmill state lives in PostgreSQL. Back up the **whole PostgreSQL cluster**, not only the `windmill`
database. Windmill can create additional databases/roles, so `pg_dumpall` is the safer cluster-level
backup.

For a quiescent backup window:

```bash
BACKUP_DIR=/var/backups/daily-dash
RUNTIME=/var/code/daily-dash-windmill-local
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"

sudo mkdir -p "$BACKUP_DIR"
sudo chown "$USER":"$USER" "$BACKUP_DIR"

cd "$RUNTIME"
docker compose stop windmill_server windmill_worker windmill_worker_native windmill_worker_dailydash

docker compose exec -T db pg_dumpall -U postgres \
  | gzip > "$BACKUP_DIR/windmill-cluster-${STAMP}.sql.gz"

docker compose start windmill_server windmill_worker windmill_worker_native windmill_worker_dailydash
```

Confirm the backup is non-empty:

```bash
gzip -t "$BACKUP_DIR/windmill-cluster-${STAMP}.sql.gz"
ls -lh "$BACKUP_DIR/windmill-cluster-${STAMP}.sql.gz"
```

Store backups off-host as well. A backup that exists only on the VPS does not protect against VPS
loss.

Restore cluster dumps into a fresh/empty PostgreSQL cluster rather than blindly replaying them over
a live populated Windmill database. PostgreSQL major-version changes need a deliberate dump/restore
procedure; do not simply change the Postgres image tag.

### 16.3 Runtime configuration and secrets

Back up these **encrypted/off-host**, not in Git:

```text
/var/code/daily-dash-windmill-local/.env
/var/code/daily-dash-windmill-local/secrets/
```

Also preserve whatever secure operator state contains the Windmill CLI API token. Never commit
these files to either repository.

## 17. Logs and routine operations

Useful application/runtime commands from `/var/code/daily-dash`:

```bash
export DAILY_DASH_WINDMILL_DIR=/var/code/daily-dash-windmill-local

./scripts/local-windmill.sh status
./scripts/local-windmill.sh logs
./scripts/local-windmill.sh rebuild
./scripts/local-windmill.sh down
```

The generated Compose stack uses Docker `json-file` log rotation. The defaults are controlled by:

```text
LOG_MAX_SIZE=20m
LOG_MAX_FILE=10
```

You may override them in the private runtime `.env`.

Monitor at least:

- disk usage under `/var/lib/docker`, `/var/code`, and your backup destination;
- PostgreSQL backup freshness;
- failed Windmill jobs;
- model-gateway failures/cost anomalies;
- data-repository push failures;
- Telegram delivery failures.

## 18. Updating DailyDash

Before an update, make sure the working checkout is clean and take a Windmill database backup when
the change affects deployment/runtime state.

Update the application checkout:

```bash
cd /var/code/daily-dash
git status --short
git fetch origin
git pull --ff-only origin main
npm ci
./scripts/check.sh
```

Then determine what changed:

### Application/config/dependency changes

Rebuild the DailyDash worker/model gateway:

```bash
export DAILY_DASH_WINDMILL_DIR=/var/code/daily-dash-windmill-local
./scripts/local-windmill.sh rebuild
```

### Windmill workspace/flow/schedule changes

Synchronize the workspace:

```bash
./scripts/sync-windmill-workspace.sh
```

### Deployment-template changes

Do **not** blindly run bootstrap `--force` on the VPS. The generated runtime contains VPS-specific
network/database hardening. Review the template diff first. If you intentionally refresh generated
files, use explicit paths and then reapply/review every VPS hardening step in section 7 before
recreating containers.

### Windmill/PostgreSQL image changes

Treat Windmill and PostgreSQL upgrades as infrastructure changes, not ordinary application updates.
Read the upstream Windmill self-hosting release/upgrade guidance first and take a complete database
backup. Never cross a PostgreSQL major version by changing only the image tag.

## 19. Rollback

Application rollback is Git-based:

```bash
cd /var/code/daily-dash
git log --oneline -10
```

Check out or reset to the known-good commit according to your Git operating policy, then rebuild the
application containers:

```bash
export DAILY_DASH_WINDMILL_DIR=/var/code/daily-dash-windmill-local
./scripts/local-windmill.sh rebuild
```

If the failed change included Windmill workspace definitions, sync the workspace from the known-good
checkout as well.

Database rollback is different: restore a tested PostgreSQL cluster backup into a fresh/empty
cluster. Do not use Git rollback as a substitute for Windmill database recovery.

## 20. Security checklist before enabling schedules

Before leaving DailyDash running unattended, verify:

- [ ] SSH uses key-based authentication and the firewall exposes only intended ports.
- [ ] Public Windmill access uses HTTPS.
- [ ] PostgreSQL is not published on a host port.
- [ ] The DailyDash model gateway remains bound to `127.0.0.1:18080` only.
- [ ] Windmill SMTP port 25 is not published unless you explicitly need and secure it.
- [ ] The default PostgreSQL `changeme` password has been replaced.
- [ ] Bootstrap/default Windmill administrator credentials are no longer in use.
- [ ] `/var/code/daily-dash-windmill-local/secrets/` is mode `0700`; secret files are `0600`.
- [ ] No application credentials are stored in the public `daily-dash` checkout.
- [ ] `daily-dash-data` is private and its deploy key is scoped only to that repository.
- [ ] Manual smoke tests succeed before paid schedules are enabled.
- [ ] PostgreSQL and runtime-secret backups exist off-host and have a documented restore path.

## 21. Final expected state

A complete single-VPS installation looks like:

```text
Internet
   |
   | HTTPS :443
   v
host Caddy
   |
   | 127.0.0.1:8080
   v
Windmill bundled proxy
   |
   +--> Windmill server
   |
   +--> PostgreSQL (internal only)
   |
   +--> Windmill workers
           |
           +--> DailyDash dedicated worker
           |       |
           |       +--> /var/code/daily-dash-data
           |
           +--> DailyDash model gateway
                   |
                   +--> /var/code/daily-dash-windmill-local/secrets/openrouter_api_key

DailyDash workspace
   |
   +--> versioned flows + schedules
   +--> Windmill secrets/variables
   +--> run -> persist -> deliver
```

The public Git repository remains the source of truth for application code, prompts, configuration,
flows, schedules, tests, and deployment templates. The generated runtime, credentials, Windmill
database, CLI token, and generated report artifacts remain private installation state.

## Related documentation

- [`../QUICKSTART.md`](../QUICKSTART.md) — shortest clean-machine setup path
- [`09_LOCAL_WINDMILL_BOOTSTRAP.md`](09_LOCAL_WINDMILL_BOOTSTRAP.md) — generated runtime mechanics
- [`15_DEPLOYMENT_CHECKLIST.md`](15_DEPLOYMENT_CHECKLIST.md) — deployment acceptance checklist
- [`05_WINDMILL_ORCHESTRATION.md`](05_WINDMILL_ORCHESTRATION.md) — Windmill architecture
- [`07_GIT_DATA_PERSISTENCE.md`](07_GIT_DATA_PERSISTENCE.md) — private artifact Git persistence
- [`SCHEDULING.md`](SCHEDULING.md) — schedules and retrieval windows
- Windmill self-hosting: <https://www.windmill.dev/docs/advanced/self_host>
- Windmill PostgreSQL 18 migration: <https://www.windmill.dev/docs/advanced/self_host/postgres_18_upgrade>
