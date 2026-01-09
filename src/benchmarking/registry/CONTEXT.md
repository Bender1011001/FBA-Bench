# Registry - Context

> **Last Updated**: 2026-01-08

## Purpose

This directory provides centralized management of global state and registries for the benchmarking module. It ensures singletons and shared variables are managed consistently.

## Key Files

| File | Description |
|------|-------------|
| `global_registry.py` | Implementation of the `GlobalRegistry` singleton for managing various benchmark components. |
| `global_variables.py` | Container for global settings, paths, and system configurations. |

## Dependencies

- **Internal**: `benchmarking.core`, `benchmarking.utils`
- **External**: `typing`, `pydantic`

## Architecture Notes

- **Singleton Pattern**: Both `GlobalRegistry` and `GlobalVariables` use a singleton pattern with a `_initialized` flag.
- **Pylint E0203 Fix**: Access to `_initialized` in `__init__` now uses `getattr(self, "_initialized", False)` to avoid access-before-definition errors during the very first instantiation.
- **Clean Code**: Verified clean of unused variables and logging f-strings (Jan 2026).
- **Centralization**: All components should prefer using these registries rather than creating ad-hoc global state.

## Related

- [Benchmarking Context](../CONTEXT.md)
- [Scenarios Context](../scenarios/CONTEXT.md)
