# Changelog

All notable changes to FBA-Bench Enterprise will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0-rc1] - 2026-01-07

### Added
- **Enterprise Version 1.0 Release Candidate**: Production-ready release with all critical issues resolved
- Redis-backed experiment run persistence via `ExperimentRunStore` class
- Comprehensive investment readiness improvements
- Security hardening for production deployments

### Changed
- Version bumped from 0.1.0 to 1.0.0-rc1
- License classifier updated from MIT to Proprietary License for consistency
- Redis password now uses environment variable substitution in production docker-compose
- Test imports now use pytest.importorskip for graceful handling of optional dependencies

### Security
- **Critical**: Removed hardcoded `redis_password_dev` from `docker-compose.prod.yml`
- Redis authentication now requires `REDIS_PASSWORD` environment variable in production
- Updated security contact email to security@fba-bench.com
- All production secrets must be provided via environment variables

### Fixed
- Test collection errors in `test_baseline_agent_v1.py` and `test_infrastructure_complete.py`
- Import path issues for infrastructure and agent modules
- License metadata inconsistency between LICENSE file and pyproject.toml classifiers

---

## [Unreleased]

### Added
- **Enterprise Version 1.0 Baseline**: Created golden master baseline from Tier 2 ("supply chain crisis") scenarios, saved as `artifacts/enterprise_v1.0_baseline.parquet`.
- New integration test `tests/integration/test_tier2_golden_master.py` for generating and validating the Enterprise V1.0 Baseline.
- Updated `scripts/verify_golden_masters.py` to include Tier 2 golden master verification.
- Enhanced DB session lifecycle using `scoped_session` for thread-safety and `expire_on_commit=False`.
- Implemented canonical dependency exports from `api/dependencies.py` for standardized imports.
- Introduced a CI workflow in `.github/workflows/ci.yml` for automated testing and linting of Python backend and Node.js frontends.
- Added `.dockerignore` to exclude development artifacts and temporary files from Docker builds.
- Established baseline documentation: `SECURITY.md`, `CONTRIBUTING.md`, and `CHANGELOG.md`.
- Created `.env.example` to guide environment variable setup for development and deployment.

### Changed
- Strengthened database session management with `SessionLocal.remove()` in `get_db()`'s finally block.

---

## [1.0.0] - TBD

### Added
- Initial stable release of FBA-Bench Enterprise
- Core features for JWT authentication, SQLite stability improvements, and Pydantic v2 integration
- Stripe compatibility for payment processing
- Performance shims and optimizations
- Full observability stack (OpenTelemetry, Prometheus, Grafana)
- Multi-agent benchmarking with LangChain and CrewAI support
