# Plugin Framework

## Overview

This repo contains a plugin framework intended to let you extend FBA-Bench with:
- New scenarios
- New agents
- New tools
- New metrics

Primary code lives in:
- `src/plugins/plugin_framework.py`
- `src/plugins/plugin_loader.py`
- `src/plugins/` subpackages for scenario/agent/tool/metrics plugin base classes

There is also a longer narrative README in:
- `src/plugins/README.md`

## What The Plugin System Provides

At a high level, the framework supports:
- Plugin discovery and loading from a directory
- Basic plugin lifecycle hooks (load/enable/disable/unload)
- Metadata and compatibility fields

## Integration Status

The plugin framework is implemented as a reusable subsystem under `src/plugins/`.
Whether it is active in your runtime depends on the entrypoint you use and whether
your orchestrator/engine calls into the plugin manager.

If you plan to rely on plugins in production runs, treat the plugin manager as
an explicit dependency you wire into:
- scenario registry / scenario selection
- agent runner selection
- tool schema / tool gateway
- metrics registry

## Quick Start (Minimal)

1) Read the base classes and expected metadata shapes:
- `src/plugins/scenario_plugins/base_scenario_plugin.py`
- `src/plugins/agent_plugins/base_agent_plugin.py`

2) Implement a plugin module that returns stable metadata and a deterministic
initialize function.

3) Load plugins via the manager:
- `src/plugins/plugin_framework.py` (`PluginManager`)

For a full example layout and sample code, see `src/plugins/README.md`.

