# Application stack template

Materialize this template using `scripts/bootstrap-local-windmill.sh`. Keep the
resulting runtime environment and credentials outside Git. Set the private
`DAILY_DASH_GATEWAY_TOKEN_SOURCE` and owned `DAILY_DASH_GATEWAY_NETWORK`.
The application worker joins the gateway's internal client network; it never
mounts a provider key. The copied provider container is retired.

Use the main repository's current LLM integration and deployment guides. These
files are generic templates and do not record any particular installation.
