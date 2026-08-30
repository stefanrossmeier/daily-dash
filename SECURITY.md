# Security Policy

DailyDash is a self-hosted, primarily single-operator project that handles API credentials,
Telegram delivery credentials, private generated report artifacts, and model-provider access.
Security reports are welcome.

## Supported version

Security fixes target the current `main` branch. Historical commits, old prompt versions, and
archived deployment states are retained for traceability but are not independently supported
releases.

## Reporting a vulnerability

Please **do not open a public GitHub issue** for a vulnerability that could expose credentials,
private report data, arbitrary code execution, unauthorized remote writes, or another user's
private deployment details.

Prefer GitHub's private vulnerability-reporting / Security Advisory mechanism for this repository
when available. If private reporting is not available, contact the repository owner through the
GitHub profile and disclose only enough information to establish a private channel; do not paste
secrets or exploit details into a public discussion.

A useful report includes:

- affected commit/version;
- affected component or workflow;
- impact;
- reproduction steps using non-sensitive test values where possible;
- suggested mitigation, if known.

Never send real API keys, Telegram tokens, deploy keys, or private generated artifacts as part of a
report.

## Security boundaries

The intended deployment model keeps secrets and private runtime state outside the public source
repository:

```text
daily-dash/                  public source/config/workflows
daily-dash-windmill-local/   private runtime + local secret files
daily-dash-data/             private generated artifacts
```

Important boundaries include:

- the root OpenRouter API key is mounted only into the model gateway;
- model-backed application code accesses providers through model aliases/gateway contracts;
- Telegram/data-repository/Reddit credentials are provisioned as scoped Windmill secrets;
- generated artifacts are persisted outside the public source checkout;
- production workflows persist before external delivery;
- secrets must not be embedded in configuration, workflow source, Docker images, logs, prompt
  traces, or report artifacts.

See [`docs/09_LOCAL_WINDMILL_BOOTSTRAP.md`](docs/09_LOCAL_WINDMILL_BOOTSTRAP.md) and
[`docs/16_ARCHITECTURE_BOUNDARIES.md`](docs/16_ARCHITECTURE_BOUNDARIES.md).

## Operator responsibilities

Self-hosting means the operator is responsible for:

- keeping Docker, Windmill, Python dependencies, and host packages patched;
- restricting access to the Windmill UI and host filesystem;
- protecting the local `secrets/` directory and private data repository;
- using repository-scoped deploy keys rather than broad personal credentials where possible;
- reviewing third-party source/API terms and changes;
- rotating credentials after suspected exposure;
- reviewing logs/artifacts before sharing them publicly.

## Dependency and source risk

DailyDash consumes third-party RSS/API/WebSocket sources. Upstream behavior can change without
notice. Treat external content as untrusted input and preserve structured validation/failure
handling at adapter/model boundaries.

The anonymous TradingView/tvDatafeed integration depends on an unofficial protocol and should be
considered operationally fragile rather than a trusted security boundary.

## Scope notes

General market-data inaccuracies, source downtime, LLM ranking disagreements, or editorial choices
are not security vulnerabilities unless they arise from an exploitable integrity/authentication
failure.
