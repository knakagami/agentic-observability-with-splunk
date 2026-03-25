"""
Load Generator — runs as a separate Pod.
Sends continuous order requests to order-service.
60% of requests use integer amounts (triggers bug in v1.1).
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
REQUEST_INTERVAL = float(os.getenv("REQUEST_INTERVAL_SECONDS", "2"))

ITEMS = ["widget", "gadget", "doohickey", "thingamajig", "whatsit"]


def make_amount() -> float:
    """60% integer amount (whole number), 40% decimal amount."""
    if random.random() < 0.6:
        return float(random.randint(10, 500))   # integer → triggers ZeroDivisionError in v1.1
    else:
        return round(random.uniform(10.5, 499.9), 2)


def main():
    logger.info("Load generator starting", extra={"target": ORDER_SERVICE_URL})
    time.sleep(10)  # wait for services to be ready

    while True:
        order_id = str(uuid.uuid4())[:8]
        amount = make_amount()
        item = random.choice(ITEMS)
        payload = {"order_id": order_id, "item": item, "amount": amount}

        try:
            resp = httpx.post(f"{ORDER_SERVICE_URL}/order", json=payload, timeout=10.0)
            logger.info("Request sent", extra={
                "order_id": order_id,
                "amount": amount,
                "is_integer": amount == int(amount),
                "status_code": resp.status_code,
            })
        except Exception as exc:
            logger.error("Request failed", extra={"order_id": order_id, "error": str(exc)})

        time.sleep(REQUEST_INTERVAL)


if __name__ == "__main__":
    main()
