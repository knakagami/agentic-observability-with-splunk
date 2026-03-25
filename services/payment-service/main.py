"""
payment-service v1.1 — BUG VERSION
Deploy this on the feature/v1.1-payment-bug branch.

Bug: ZeroDivisionError when payment.amount is a whole number (e.g. 100, 200).
     decimal_part = 0  →  payment.amount / decimal_part  →  ZeroDivisionError

Load generator sends 60% integer amounts → ~60% error rate after deploy.
"""
import logging

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from opentelemetry import trace
from pythonjsonlogger import jsonlogger

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


class PaymentRequest(BaseModel):
    payment_id: str
    amount: float


class PaymentResponse(BaseModel):
    payment_id: str
    status: str
    charged: float


@app.get("/health")
def health():
    return {"status": "ok", "service": "payment-service"}


@app.post("/pay", response_model=PaymentResponse)
def process_payment(payment: PaymentRequest):
    with tracer.start_as_current_span("process_payment") as span:
        span.set_attribute("payment.id", payment.payment_id)
        span.set_attribute("payment.amount", payment.amount)

        logger.info("Processing payment", extra={
            "payment_id": payment.payment_id,
            "amount": payment.amount,
        })

        # ── v1.1 BUG: ZeroDivisionError for whole-number amounts ─────────────
        # Intended: compute a "decimal discount" for amounts with cents.
        # Bug: when amount is a whole number, decimal_part == 0 → division by zero.
        decimal_part = payment.amount - int(payment.amount)
        discount_rate = payment.amount / decimal_part  # BUG: ZeroDivisionError when decimal_part == 0

        fee = round(payment.amount * 0.03, 2)
        total = round(payment.amount + fee - discount_rate, 2)

        span.set_attribute("payment.fee", fee)
        span.set_attribute("payment.total", total)

        logger.info("Payment processed", extra={
            "payment_id": payment.payment_id,
            "amount": payment.amount,
            "fee": fee,
            "total": total,
        })

        return PaymentResponse(payment_id=payment.payment_id, status="success", charged=total)
