## Summary

<!-- What changed and why? -->

## Architecture / behavior

<!-- Which layers, sources, prompts/policies, persisted contracts, or user-facing reports changed? -->

## Validation

- [ ] `./scripts/check.sh`
- [ ] `git diff --check`
- [ ] focused tests added/updated
- [ ] Windmill contract/schedule checks run when applicable
- [ ] real-source/flow smoke test run when appropriate, or reason documented

## Deployment impact

- [ ] no runtime action required
- [ ] application/worker rebuild required
- [ ] Windmill workspace sync required
- [ ] new/changed installation secret or variable documented

## Safety / repository hygiene

- [ ] no credentials, private report data, local `.env`, runtime state, caches, or generated dependency folders are included
- [ ] Telegram/presentation output contains reader-facing information rather than internal ranking/model diagnostics
- [ ] production ordering remains `run -> persist -> deliver`
