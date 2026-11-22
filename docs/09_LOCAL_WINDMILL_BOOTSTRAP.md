# Local Windmill bootstrap

`deploy/local-windmill` contains reproducible application-stack templates.
`scripts/bootstrap-local-windmill.sh` materializes them outside the checkout,
creates private empty application secret files and preserves existing environment
and secrets unless explicitly told to rewrite them. `--force` refreshes templates.

```sh
./scripts/bootstrap-local-windmill.sh --target /absolute/private/runtime \
  --data-repo /absolute/private/data --gateway-token-file /absolute/private/client.token
```

Configure a real database password and the owned internal gateway network before
starting. Provider keys are not application credentials. The worker uses
`DAILY_DASH_GATEWAY_URL` and `DAILY_DASH_GATEWAY_TOKEN_FILE`. Token source mounts
and `DAILY_DASH_GATEWAY_NETWORK` are explicit runtime environment values.

Operate the application with `DAILY_DASH_WINDMILL_DIR` and
`scripts/local-windmill.sh`. Provision the reusable gateway independently from its
reviewed release, preserving its project configuration and ledger. See
[LLM integration](LLM_GATEWAY.md) and [deployment](VPS_DEPLOYMENT.md).
