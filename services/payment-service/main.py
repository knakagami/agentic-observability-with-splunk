"""
payment-service v1.0 — 正常版 (no bugs)

v1.1 bug: decimal_part = payment.amount - int(payment.amount)
          discount_rate = payment.amount / decimal_part  ← ZeroDivisionError when whole number

v1.2 fix: guard against decimal_part == 0 before division
"""
import logging
import os

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from pythonjsonlogger import jsonlogger

# ── OTel setup ────────────────────────────────────────────────────────────────
SERVICE_VERSION = os.getenv("SERVICE_VERSION", "1.0")
resource = Resource.create({
    "service.name": "payment-service",
    "service.version": SERVICE_VERSION,
    "deployment.environment": "demo",
    "service.namespace": "agentic-o11y-mcp",
})
provider = TracerProvider(resource=resource)
otlp_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://otel-collector:4317")
provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=otlp_endpoint)))
trace.set_tracer_provider(provider)
tracer = trace.get_tracer("payment-service")

# ── Structured JSON logging with trace_id ─────────────────────────────────────
class TraceIdFilter(logging.Filter):
    def filter(self, record):
        span = trace.get_current_span()
        ctx = span.get_span_context()
        record.trace_id = format(ctx.trace_id, "032x") if ctx.is_valid else ""
        record.span_id = format(ctx.span_id, "016x") if ctx.is_valid else ""
        return True

handler = logging.StreamHandler()
formatter = jsonlogger.JsonFormatter(
    fmt="%(asctime)s %(levelname)s %(name)s %(message)s %(trace_id)s %(span_id)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
handler.setFormatter(formatter)
handler.addFilter(TraceIdFilter())
logging.root.handlers = [handler]
logging.root.setLevel(logging.INFO)
logger = logging.getLogger("payment-service")

# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(title="payment-service")
FastAPIInstrumentor.instrument_app(app)


class PaymentRequest(BaseModel):
    payment_id: str
    amount: float


class PaymentResponse(BaseModel):
    payment_id: str
    status: str
    charged: float


@app.get("/health")
def health():
    return {"status": "ok", "service": "payment-service", "version": SERVICE_VERSION}


@app.post("/pay", response_model=PaymentResponse)
def process_payment(payment: PaymentRequest):
    with tracer.start_as_current_span("process_payment") as span:
        span.set_attribute("payment.id", payment.payment_id)
        span.set_attribute("payment.amount", payment.amount)

        logger.info("Processing payment", extra={
            "payment_id": payment.payment_id,
            "amount": payment.amount,
        })

        # ── v1.0: normal processing ───────────────────────────────────────────
        # Apply a small fixed fee
        fee = round(payment.amount * 0.03, 2)
        total = round(payment.amount + fee, 2)

        span.set_attribute("payment.fee", fee)
        span.set_attribute("payment.total", total)

        logger.info("Payment processed", extra={
            "payment_id": payment.payment_id,
            "amount": payment.amount,
            "fee": fee,
            "total": total,
        })

        return PaymentResponse(payment_id=payment.payment_id, status="success", charged=total)
