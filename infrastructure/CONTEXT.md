# Infrastructure - Context

> **Last Updated**: 2026-01-05

## Purpose

The Infrastructure module manages deployment, scaling, multi-tenancy, and cloud resource provisioning for the FBA-Bench Enterprise platform.

## Key Files

| File | Description |
|------|-------------|
| `deployment.py` | Core deployment logic and automation. |
| `distributed_coordinator.py` | Orchestration for distributed simulation runs. |
| `distributed_event_bus.py` | Redis-backed event bus for cross-node communication. |
| `fast_forward_engine.py` | Optimization for high-speed simulation execution. |
| `llm_batcher.py` | Batching layer for LLM requests to optimize cost and latency. |
| `performance_monitor.py` | Real-time monitoring of resource usage and simulation health. |
| `resource_manager.py` | Management of compute and storage resources. |

## Subdirectories

- `terraform/`: Infrastructure as Code (AWS/GCP provider) for provisioning cloud environments.
- `tenants/`: Configuration for isolated enterprise tenant environments.
- `config/`: Centralized configuration templates and environment generation scripts.

## Multi-Tenancy

- **Consolidated Setup**: `infrastructure/config/generate_tenant_env.sh` is the primary script for generating new tenant environments.
- **Legacy Path**: Redundant scripts remain in `infrastructure/scripts/` and are slated for removal.

## Scaling

The system uses a distributed event bus and coordinator to scale simulations across multiple worker nodes, utilizing Redis for real-time IPC.

## ⚠️ Known Issues

| Location | Issue | Severity |
|----------|-------|----------|
| `deployment.py` | Large (33KB, 1000+ LOC) and likely contains mixed concerns (deployment logic vs. state management). | Medium |

## Related

- [.agent/context.md](file:///c:/Users/admin/GitHub-projects/fba/FBA-Bench-Enterprise/.agent/context.md) - Root overview
- [docs/ops/](file:///c:/Users/admin/GitHub-projects/fba/FBA-Bench-Enterprise/docs/ops/) - Operational guides
