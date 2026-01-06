---
description: Audit the project for issues, incomplete features, and production readiness
---

# Production Readiness Audit

This workflow performs a comprehensive audit of the codebase to identify issues that may prevent production deployment.

## 1. Static Code Analysis

// turbo
```bash
# Run linter
cd C:\Users\admin\GitHub-projects\fba\FBA-Bench-Enterprise
make lint
```

// turbo
```bash
# Run type checker (if configured)
cd C:\Users\admin\GitHub-projects\fba\FBA-Bench-Enterprise
mypy src/ --ignore-missing-imports 2>&1 | head -50
```

## 2. Search for Incomplete Code

Search for common markers of incomplete implementations:

```
# Find TODOs
grep -r "TODO" src/ --include="*.py" | head -30

# Find FIXME
grep -r "FIXME" src/ --include="*.py" | head -30

# Find Future: comments (project-specific pattern)
grep -r "Future:" src/ --include="*.py" | head -30
grep -r "Future:" godot_gui/ --include="*.gd" | head -30

# Find placeholder/stub implementations
grep -r "NotImplementedError" src/ --include="*.py" | head -20
grep -r "pass\s*$" src/ --include="*.py" | head -20

# Find hardcoded values that should be configurable
grep -r "localhost" src/ --include="*.py" | head -20
grep -r "127.0.0.1" src/ --include="*.py" | head -20
```

## 3. Test Suite Health

// turbo
```bash
# Run tests and check for failures
cd C:\Users\admin\GitHub-projects\fba\FBA-Bench-Enterprise
pytest --collect-only -q 2>&1 | tail -10
```

```bash
# Check test coverage (if coverage is configured)
pytest --cov=src --cov-report=term-missing 2>&1 | tail -30
```

## 4. Security Audit

// turbo
```bash
# Check for known vulnerabilities in dependencies
cd C:\Users\admin\GitHub-projects\fba\FBA-Bench-Enterprise
pip-audit 2>&1 | head -30
```

```
# Search for potential secrets/credentials in code
grep -rE "(api_key|secret|password|token)\s*=" src/ --include="*.py" | grep -v "Optional\[" | head -20

# Check for debug flags that should be disabled
grep -r "DEBUG\s*=\s*True" src/ --include="*.py"
grep -r "TESTING\s*=\s*True" src/ --include="*.py"
```

## 5. Configuration Validation

Review core configuration files for missing or placeholder values:

- `config/config.yaml` - Check for `localhost`, `example.com`, or missing keys
- `.env.example` - Ensure all required env vars are documented
- `docker-compose.prod.yml` - Verify production-ready settings

## 6. Documentation Completeness

Check that key documentation exists and is up-to-date:

- [ ] `README.md` - Project overview
- [ ] `DEV_SETUP.md` - Developer setup instructions
- [ ] `docs/architecture.md` - System architecture
- [ ] `CONTRIBUTING.md` - Contribution guidelines
- [ ] `LICENSE` - License file
- [ ] API documentation (OpenAPI/Swagger)

## 7. Database & Migration Check

// turbo
```bash
# List pending migrations
cd C:\Users\admin\GitHub-projects\fba\FBA-Bench-Enterprise
alembic history --verbose 2>&1 | tail -20
```

## 8. Review CONTEXT.md Files

Read the `CONTEXT.md` files for each major directory to identify documented issues:

- `.agent/context.md` - Root issues list
- `src/services/CONTEXT.md`
- `src/fba_bench_api/CONTEXT.md`
- `src/agents/CONTEXT.md`
- `godot_gui/CONTEXT.md`
- `infrastructure/CONTEXT.md`
- `tests/CONTEXT.md`

## 9. Generate Report

After completing all checks, compile a report with:

1. **Critical Issues** - Must fix before production
2. **High Priority** - Should fix before production
3. **Medium Priority** - Can be deferred but noted
4. **Low Priority / Tech Debt** - Non-blocking, for future cleanup

Save the report to `.agent/audit_report.md`.
