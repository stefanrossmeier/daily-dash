# LLM gateway integration

All inference uses the reusable authenticated LLM gateway: chat/ranking,
consolidation and native X retrieval. The copied provider service is removed.
Provider keys are mounted only into the gateway, never application workers.

Configure `DAILY_DASH_GATEWAY_URL` and `DAILY_DASH_GATEWAY_TOKEN_FILE` (or the
explicit token environment variable). CLI clients default to loopback port 18181.
There is no silent legacy URL fallback. The application deployment requires an
explicit private `DAILY_DASH_GATEWAY_TOKEN_SOURCE` mount.

Scheduled jobs derive their logical run ID from durable Windmill job metadata.
Manual/evaluation calls require `DAILY_DASH_RUN_ID`: choose a new ID for new work,
and reuse the same ID when recovering an interrupted run. Invocation identity
includes the canonical body and run ID, so process restart does not buy the same
logical request again. After transport loss the client queries the original result.
Enable sufficient result retention at the gateway to recover response content.

Nullable usage/cost propagates as unknown through traces and summaries. The
canonical consumed-cost source is authenticated gateway `GET /v1/usage`, with
`group_by=day`, `alias`, `run_id`, provider/model dimensions and `since`/`until`
windows. Measured cost, estimated cost and unresolved exposure remain separate.

Native X uses per-fetched-post/profile pricing and an explicitly accepted request
risk allowance. This allowance is not an enforced upstream spending cap. Unknown
outcomes retain exposure; measured overruns stop project admission for review.
No alternate direct-provider route is used on failure.

Use the gateway release's parameterized deployment template and exact reviewed
image identity. Preserve private configuration, state, receipts and backups across
upgrades. Public documentation does not list particular installations.
