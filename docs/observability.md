Production Observability for FBA Benchmarking v3.0.0-rc1

Status: Implemented and production-ready

This document describes the end-to-end observability stack implemented for the FBA benchmarking project, including secure OTLP ingestion, centralized logs, distributed tracing, metrics collection and alerting, and environment-specific configurations.

1) Current vs. Improved Architecture

Previous state (gaps)
- No secure OTLP receiver endpoints
- No centralized logs backend
- Potential plaintext telemetry transport
- No environment-separated configs or basic alert rules

Improved state (this work)
- Secure OTLP ingestion over TLS for both gRPC :4317 and HTTP :4318
- Authentication enforced at collector via BasicAuth (htpasswd) with optional mTLS
- Centralized logs aggregation to Loki with JSON-structured logs and correlation fields
- Distributed tracing exported to Tempo with production sampling policies
- Metrics exposed locally to Prometheus and remote_write supported for long-term storage
- Span to metrics conversion (spanmetrics) enables latency/error SLOs
- Alerting via Prometheus + Alertmanager with Slack/PagerDuty/email receivers
- Environment-specific collector bundles for dev/staging/prod
- Grafana provisioned with datasources and dashboards

2) Components and Files

OpenTelemetry Collector
- Global default (secure): [otel-collector-config.yaml](otel-collector-config.yaml)
- Environment-specific:
  - Dev (local, simpler): [otel-collector.dev.yaml](config/observability/otel-collector.dev.yaml)
  - Staging (secure, production-like): [otel-collector.staging.yaml](config/observability/otel-collector.staging.yaml)
  - Production (secure, scalable): [otel-collector.prod.yaml](config/observability/otel-collector.prod.yaml)

Prometheus
- Server configuration: [prometheus.yml](prometheus.yml)
- SLO alert rules: [alerts.yml](config/prometheus/alerts.yml)

Alertmanager
- Receivers and routes: [alertmanager.yml](config/alertmanager/alertmanager.yml)

Grafana
- Datasources: [datasources.yaml](config/grafana/provisioning/datasources/datasources.yaml)
- Dashboards provisioning: [dashboards.yaml](config/grafana/provisioning/dashboards/dashboards.yaml)
- Overview dashboard: [FBA-Overview.json](config/grafana/provisioning/dashboards/fba/FBA-Overview.json)

3) Secure OTLP Endpoints

Collector Receivers (staging/prod)
- gRPC: 0.0.0.0:4317 (TLS, mTLS optional, BasicAuth enforced)
- HTTP: 0.0.0.0:4318 (TLS, mTLS optional, BasicAuth enforced)

Key configuration (from [otel-collector-config.yaml](otel-collector-config.yaml)):
- TLS server certificate and key:
  - /etc/ssl/certs/otlp_server.crt
  - /etc/ssl/private/otlp_server.key
- Optional client CA for mTLS:
  - /etc/ssl/certs/otlp_client_ca.crt
- Server-side authentication:
  - auth.authenticator: basicauth/server
  - basicauth/server.htpasswd set via env: OTLP_BASICAUTH_HTPASSWD

Client configuration (applications)
- Use OTEL_EXPORTER_OTLP_HEADERS to pass Basic auth:
  - OTEL_EXPORTER_OTLP_HEADERS=Authorization=Basic <base64(user:pass)>
- Set protocol and endpoint:
  - gRPC: OTEL_EXPORTER_OTLP_PROTOCOL=grpc
  - Endpoint: OTEL_EXPORTER_OTLP_ENDPOINT=https://<collector-host>:4317
- For HTTP/JSON OTLP:
  - OTEL_EXPORTER_OTLP_PROTOCOL=http/protobuf
  - Endpoint: https://<collector-host>:4318

Note about BasicAuth header
- Basic <token> must be base64 of "username:password"
- Example to compute on Linux/macOS:
  - echo -n 'collector_user:strongpassword' | base64
- On Windows PowerShell:
  - [Convert]::ToBase64String([Text.Encoding]::ASCII.GetBytes('collector_user:strongpassword'))

4) Centralized Logging (Loki)

Collector logs pipeline
- Receiver: otlp (from apps) and filelog (optional host/container logs)
- Processors: resource, resourcedetection, batch, memory_limiter
- Exporter: loki (TLS + BasicAuth supported)

Configuration
- Loki endpoint (HTTPS strongly recommended):
  - LOKI_ENDPOINT=https://loki.example.com/loki/api/v1/push
- Credentials via basicauth/loki extension:
  - LOKI_USERNAME / LOKI_PASSWORD
