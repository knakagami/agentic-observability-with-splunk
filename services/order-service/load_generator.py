"""
Load Generator — runs as a separate Pod.
Sends continuous order requests to order-service.
60% of requests use integer amounts (triggers bug in v1.1).

Env:
  ORDER_SERVICE_URL — default http://order-service:8000
  REQUEST_INTERVAL_SECONDS — pause between requests (default 0.5; lower = more RPS)
  LOADGEN_MAX_RETRIES — POST retries for transient network errors (default 3)
"""
import os
import random
import time
import uuid
import logging
import httpx
from pythonjsonlogger import jsonlogger

handler = logging.StreamHandler()
formatter = jsonlogger.JsonFormatter(
    fmt="%(asctime)s %(levelname)s %(name)s %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
handler.setFormatter(formatter)
logging.root.handlers = [handler]
logging.root.setLevel(logging.INFO)
logger = logging.getLogger("load-generator")

ORDER_SERVICE_URL = os.getenv("ORDER_SERVICE_URL", "http://order-service:8000")
REQUEST_INTERVAL = float(os.getenv("REQUEST_INTERVAL_SECONDS", "0.5"))
MAX_RETRIES = int(os.getenv("LOADGEN_MAX_RETRIES", "3"))

ITEMS = ["widget", "gadget", "doohickey", "thingamajig", "whatsit"]

_TRANSIENT = (httpx.ConnectError, httpx.ReadTimeout, httpx.ConnectTimeout, httpx.WriteTimeout)


def wait_for_order_health() -> None:
    """Poll order-service /health before main loop to reduce cold-start noise."""
    base = ORDER_SERVICE_URL.rstrip("/")
    health_url = f"{base}/health"
    deadline = time.time() + 120
    while time.time() < deadline:
        try:
            resp = httpx.get(health_url, timeout=3.0)
            if resp.status_code == 200:
                logger.info("order-service health ok", extra={"url": health_url})
                return
        except Exception:
            pass
        time.sleep(2)
    logger.warning(
        "order-service health not ready after wait; continuing",
        extra={"url": health_url},
    )


def post_order(payload: dict) -> tuple[httpx.Response | None, Exception | None, int]:
    """
    POST /order with retries on transient httpx errors.
    Returns (response, error, attempt_count).
    """
    url = f"{ORDER_SERVICE_URL.rstrip('/')}/order"
    last_err: Exception | None = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = httpx.post(url, json=payload, timeout=10.0)
            return resp, None, attempt
        except _TRANSIENT as exc:
            last_err = exc
            if attempt < MAX_RETRIES:
                time.sleep(0.3 * attempt)
        except Exception as exc:
            return None, exc, attempt
    return None, last_err, MAX_RETRIES


def make_amount() -> float:
    """60% integer amount (whole number), 40% decimal amount."""
    if random.random() < 0.6:
        return float(random.randint(10, 500))  # integer → KeyError: 0 in v1.1 payment-service
    return round(random.uniform(10.5, 499.9), 2)


def main():
    logger.info(
        "Load generator starting",
        extra={
            "target": ORDER_SERVICE_URL,
            "request_interval_seconds": REQUEST_INTERVAL,
            "max_retries": MAX_RETRIES,
        },
    )
    time.sleep(5)
    wait_for_order_health()

    while True:
        order_id = str(uuid.uuid4())[:8]
        amount = make_amount()
        item = random.choice(ITEMS)
        payload = {"order_id": order_id, "item": item, "amount": amount}

        resp, err, attempts = post_order(payload)
        if err is None and resp is not None:
            logger.info(
                "Request sent",
                extra={
                    "order_id": order_id,
                    "amount": amount,
                    "is_integer": amount == int(amount),
                    "status_code": resp.status_code,
                    "retry_count": attempts - 1,
                },
            )
        else:
            exc = err or RuntimeError("unknown")
            logger.error(
                "Request failed",
                extra={
                    "order_id": order_id,
                    "error": str(exc),
                    "error_class": type(exc).__name__,
                    "retry_count": attempts - 1,
                },
            )

        time.sleep(REQUEST_INTERVAL)


if __name__ == "__main__":
    main()
