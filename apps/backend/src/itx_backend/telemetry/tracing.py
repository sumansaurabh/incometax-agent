import base64
import logging
from contextlib import contextmanager
from typing import Any

from itx_backend.config import settings

_otel_ready = False
_otel_trace = None
_trace_status: dict[str, Any] = {
    "enabled": False,
    "backend": "fallback",
    "exporter": "none",
    "endpoint": None,
}


logger = logging.getLogger("itx_backend")


def _parsed_headers(raw_headers: str) -> dict[str, str]:
    headers: dict[str, str] = {}
    for item in raw_headers.split(","):
        if "=" not in item:
            continue
        key, value = item.split("=", 1)
        key = key.strip()
        value = value.strip()
        if key:
            headers[key] = value
    return headers


def _langfuse_headers() -> dict[str, str]:
    if not settings.langfuse_public_key or not settings.langfuse_secret_key:
        return {}
    token = base64.b64encode(
        f"{settings.langfuse_public_key}:{settings.langfuse_secret_key}".encode("utf-8")
    ).decode("ascii")
    return {"Authorization": f"Basic {token}"}


def _resolve_exporter_config() -> tuple[str, str, dict[str, str]]:
    if settings.langfuse_enabled:
        endpoint = settings.langfuse_otlp_endpoint or settings.otel_exporter_otlp_endpoint
        headers = {**_parsed_headers(settings.otel_exporter_otlp_headers), **_langfuse_headers()}
        return "langfuse", endpoint, headers
    if settings.otel_exporter_otlp_endpoint:
        return "otlp", settings.otel_exporter_otlp_endpoint, _parsed_headers(settings.otel_exporter_otlp_headers)
    return "console", "", {}


def setup_tracing() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    global _otel_ready, _otel_trace, _trace_status
    if _otel_ready and _otel_trace is not None:
        return
    try:
        from opentelemetry import trace
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter

        resource = Resource.create(
            {
                "service.name": settings.otel_service_name,
                "deployment.environment": settings.environment,
                "itx.ai_provider": settings.ai_provider or "not_configured",
            }
        )
        provider = TracerProvider(resource=resource)
        backend, endpoint, headers = _resolve_exporter_config()
        exporter = ConsoleSpanExporter()
        exporter_name = "console"
        if endpoint:
            try:
                from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

                exporter = OTLPSpanExporter(
                    endpoint=endpoint,
                    headers=headers or None,
                )
                exporter_name = backend
            except Exception as exc:  # pragma: no cover - optional dependency path
                exporter_name = f"console_fallback:{exc.__class__.__name__}"
        processor = BatchSpanProcessor(exporter)
        provider.add_span_processor(processor)
        trace.set_tracer_provider(provider)

        _otel_trace = trace
        _otel_ready = True
        _trace_status = {
            "enabled": True,
            "backend": backend,
            "exporter": exporter_name,
            "endpoint": endpoint or None,
            "langfuse_enabled": settings.langfuse_enabled,
            "ai_provider": settings.ai_provider or "not_configured",
            "service_name": settings.otel_service_name,
        }
        logger.info("Tracing initialized (%s)", exporter_name)
    except Exception as exc:
        _otel_ready = False
        _otel_trace = None
        _trace_status = {
            "enabled": False,
            "backend": "fallback",
            "exporter": "none",
            "endpoint": None,
            "error": exc.__class__.__name__,
        }
        logger.info("Tracing initialized (fallback)")


class SimpleSpan:
    def __init__(self, name: str) -> None:
        self.name = name
        self.attributes: dict[str, object] = {}

    def set_attribute(self, key: str, value: object) -> None:
        self.attributes[key] = value


class SimpleTracer:
    def __init__(self, name: str) -> None:
        self.name = name

    @contextmanager
    def start_as_current_span(self, span_name: str):
        span = SimpleSpan(span_name)
        yield span


def get_tracer(name: str) -> SimpleTracer:
    if _otel_ready and _otel_trace is not None:
        return _otel_trace.get_tracer(name)
    return SimpleTracer(name)


def get_trace_status() -> dict[str, Any]:
    return dict(_trace_status)
