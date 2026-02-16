# LLM Interface & Providers

## Overview

The LLM integration layer is designed to let the benchmark run against different providers with a consistent contract, while supporting reproducibility tooling (cache, deterministic wrappers).

Primary directory:
- `src/llm_interface/`

## Key Concepts

- Provider clients: OpenAI/OpenRouter/etc clients implement a common calling surface.
- Contracts: `src/llm_interface/contract.py` defines the provider-facing interface and error types.
- Deterministic wrapper (optional): `src/llm_interface/deterministic_client.py` wraps any provider client with caching/mode control.

## Configuration

Provider configuration structures typically live under:
- `src/llm_interface/llm_config.py`
- `configs/` and `config/` (YAML templates and environment-driven settings)

## Reproducibility Integration

For deterministic runs, the intended pairing is:
- `src/llm_interface/deterministic_client.py`
- `src/reproducibility/llm_cache.py`
- `src/reproducibility/simulation_modes.py`

See: `docs/reproducibility.md`