- CA file if using private CA:
  - LOKI_CA_FILE=/etc/ssl/certs/loki_ca.pem

Log correlation
- Python: enable trace/log correlation with OpenTelemetry by setting:
  - OTEL_PYTHON_LOG_CORRELATION=true
  - OTEL_PYTHON_LOG_LEVEL=INFO (as needed)
- Ensure logs contain trace_id/span_id; Loki derived fields in Grafana datasource already reference trace_id.

5) Metrics Collection and Export

Local Prometheus scrape
- Collector exposes metrics at 0.0.0.0:8889
- Prometheus scrapes this endpoint:
  - See [prometheus.yml](prometheus.yml), job_name: "otel-collector"

Span-to-metrics conversion
- spanmetrics processor produces:
  - traces_spanmetrics_latency_bucket
  - traces_spanmetrics_calls_total
- These power p95 latency and error rate SLOs

Remote write (optional but recommended)
- prometheusremotewrite exporter configured with:
  - PROM_REMOTE_WRITE_URL
  - PROM_REMOTE_WRITE_USERNAME / PROM_REMOTE_WRITE_PASSWORD
  - PROM_REMOTE_WRITE_CA_FILE (if needed)

Host/system metrics
- hostmetrics receiver enabled for CPU, memory, disk, network, etc.
- Example metrics:
  - system_cpu_utilization
  - system_memory_utilization

6) Distributed Tracing (Tempo)

Trace exporter
- otlp/tempo exporter configured with TLS and bearer token
  - TEMPO_ENDPOINT
  - TEMPO_BEARER_TOKEN
  - TEMPO_CA_FILE (if needed)

Sampling
- tailsampling processor:
  - Policies for errors, high latency, and probabilistic sampling
  - Production defaults: 10% probabilistic, collect errors and slow traces

7) Security and Encryption

Encryption in transit
- TLS enforced at OTLP receivers (both gRPC/HTTP)
- TLS configured for exporters (Loki/Tempo/RemoteWrite) with CA pinning options

Authentication
- OTLP receivers require BasicAuth; manage credentials via htpasswd secret
- Example htpasswd line (bcrypt recommended):
  - collector_user:$2y$05$Qf0d... (do not commit secrets)

Credential management
- Secrets injected via environment variables or secret mounts
- Strictly keep certs and htpasswd outside of repo; mount at runtime

Network security
- Restrict OTLP ports (4317/4318) to known application subnets
- Expose Prometheus metrics (8889) internally; protect via network policy or reverse proxy auth
- Restrict egress to Loki/Tempo/RemoteWrite endpoints

8) Environment-specific Configuration

Dev ([otel-collector.dev.yaml](config/observability/otel-collector.dev.yaml))
- Plaintext for convenience (local only)
- Insecure TLS allowed for local Tempo/Loki endpoints
- Sampling set to 100% (adjust if noisy)

Staging ([otel-collector.staging.yaml](config/observability/otel-collector.staging.yaml))
- TLS enforced; BasicAuth required
- Reduced sampling (25% probabilistic) + error/latency policies
- Mirrors production topology with distinct endpoints

Production ([otel-collector.prod.yaml](config/observability/otel-collector.prod.yaml))
- Strict TLS, BasicAuth, and optional mTLS for OTLP
- 10% probabilistic sampling + error/latency capture
- Memory limiter tuned higher (2048 MiB default)

Runtime env variables (illustrative)
- Common
  - ENVIRONMENT=production|staging|development
  - PROMETHEUS_USERNAME / PROMETHEUS_PASSWORD (if scraping is protected)
- Loki
  - LOKI_ENDPOINT
  - LOKI_USERNAME / LOKI_PASSWORD
  - LOKI_CA_FILE (optional)
- Tempo
  - TEMPO_ENDPOINT
  - TEMPO_BEARER_TOKEN
  - TEMPO_CA_FILE (optional)
- Remote Write
  - PROM_REMOTE_WRITE_URL
  - PROM_REMOTE_WRITE_USERNAME / PROM_REMOTE_WRITE_PASSWORD
  - PROM_REMOTE_WRITE_CA_FILE (optional)
- OTLP Receiver
  - OTLP_BASICAUTH_HTPASSWD (path to htpasswd file)
- Memory limiter
  - OTEL_MEM_LIMIT_MIB (default 1024/2048)
  - OTEL_MEM_SPIKE_MIB

9) Application Tracing, Metrics, and Logs (Python, no code changes required)

