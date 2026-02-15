# Observability & Instrumentation

## Overview

FBA-Bench Enterprise provides observability at three levels:
- **Application logs** (structured where possible)
- **Metrics** (Prometheus-style)
- **Tracing** (OpenTelemetry)

Key code areas:
- Instrumentation helpers: `src/instrumentation/`
- Runtime alerting/trace analysis: `src/observability/`
- API metrics endpoint: `src/fba_bench_api/api/routes/metrics.py`

## Metrics

The API exposes a metrics endpoint:
- `GET /api/metrics`

In the one-click Docker stack, it is reachable via the nginx front door.

## Tracing (OpenTelemetry)

The repo includes OTel-friendly patterns and configuration hooks. Typical env vars:
- `OTEL_EXPORTER_OTLP_ENDPOINT`
- `OTEL_SERVICE_NAME`

See also: `docs/observability.md`

## ClearML (Optional)

There is integration scaffolding for ClearML:
- `src/instrumentation/clearml_tracking.py`

This is intended for experiment/run tracking when you want a hosted UI and artifact storage.

## Alerts / Trace Analysis

Alerting and trace inspection helpers live in:
- `src/observability/alert_system.py`
- `src/observability/trace_analyzer.py`

These are useful when you’re debugging:
- slow ticks (which tool/model caused delays)
- error spikes
- regressions between runs

