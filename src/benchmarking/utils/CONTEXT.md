# Utils - Context

> **Last Updated**: 2024-01-20

## Purpose

This directory contains utility functions and cross-cutting concerns like async compatibility and error handling for the benchmarking system.

## Key Files

| File | Description |
|------|-------------|
| `error_handling.py` | Centralized error handling and logging system for FBA-Bench components. |
| `asyncio_compat.py` | Shims and helpers for cross-platform and cross-version async execution. |

## Dependencies

- **Internal**: `benchmarking.registry`
- **External**: `asyncio`, `logging`, `traceback`

## Architecture Notes

- **Absolute Imports**: Utilities should use absolute imports from `src/` where possible.
- **Error Handling**: `ErrorHandler` manages history, stats, and logging. It should be used via the `handle_errors` decorator or direct call to `handle_error`.
- **Top-level Imports**: Fixed `E0402` errors by ensuring utilities do not use relative imports beyond the top-level package.

## Related

- [Benchmarking Context](../CONTEXT.md)
- [Registry Context](../registry/CONTEXT.md)
