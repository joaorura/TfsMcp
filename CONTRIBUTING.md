# Contributing

## Development setup

1. Create/install dependencies:
   - `pip install -e .[dev]`
2. Run tests:
   - `python -m pytest -q`

## Pull request checklist

1. Keep changes focused and small.
2. Add or update tests for behavior changes.
3. Keep repository free of machine-specific values (usernames, local absolute paths, secrets).
4. Update `README.md` when tool behavior or commands change.

## Code style

1. Prefer clear, explicit Python over clever shortcuts.
2. Preserve existing APIs unless the PR explicitly introduces a breaking change.
3. Avoid unrelated refactors in the same PR.

## Security

If a change may expose credentials, local profile data, internal URLs, or other sensitive values, stop and sanitize before opening the PR.
