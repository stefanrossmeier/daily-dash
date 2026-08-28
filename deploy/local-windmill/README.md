# Local Windmill deployment source

These files are the checked-in source for the local DailyDash Windmill stack.
Do not maintain a separate hand-edited copy as the source of truth.

Materialize a machine-specific deployment directory with:

```bash
./scripts/bootstrap-local-windmill.sh
```

The bootstrap script copies these files and writes a local `.env` containing
absolute checkout/key paths. The generated `.env` and `secrets/` directory are
never intended for Git.
