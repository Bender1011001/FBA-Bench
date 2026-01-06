# FBA-Bench Enterprise Repository Structure

> Last updated: 2026-01-05

This document provides an overview of the repository's folder structure after the cleanup consolidation.

## Directory Overview (41 folders)

### Core Application
| Folder | Purpose |
|--------|---------|
| `src/` | Main source code (477+ items) - all core modules |
| `config/` | Application configuration (model_config, observability, grafana, prometheus) |
| `configs/` | Scenario YAML files and experiment configurations |
| `constraints/` | Budget enforcer, token counter, tier configs |
| `events/` | Event definitions and event bus |

### API & Services
| Folder | Purpose |
|--------|---------|
| `dashboard/` | Dashboard service API |
| `leaderboard/` | Leaderboard functionality |
| `metrics/` | Metrics collection |

### Testing
| Folder | Purpose |
|--------|---------|
| `tests/` | Main test suite (163 items) - unit, integration, regression |
| `integration/` | Real-world adapters and marketplace integrations |
| `integration_tests/` | Integration test scenarios and validation reports |

### Agents & Bots
| Folder | Purpose |
|--------|---------|
| `baseline_bots/` | Reference bot implementations (greedy, GPT, Claude, etc.) |
| `learning/` | RL/meta-learning modules for agent training |
| `learning_data/` | Learning artifacts and experience data |

### Infrastructure & Deployment
| Folder | Purpose |
|--------|---------|
| `infrastructure/` | Deployment scripts, Docker configs, tenant setup (37 items) |
| `infrastructure/terraform/` | Terraform AWS infrastructure (main.tf) |
| `alembic/` | Database migration scripts |
| `deploy/` | Tenant deployment configs |

### Godot Frontend
| Folder | Purpose |
|--------|---------|
| `godot_gui/` | Godot 4.5 GUI project (26 items) |

### Documentation
| Folder | Purpose |
|--------|---------|
| `docs/` | All documentation (41 items) |
| `docs/planning/` | Project roadmaps and planning documents |
| `.github/` | CI/CD workflows and GitHub templates |

### Experiments & Research
| Folder | Purpose |
|--------|---------|
| `golden_masters/` | Baseline test data for reproducibility |
| `medusa_experiments/` | Medusa analyzer for genome experiments |
| `redteam_scripts/` | Security testing and adversarial exploits |

### Utilities
| Folder | Purpose |
|--------|---------|
| `scripts/` | Utility scripts (85 items) |
| `tools/` | CLI tools and helpers |
| `examples/` | Example implementations |
| `community/` | Community contribution tools |
| `marketing/` | Marketing assets and campaigns |

### Runtime/Cache (gitignored)
| Folder | Purpose |
|--------|---------|
| `.venv/` | Python virtual environment |
| `__pycache__/` | Python bytecode cache |
| `.pytest_cache/` | Pytest cache |
| `clearml-data/` | ClearML artifacts |
| `artifacts/` | Generated benchmark artifacts |
| `config_storage/` | Runtime config cache |

### Other
| Folder | Purpose |
|--------|---------|
| `dependency_injector/` | DI container helpers |
| `instrumentation/` | OpenTelemetry tracer |
| `prometheus_client/` | Prometheus metrics wrapper |
| `env/` | Environment file templates |
| `.idx/` | IDX IDE configuration |

## Deleted/Consolidated Folders

The following folders were removed during the 2026-01-05 cleanup:

| Folder | Action | Reason |
|--------|--------|--------|
| `agents/` | Deleted | Empty, moved to `src/agents/` |
| `scenarios/` | Deleted | Empty, moved to `src/scenarios/` |
| `results/` | Deleted | Empty runtime artifact |
| `data/` | Deleted | Empty runtime artifact |
| `logs/` | Deleted | Empty runtime artifact |
| `temp/` | Deleted | Empty runtime artifact |
| `ssl/` | Deleted | Empty placeholder |
| `version_manifests/` | Deleted | Empty placeholder |
| `audit_trails/` | Deleted | Empty runtime artifact |
| `venv/` | Deleted | Duplicate of `.venv/` (freed ~480MB) |
| `infra/` | Merged | `main.tf` moved to `infrastructure/terraform/` |
| `llm_interface/` (root) | Deleted | Duplicate of `src/llm_interface/` |
| `context-code/` | Moved | Content moved to `docs/planning/` |
| `src/fba_bench_api/api/routers/` | Merged | Consolidated into `src/fba_bench_api/api/routes/` |

## File Organization Guidelines

1. **New Python modules** → `src/` subdirectories
2. **New tests** → `tests/` with appropriate subdirectory
3. **New scenarios** → `configs/` or `src/scenarios/`
4. **New agents** → `src/agents/` or `baseline_bots/`
5. **New docs** → `docs/` with appropriate subdirectory
6. **Infrastructure changes** → `infrastructure/`
7. **CI/CD changes** → `.github/workflows/`

## Folder Count Summary

- **Before cleanup**: 54 folders
- **After cleanup**: 41 folders
- **Reduction**: 13 folders (24%)
- **Disk space saved**: ~480MB (from duplicate venv)
