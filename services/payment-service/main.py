"""
payment-service v1.2
"""
import logging

from fastapi import FastAPI
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

# Discount rate table keyed by decimal tier (0–9).
# 0: integer amount (no decimal part), 1–9: fractional amounts.
DISCOUNT_RATES = {
    0: 0.0,
    1: 0.01, 2: 0.02, 3: 0.03, 4: 0.04, 5: 0.05,
    6: 0.06, 7: 0.07, 8: 0.08, 9: 0.09,
}


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

        logger.info("Processing payment", extra={
            "payment_id": payment.payment_id,
            "amount": payment.amount,
        })

        decimal_part = payment.amount - int(payment.amount)
        tier_key = round(decimal_part * 10)
        discount_rate = DISCOUNT_RATES[tier_key]

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
