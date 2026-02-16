# Contributing to FBA-Bench Enterprise

Thank you for considering contributing to FBA-Bench Enterprise! We value contributions that improve the codebase, documentation, or features while adhering to our standards for quality, security, and maintainability. All contributors must follow these guidelines.

## Code of Conduct

This project follows the [Contributor Covenant Code of Conduct](CODE_OF_CONDUCT.md). By participating, you agree to uphold it. Reports of unacceptable behavior can be sent to conduct@fba-bench.com.

## Getting Started

### Prerequisites
- Python 3.10–3.13
- Poetry
  - macOS/Linux:
    - `curl -sSL https://install.python-poetry.org | python3 -`
  - Windows (PowerShell):
    - `(Invoke-WebRequest -Uri https://install.python-poetry.org -UseBasicParsing).Content | py -`
- Git
- Make (or Git Bash/WSL on Windows)
- Docker (recommended for integration and deployment testing)

### Setup Development Environment
Follow [DEV_SETUP.md](DEV_SETUP.md) for detailed instructions:
1. Clone/fork the repo.
2. `poetry install && poetry shell`
3. Copy `.env.example` to `.env` and configure.
4. `make be-migrate`
5. Verify: `make ci-local`

This ensures your environment matches production standards.

## Development Workflow

### Branching
- Use feature branches: `git checkout -b feat/your-feature-name`
- Base on `main` for new features.
- Keep branches small and focused.

### Making Changes
1. **Identify Issue**: Use or create a GitHub issue for your work.
2. **Code**: Implement in `src/` packages. Prefer importing the installed package names (e.g., `from fba_bench_core...`, `from fba_bench_api...`).
3. **Test Locally**: 
    - Unit/Contracts: `poetry run pytest -q`
    - Full: `make test-all`
    - Integration: `poetry run pytest -m integration -v`
4. **Lint and Format**: `make lint && make format-fix`
5. **Type Check**:
   - Fast/local: `make type-check` (non-blocking)
   - Strict gate (CI-quality): `make type-check-strict`
6. **CI Parity**: `make ci-local` (must pass before push).

### Commit Messages
Use [Conventional Commits](https://www.conventionalcommits.org/):
- `feat(scope): add new feature` – New functionality.
- `fix(scope): resolve bug` – Bug fixes.
- `docs(scope): update documentation` – Docs only.
- `style(scope): formatting changes` – No functional changes.
- `refactor(scope): code restructuring` – No behavior change.
- `test(scope): add tests` – Testing only.
- `chore(scope): misc (e.g., deps)` – Maintenance.
- `ci(scope): workflow updates`.

Example: `feat(benchmarking): add OpenRouter model support`

Keep messages concise (<72 chars subject); body for details.

## Coding Standards

All contributions must strictly follow the rules documented in [AGENTS.md](AGENTS.md), including:

- **Structure**: Code in `src/` packages. Small, focused modules. Avoid cyclic imports.
- **Naming**:
  - Modules/functions: `snake_case`
  - Classes: `PascalCase`
  - Constants: `UPPER_SNAKE_CASE`
- **Formatting**: 4-space indent, 100-char lines. Use Black (repo standard).
- **Linting**: Ruff for checks (CI/Makefile enforces).
- **Typing**: Mypy strict on `src/`. All public APIs typed; use `typing` or `pydantic`.
- **Imports**: Use absolute imports (no relative imports). Prefer the installed package names (`fba_bench_core`, `fba_bench_api`, etc.).
- **Security**: No secrets in code. Use Pydantic Settings for configs. Sanitize inputs.
- **Dependencies**: Add via Poetry (`poetry add package` for prod, `--group dev` for tools). Pin in `pyproject.toml`.
- **Async**: Use async where beneficial (e.g., API, LLM calls); pytest-asyncio for tests.

Review [Coding Style](AGENTS.md#coding-style--naming-conventions) for details.

## Testing Requirements

All changes must include tests:
- **Unit**: Cover new/changed logic (80%+ coverage).
- **Integration**: For cross-module interactions.
- **Contracts**: Schema/API validation if affected.

See [Testing Strategy](docs/testing.md) for types and commands. Tests must pass `make test-all`.

## Documentation

- Update inline docs (docstrings) for new public APIs.
- Add examples in `examples/` or `docs/guides/`.
- For major changes, update [architecture.md](docs/architecture.md), [API.md](docs/API.md), or README.
- Use Markdown with consistent headers, code blocks (```python), and links.

## Pull Requests (PRs)

### Preparation
1. Push branch: `git push origin feat/your-feature`
2. Create PR from GitHub (base: `main`).
3. Ensure `make ci-local` passes locally.

### PR Template
PRs must include:
- **Description**: What/why (link issue).
- **Rationale**: Problem solved, alternatives considered.
- **Changes**: Key diffs.
- **Screenshots/Logs**: For UI/API/behavior changes.
- **Tests**: Added/updated.
- **Checklist**:
  - [ ] `make ci-local` passes
  - [ ] Tests added/updated
  - [ ] Docs updated
  - [ ] No breaking changes (or noted)
  - [ ] Security review (no secrets, sanitized inputs)

### Review Process
- Assign reviewers (or self if minor).
- Address feedback iteratively.
- Squash commits if needed; rebase for clean history.
- Merge via GitHub (squash/rebase preferred; require approvals).

### Post-Merge
- Update branch: `git checkout main && git pull --rebase origin main`
- Delete branch.

## Security and Sensitive Contributions

- **Vulnerabilities**: Report privately via [SECURITY.md](SECURITY.md).
- **Sensitive Code**: Flag in PR (e.g., crypto, auth); review by security lead.
- **No Secrets**: Never commit keys; use `.env` or mocks.

## Additional Guidelines

- **Scope**: Contributions should align with project goals (AI benchmarking, e-commerce sims). Off-topic proposals via issues/discussions.
- **Releases**: Follow Semantic Versioning; changelog updates in PRs.
- **Community**: Join discussions for ideas; credits in CHANGELOG for significant contribs.

For questions, open an issue or discuss on GitHub. We appreciate your efforts to make FBA-Bench Enterprise better!
