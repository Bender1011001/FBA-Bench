.PHONY: be-migrate be-test lint format-check format-fix type-check type-check-strict test-contracts test-all coverage ci-local pre-commit-install pre-commit-run sim-contract-check sim-matrix-dry-run

# Use Poetry to run all Python tooling by default
# Detect Poetry command (Windows-friendly)
# Use the CLI entrypoint instead of `py -m poetry` because Poetry has no __main__.
# Use the most robust way to invoke Poetry on Windows/Anaconda.
ifeq ($(OS),Windows_NT)
NULLDEV := NUL
else
NULLDEV := /dev/null
endif
POETRY := $(shell python -m poetry --version >$(NULLDEV) 2>&1 && echo python -m poetry || echo poetry)


# -----------------------------------------------------------------------------
# Backend commands (legacy shims)
# -----------------------------------------------------------------------------
be-migrate:
	$(POETRY) run dotenv run alembic upgrade head

be-test:
	$(POETRY) run pytest -q

# -----------------------------------------------------------------------------
# Quality gates (mirror CI)
# -----------------------------------------------------------------------------
lint:
	$(POETRY) run ruff check --ignore E501,E402,F811,F401,F841,F821,E722,E741,E721,E712 src tests

format-check:
	$(POETRY) run black --check src tests

format-fix:
	$(POETRY) run black src tests

type-check:
	@echo "Running mypy (non-blocking). Use 'make type-check-strict' to enforce."
	-$(POETRY) run mypy --namespace-packages src tests

type-check-strict:
	$(POETRY) run mypy --config-file mypy_strict.ini

# -----------------------------------------------------------------------------
# Tests
# -----------------------------------------------------------------------------
test-unit:
	$(POETRY) run pytest -q \
		tests/unit/api/test_dependencies_managers.py \
		tests/unit/test_eventbus_logging.py \
		tests/unit/test_learning.py

test-integration:
	$(POETRY) run pytest -m integration -v --cov=src --cov-report=xml --cov-report=term-missing

test-contracts:
	$(POETRY) run pytest -q tests/contracts

test-validation:
	$(POETRY) run pytest -m validation --cov=src --cov-report=xml --cov-report=term-missing

test-performance:
	$(POETRY) run pytest -m performance --cov=src --cov-report=xml --cov-report=term-missing

test-all:
	$(POETRY) run pytest -m "not slow" --cov=src --cov-report=term-missing --cov-report=html:htmlcov --cov-report=xml --cov-fail-under=80 --ignore=integration_tests --ignore=scripts

# Timeboxed full test run to avoid local hangs; respects pytest-timeout settings from pyproject
test-all-timeboxed:
	$(POETRY) run pytest -m "not slow and not performance" --cov=src --cov-report=xml --maxfail=1 -vv -s --ignore=integration_tests --ignore=scripts

# Run all including slow and performance tests (use with caution)
test-complete:
	$(POETRY) run pytest --cov=src --cov-report=term-missing --cov-report=html:htmlcov --cov-report=xml --cov-fail-under=80 --ignore=integration_tests --ignore=scripts

coverage: test-all

# -----------------------------------------------------------------------------
# Verification helpers
# -----------------------------------------------------------------------------
verify-golden:
	$(POETRY) run python scripts/verify_golden_masters.py

verify-coverage:
	$(POETRY) run python scripts/verify_coverage_thresholds.py

sim-contract-check:
	$(POETRY) run python scripts/verify_sim_benchmark_contract.py --latest

sim-matrix-dry-run:
	$(POETRY) run python scripts/run_sim_benchmark_matrix.py --days 14 --seeds 42,43,44 --print-only

# -----------------------------------------------------------------------------
# Website and Documentation
# -----------------------------------------------------------------------------
build-docs:
	$(POETRY) run python generate_github_pages.py

# -----------------------------------------------------------------------------
# CI parity aggregate
# -----------------------------------------------------------------------------
ci-local:
	py -m pip install -q poetry
	$(POETRY) install --no-interaction --no-ansi
	$(MAKE) lint
	$(MAKE) format-check
	$(MAKE) type-check
	$(MAKE) test-unit
	$(MAKE) test-contracts
	$(MAKE) verify-golden
	$(MAKE) build-docs

# -----------------------------------------------------------------------------
# Pre-commit helpers
# -----------------------------------------------------------------------------
pre-commit-install:
	$(POETRY) run pre-commit install --install-hooks

pre-commit-run:
	$(POETRY) run pre-commit run --all-files --show-diff-on-failure

# -----------------------------------------------------------------------------
# Database migrations
# -----------------------------------------------------------------------------
db-migrate:
	$(POETRY) run alembic upgrade head

# -----------------------------------------------------------------------------
# Build targets
# -----------------------------------------------------------------------------
build:
	docker-compose build

frontend-build:
	cd frontend && npm ci && npm run build
	cp -r frontend/dist ./static

# -----------------------------------------------------------------------------
# Deployment
# -----------------------------------------------------------------------------
deploy:
	docker-compose -f docker-compose.prod.yml up -d

deploy-down:
	docker-compose -f docker-compose.prod.yml down

# -----------------------------------------------------------------------------
# Load Testing
# -----------------------------------------------------------------------------
load-test:
	poetry run locust -f locustfile.py --headless -u 10 -r 2 --run-time 30s --host=http://localhost:8000

# -----------------------------------------------------------------------------
# CI enhancements
# -----------------------------------------------------------------------------
ci-docker:
	$(MAKE) build
	docker-compose run api make ci-local

# ci-local target consolidated above

# -----------------------------------------------------------------------------
# Deployment targets
# -----------------------------------------------------------------------------
VERSION ?= 1.0.0
IMAGE_NAME ?= fba-bench-app
REGISTRY ?= docker.io/$(USER)

deploy-prod:
	docker-compose -f docker-compose.prod.yml up -d --build

rollback:
	docker-compose -f docker-compose.prod.yml down
	@echo "Rollback complete. To restore previous version, pull specific image tag or use git revert."

release: deploy-prod
	git tag -a v$(VERSION) -m "Release v$(VERSION)"
	git push origin v$(VERSION)
	docker build -t $(REGISTRY)/$(IMAGE_NAME):$(VERSION) -f Dockerfile.prod .
	docker push $(REGISTRY)/$(IMAGE_NAME):$(VERSION)
	docker tag $(REGISTRY)/$(IMAGE_NAME):$(VERSION) $(REGISTRY)/$(IMAGE_NAME):latest
	docker push $(REGISTRY)/$(IMAGE_NAME):latest
	@echo "Release v$(VERSION) tagged, pushed, and deployed."

# -----------------------------------------------------------------------------
# Development Startup
# -----------------------------------------------------------------------------
start:
	scripts\\fba-start.bat
