# Contributing

Thank you for helping build SemanticVideo as reusable open infrastructure.

## Development setup

```bash
git clone https://github.com/TristinOrg/SemanticVideo.git
cd SemanticVideo
uv sync --all-groups
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run mypy src
```

## Change scope

- Keep changes small and aligned with the current roadmap milestone.
- Add tests for schema rules and behavior changes.
- Update examples and documentation when public models change.
- Keep core schemas independent of proprietary model providers.
- Record durable architectural choices in `docs/adr/`.

## Commit messages

Use [Conventional Commits](https://www.conventionalcommits.org/):

```text
feat(schema): add typed location annotations

- add confidence-aware provenance records
- validate annotation ranges against media duration
- update example manifests and schema fixtures
```

Common types include `feat`, `fix`, `docs`, `test`, `refactor`, `build`, `ci`,
and `chore`.

## Pull requests

Describe:

- what changed
- why the change is needed
- compatibility implications
- validation performed

Schema-breaking changes require a migration strategy and a versioning decision.

