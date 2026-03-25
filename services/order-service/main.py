import logging
import os
import json
import time

import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from pythonjsonlogger import jsonlogger

# ── OTel setup ────────────────────────────────────────────────────────────────
SERVICE_VERSION = os.getenv("SERVICE_VERSION", "1.0")
resource = Resource.create({
    "service.name": "order-service",
    "service.version": SERVICE_VERSION,
    "deployment.environment": "demo",
    "service.namespace": "agentic-o11y-mcp",
})
provider = TracerProvider(resource=resource)
otlp_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://otel-collector:4317")
provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=otlp_endpoint)))
trace.set_tracer_provider(provider)
tracer = trace.get_tracer("order-service")

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
logger = logging.getLogger("order-service")

# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(title="order-service")
FastAPIInstrumentor.instrument_app(app)
HTTPXClientInstrumentor().instrument()

PAYMENT_SERVICE_URL = os.getenv("PAYMENT_SERVICE_URL", "http://payment-service:8001")


class OrderRequest(BaseModel):
    order_id: str
    item: str
    amount: float


class OrderResponse(BaseModel):
    order_id: str
    status: str
    payment_result: dict


@app.get("/health")
def health():
    return {"status": "ok", "service": "order-service"}


@app.post("/order", response_model=OrderResponse)
async def create_order(req: OrderRequest):
    with tracer.start_as_current_span("create_order") as span:
        span.set_attribute("order.id", req.order_id)
        span.set_attribute("order.item", req.item)
        span.set_attribute("order.amount", req.amount)

        logger.info("Order received", extra={
            "order_id": req.order_id,
            "item": req.item,
            "amount": req.amount,
        })

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(
                    f"{PAYMENT_SERVICE_URL}/pay",
                    json={"payment_id": req.order_id, "amount": req.amount},
                )
            resp.raise_for_status()
            result = resp.json()
            logger.info("Order completed", extra={
                "order_id": req.order_id,
                "payment_status": result.get("status"),
            })
            return OrderResponse(order_id=req.order_id, status="completed", payment_result=result)
        except httpx.HTTPStatusError as exc:
            span.set_attribute("error", True)
            span.record_exception(exc)
            logger.error("Payment failed", extra={
                "order_id": req.order_id,
                "http_status": exc.response.status_code,
                "response_body": exc.response.text,
            })
            raise HTTPException(status_code=502, detail=f"Payment service error: {exc.response.text}")
        except Exception as exc:
            span.set_attribute("error", True)
            span.record_exception(exc)
            logger.error("Unexpected error", extra={"order_id": req.order_id, "error": str(exc)})
            raise HTTPException(status_code=500, detail="Internal server error")