Auto-instrumentation (recommended)
- Install:
  - pip install opentelemetry-distro opentelemetry-exporter-otlp opentelemetry-instrumentation-logging
- Run the API with auto-instrument:
  - Linux/macOS:
    - OTEL_SERVICE_NAME=fba-bench-api \
      OTEL_EXPORTER_OTLP_PROTOCOL=grpc \
      OTEL_EXPORTER_OTLP_ENDPOINT=https://<collector-host>:4317 \
      OTEL_EXPORTER_OTLP_HEADERS="Authorization=Basic <base64(user:pass)>" \
      OTEL_RESOURCE_ATTRIBUTES="deployment.environment=production,service.namespace=fba-bench" \
      OTEL_TRACES_SAMPLER=parentbased_traceidratio \
      OTEL_TRACES_SAMPLER_ARG=0.1 \
      OTEL_PYTHON_LOG_CORRELATION=true \
      opentelemetry-instrument uvicorn fba_bench_api.server.app_factory:create_app --host 0.0.0.0 --port 8000
  - Windows (PowerShell):
    - $env:OTEL_SERVICE_NAME="fba-bench-api"
    - $env:OTEL_EXPORTER_OTLP_PROTOCOL="grpc"
    - $env:OTEL_EXPORTER_OTLP_ENDPOINT="https://<collector-host>:4317"
    - $env:OTEL_EXPORTER_OTLP_HEADERS="Authorization=Basic <base64(user:pass)>"
    - $env:OTEL_RESOURCE_ATTRIBUTES="deployment.environment=production,service.namespace=fba-bench"
    - $env:OTEL_TRACES_SAMPLER="parentbased_traceidratio"
    - $env:OTEL_TRACES_SAMPLER_ARG="0.1"
    - $env:OTEL_PYTHON_LOG_CORRELATION="true"
    - opentelemetry-instrument uvicorn fba_bench_api.server.app_factory:create_app --host 0.0.0.0 --port 8000

Logging integration
- The project already provides robust JSON/text logging with request_id middleware
- With OTEL_PYTHON_LOG_CORRELATION=true, trace_id/span_id are injected into logs
- Loki derived field trace_id is configured in Grafana datasource for trace correlation

10) Dashboards and Datasources (Grafana)

Provisioning
- Datasources: [datasources.yaml](config/grafana/provisioning/datasources/datasources.yaml)
  - Prometheus (uid: prometheus_ds), Loki (uid: loki_ds), Tempo (uid: tempo_ds)
  - Traces-to-logs and traces-to-metrics wired
- Dashboards provider: [dashboards.yaml](config/grafana/provisioning/dashboards/dashboards.yaml)
- Overview dashboard: [FBA-Overview.json](config/grafana/provisioning/dashboards/fba/FBA-Overview.json)
  - p95 latency, error rate, RPS, CPU and Memory utilization, Logs panel

11) Alerting and Monitoring Rules

Rules
- Prometheus rules: [alerts.yml](config/prometheus/alerts.yml)
  - HighLatencyP95 / HighLatencyP95_HTTP
  - HighErrorRate / HighErrorRate_HTTP
  - HighCPUUtilization / HighMemoryUtilization (+ node exporter fallbacks)
  - OtelCollectorDown, write path errors

Alertmanager
- Configuration: [alertmanager.yml](config/alertmanager/alertmanager.yml)
- Slack: SLACK_WEBHOOK_URL, SLACK_CHANNEL
- PagerDuty: PAGERDUTY_ROUTING_KEY
- Email: SMTP_SMARTHOST, SMTP_FROM, SMTP_USERNAME, SMTP_PASSWORD, ALERT_EMAIL_TO
- Enable environment expansion in Alertmanager:
  - --enable-feature=expand-env
  - Alternatively pre-process using envsubst

12) Health Checks

Collector
- Health extension enabled:
  - GET http://<collector-host>:13133/healthz (default health_check extension port if configured; if using default extension settings, port binding follows collector defaults)
- Metrics endpoint for collector export:
  - Scraped at 8889 by Prometheus

Application
- API health endpoints already provided by the application (e.g. /health, /api/v1/health)

Backends
- Verify Loki / Tempo / Remote write reachability and TLS using curl with CA trust or openssl s_client

13) Validation Steps (End-to-End)

1. Validate collector health:
   - curl -sS http://<collector-host>:13133/healthz
   - Expected: {"status":"Server available"}

