import logging
from contextlib import contextmanager

_otel_ready = False
_otel_trace = None


logger = logging.getLogger("itx_backend")


def setup_tracing() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    global _otel_ready, _otel_trace
    try:
        from opentelemetry import trace
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter

        resource = Resource.create({"service.name": "itx-backend"})
        provider = TracerProvider(resource=resource)
        processor = BatchSpanProcessor(ConsoleSpanExporter())
        provider.add_span_processor(processor)
        trace.set_tracer_provider(provider)

        _otel_trace = trace
        _otel_ready = True
        logger.info("Tracing initialized (OpenTelemetry)")
    except Exception:
        _otel_ready = False
        _otel_trace = None
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
