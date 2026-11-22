# Self-hosted deployment

This is a generic installation guide, not an inventory of any live host.
DailyDash runs a Windmill/database/application stack and connects to its owned,
authenticated reusable LLM gateway. Provider credentials belong at that gateway.

1. Choose private persistent source, runtime, secret and application-data paths.
2. Provision a reviewed gateway release using its parameterized deployment template,
   project-owned aliases/pricing/budgets, private tokens and persistent state.
3. Materialize the application stack with `scripts/bootstrap-local-windmill.sh`
   using `--target`, `--data-repo` and `--gateway-token-file` as appropriate.
4. Set `DAILY_DASH_GATEWAY_NETWORK` in the private runtime environment to the
   gateway's owned internal client network. The worker joins that network in
   addition to its application network; the gateway itself has no direct outbound
   network, only its allowlisted egress proxy.
5. Set real database/operator credentials before exposing administration. Keep
   Windmill administration private or protect it with an appropriate HTTPS boundary.
6. Build/start the application using `scripts/local-windmill.sh`; synchronize owned
   workflow definitions without changing unrelated projects or schedule enablement.
7. Verify authenticated gateway readiness and accounting continuity without running
   a paid model call or sending a Telegram message merely for liveness.

See [LLM integration](LLM_GATEWAY.md) for current variables, durable IDs, nullable
usage, X risk allowances and cost reporting. Copied provider services are retired.

Back up application data, the Windmill database, private runtime secrets and gateway
accounting independently. Preserve unresolved billing exposure and delivery state.
Never run `down -v` or replace a ledger to clear a cap. Upgrade with reviewed image
identities and keep a tested rollback image/checkpoint. Gateway documentation
provides the exact artifact/security/state recovery procedure.