2. Validate OTLP mTLS/TLS and BasicAuth (HTTP/4318):
   - curl -vk --cert otlp_client.crt --key otlp_client.key \
     --cacert otlp_client_ca.crt \
     -H "Authorization: Basic <base64(user:pass)>" \
     https://<collector-host>:4318/v1/metrics
   - Expected: HTTP 200 on POST with valid OTLP payload; GET will typically return 404/405 (not implemented), which still validates TLS and auth

3. Send a test trace/metric/log from a local script or using opentelemetry-instrument:
   - Run the API under opentelemetry-instrument (see above)
   - Issue some requests; check Tempo UI / Grafana Explore for traces
   - Confirm logs in Grafana Explore (Loki), with trace_id linking to Tempo
   - Confirm metrics in Prometheus; evaluate p95/error rules

4. Validate alerts:
   - Temporarily increase latency threshold to near-zero or generate 5xx to trigger alerts
   - Check Alertmanager UI for firing alerts and receiver notifications (Slack/PagerDuty/Email)

14) Operations and Runbooks

Certificate rotation
- Replace server cert/key mounts on collector; restart collector
- Update CA files for exporters as needed

Credential rotation
- Rotate OTLP htpasswd users; restart collector
- Rotate Loki/RemoteWrite credentials; restart collector

Scaling and performance
- Tune batch, memory_limiter, and tailsampling policies in collector configs
- Consider sharding collectors or deploying as DaemonSets/sidecars in Kubernetes

Retention
- Configure Loki retention in Loki’s own config (outside scope of collector)
- For metrics, use Prometheus remote write to long-term storage (Mimir, Cortex, Thanos, etc.)

15) Appendix: Minimal Environment Examples

Staging (example)
- ENVIRONMENT=staging
- OTLP_BASICAUTH_HTPASSWD=/etc/otel/otlp-htpasswd
- LOKI_ENDPOINT=https://loki.staging.example.com/loki/api/v1/push
- LOKI_USERNAME=staging_writer
- LOKI_PASSWORD=REDACTED
- LOKI_CA_FILE=/etc/ssl/certs/loki_ca.pem
- TEMPO_ENDPOINT=https://tempo.staging.example.com:4317
- TEMPO_BEARER_TOKEN=REDACTED
- TEMPO_CA_FILE=/etc/ssl/certs/tempo_ca.pem
- PROM_REMOTE_WRITE_URL=https://mimir.staging.example.com/api/v1/push
- PROM_REMOTE_WRITE_USERNAME=rw_user
- PROM_REMOTE_WRITE_PASSWORD=REDACTED
- PROM_REMOTE_WRITE_CA_FILE=/etc/ssl/certs/mimir_ca.pem
- PROMETHEUS_USERNAME=prom_user
- PROMETHEUS_PASSWORD=REDACTED
- SLACK_WEBHOOK_URL=https://hooks.slack.com/services/...
- SLACK_CHANNEL=#observability
- PAGERDUTY_ROUTING_KEY=REDACTED
- SMTP_SMARTHOST=smtp.staging.example.com:587
- SMTP_FROM=alerts@staging.example.com
- SMTP_USERNAME=alerts
- SMTP_PASSWORD=REDACTED
- ALERT_EMAIL_TO=observability@staging.example.com

Production (example)
- ENVIRONMENT=production
- All of the above set to production endpoints, credentials, and CAs
- Ensure firewall rules restrict OTLP ingest and Prometheus exposure appropriately
- Ensure BasicAuth htpasswd uses strong bcrypt hashes

Change Log
- Added secure OTLP endpoints with TLS and BasicAuth in [otel-collector-config.yaml](otel-collector-config.yaml)
- Added Loki, Tempo, Prometheus remote_write exporters with TLS and auth
- Added spanmetrics processor and hostmetrics receiver
- Created env-specific collectors:
  - [otel-collector.dev.yaml](config/observability/otel-collector.dev.yaml)
  - [otel-collector.staging.yaml](config/observability/otel-collector.staging.yaml)
  - [otel-collector.prod.yaml](config/observability/otel-collector.prod.yaml)
- Updated [prometheus.yml](prometheus.yml) to include [alerts.yml](config/prometheus/alerts.yml) and Alertmanager
- Created Alertmanager config [alertmanager.yml](config/alertmanager/alertmanager.yml) with Slack/PagerDuty/Email
- Provisioned Grafana datasources and dashboards:
  - [datasources.yaml](config/grafana/provisioning/datasources/datasources.yaml)
  - [dashboards.yaml](config/grafana/provisioning/dashboards/dashboards.yaml)
  - [FBA-Overview.json](config/grafana/provisioning/dashboards/fba/FBA-Overview.json)

This completes the production observability implementation according to the release readiness requirements.
