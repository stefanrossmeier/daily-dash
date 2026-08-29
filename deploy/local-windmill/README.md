# Local Windmill deployment source

These files are the checked-in source for the local DailyDash Windmill stack.
Do not maintain a separate hand-edited copy as the source of truth.

Materialize a machine-specific deployment directory with:

```bash
./scripts/bootstrap-local-windmill.sh
```

The bootstrap script copies these files and writes a local `.env` containing only
Compose/runtime paths. Application credentials are stored as one-value files under
the generated `secrets/` directory. Neither `.env` nor `secrets/` is intended for Git.
