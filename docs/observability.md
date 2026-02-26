# Observability & Instrumentation

## Overview

FBA-Bench provides observability at three levels:
- **Application logs** (structured where possible)
- **Metrics** (Prometheus-style)
- **Tracing** (OpenTelemetry)

Key code areas:
- Instrumentation helpers: `src/instrumentation/`
- Runtime alerting/trace analysis: `src/observability/`
- API metrics endpoint: `src/fba_bench_api/api/routes/metrics.py`

## Logs

- Controlled via `LOG_LEVEL` (e.g. `INFO`, `DEBUG`).
- Prefer structured logs in production (collector/agent side).

## Metrics

The API exposes a metrics endpoint:
- `GET /api/metrics`

In Docker stacks, you can scrape the API container directly or via reverse proxy.

## Tracing (OpenTelemetry)

When enabled, traces/metrics can be exported to an OTLP collector.

Common environment variables:
- `OTEL_EXPORTER_OTLP_ENDPOINT` (e.g. `https://otel-collector:4317` in production)
- `OTEL_SERVICE_NAME` (optional)

Production guidance:
- Use TLS for OTLP endpoints.
- Do not export telemetry to public endpoints without authentication.

## ClearML (Optional)

There is integration scaffolding for ClearML:
- `src/instrumentation/clearml_tracking.py`

This is intended for experiment/run tracking when you want a hosted UI and artifact storage.

## Alerts / Trace Analysis

Alerting and trace inspection helpers live in:
- `src/observability/alert_system.py`
- `src/observability/trace_analyzer.py`

These are useful when debugging:
- Slow ticks (which tool/model caused delays)
- Error spikes
- Regressions between runs
