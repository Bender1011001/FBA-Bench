# Observability

The API supports basic observability through logs, Prometheus-style metrics, and OpenTelemetry (OTel).

## Logs

- Controlled via `LOG_LEVEL` (e.g. `INFO`, `DEBUG`).
- Prefer structured logs in production (collector/agent side).

## Metrics

- Metrics endpoint: `GET /api/metrics`
- In Docker stacks, you can scrape the API container directly or via reverse proxy.

## OpenTelemetry

When enabled, traces/metrics can be exported to an OTLP collector.

Common environment variables:
- `OTEL_EXPORTER_OTLP_ENDPOINT` (e.g. `https://otel-collector:4317` in production)
- `OTEL_SERVICE_NAME` (optional)

Production guidance:
- Use TLS for OTLP endpoints.
- Do not export telemetry to public endpoints without authentication.

