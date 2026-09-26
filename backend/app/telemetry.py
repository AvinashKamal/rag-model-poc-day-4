from opentelemetry import metrics, trace
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from app.config import settings

_resource = Resource.create({"service.name": "backend"})

_provider = TracerProvider(resource=_resource)
_provider.add_span_processor(
    BatchSpanProcessor(OTLPSpanExporter(endpoint=settings.OTEL_EXPORTER_OTLP_ENDPOINT))
)
trace.set_tracer_provider(_provider)

tracer = trace.get_tracer("backend")

# --- Metrics ---------------------------------------------------------------
#
# NOTE on semantic-convention stability (see rag-app.json vs. the installed
# opentelemetry-instrumentation-fastapi==0.65b0 behavior, checked directly
# against the library source at
# .../opentelemetry/instrumentation/asgi/__init__.py):
#
# `infra/grafana/dashboards/rag-app.json` queries
# `http_server_duration_milliseconds_bucket` — i.e. the OLD HTTP semantic
# convention (`http.server.duration`, unit `ms`, a Histogram -> Prometheus
# `_bucket` suffix).
#
# FastAPIInstrumentor/ASGI's instrumentation decides which convention(s) to
# emit based on the `OTEL_SEMCONV_STABILITY_OPT_IN` env var:
#   - unset / "default"      -> OLD only: `http.server.duration` (ms)
#   - "http"                 -> NEW only: `http.server.request.duration` (s)
#   - "http/dup"             -> BOTH
# We deliberately do NOT set `OTEL_SEMCONV_STABILITY_OPT_IN` anywhere (it's
# absent from `Settings` and from the environment), so the instrumentation
# runs in its default mode and emits exactly the OLD `http.server.duration`
# (ms) histogram the dashboard already expects — no reconciliation needed.
# If this env var is ever introduced (e.g. to pick up other new-convention
# metrics), it must be set to "http/dup" rather than "http", or the dashboard
# will silently go empty.
_metric_exporter = OTLPMetricExporter(endpoint=settings.OTEL_EXPORTER_OTLP_ENDPOINT)
_metric_reader = PeriodicExportingMetricReader(
    _metric_exporter, export_interval_millis=5000
)
meter_provider = MeterProvider(resource=_resource, metric_readers=[_metric_reader])
metrics.set_meter_provider(meter_provider)

meter = metrics.get_meter("backend")

# Per-query retrieval hit-rate signal: 1.0 when a query clears the abstention
# gate (evidence found), 0.0 when it abstains. A Histogram recording 0/1 per
# call is used rather than an ObservableGauge: this is a per-call event, not
# a value sampled from current process state at collection time (which is
# what ObservableGauge callbacks are for), and a Histogram gives us the mean
# (= hit rate) plus distribution/count for free via the same instrument.
rag_retrieval_hit_rate = meter.create_histogram(
    name="rag_retrieval_hit_rate",
    description="1.0 per query that clears the abstention gate, 0.0 per query that abstains.",
    unit="1",
)

rag_llm_tokens_total = meter.create_counter(
    name="rag_llm_tokens_total",
    description="Total LLM tokens consumed via OpenRouter, by token_type (prompt|completion).",
    unit="1",
)

# Ingestion run outcomes/latency, by domain and status (success|failure).
# A Counter + Histogram pair (same reasoning as the pair above): the count
# comes for free from the histogram too, but a dedicated Counter makes
# "runs by status" a trivial `sum by (status)` in Grafana without having to
# reach for `_count` on the histogram series.
rag_ingestion_runs_total = meter.create_counter(
    name="rag_ingestion_runs_total",
    description="Total ingestion runs, by domain and status (success|failure).",
    unit="1",
)

rag_ingestion_duration_seconds = meter.create_histogram(
    name="rag_ingestion_duration_seconds",
    description="Ingestion run wall-clock duration in seconds, by domain and status.",
    unit="s",
)


def setup_telemetry(app):
    FastAPIInstrumentor.instrument_app(app, meter_provider=meter_provider)
