#!/usr/bin/env python3
"""
Create a Splunk Observability Cloud detector for high payment-service error rate.

Usage:
  export SPLUNK_O11Y_TOKEN=<your-token>
  python create_detector.py

Requires: requests
  pip install requests
"""
import json
import os
import sys

import requests

REALM = os.getenv("SPLUNK_O11Y_REALM", "jp0")
TOKEN = os.environ["SPLUNK_O11Y_TOKEN"]
API_BASE = f"https://api.{REALM}.signalfx.com"


def create_detector():
    detector = {
        "name": "Demo: Payment Service High Error Rate",
        "description": (
            "Fires when the payment-service HTTP 5xx error rate exceeds 40% "
            "over a 1-minute window. Used in the Splunk MCP agentic demo."
        ),
        "rules": [
            {
                "name": "Error rate critical",
                "severity": "Critical",
                "detectLabel": "payment_error_rate_critical",
                "notifications": [],
                "parameterizedBody": (
                    "Payment service error rate is {{inputs.error_rate.value | round(1)}}% "
                    "(threshold: 40%). Deploy: {{event.properties.description}}"
                ),
            }
        ],
        "programOptions": {
            "minimumResolution": 60000,
            "disableSampling": False,
        },
        "programV2": """
detector('Demo: Payment Service High Error Rate') {
    var errors = data(
        'service.request.count',
        filter=filter('service.name', 'payment-service')
            and filter('deployment.environment', 'demo')
            and filter('http.status_class', '5xx'),
        rollup='sum'
    ).sum(over='1m')

    var total = data(
        'service.request.count',
        filter=filter('service.name', 'payment-service')
            and filter('deployment.environment', 'demo'),
        rollup='sum'
    ).sum(over='1m')

    var error_rate = (errors / total * 100).publish(label='error_rate')

    detect(when(error_rate > 40)).publish('payment_error_rate_critical')
}
""",
        "tags": ["demo", "payment-service", "agentic-o11y-mcp"],
        "visualizationOptions": {
            "disableSampling": False,
            "showDataMarkers": True,
        },
    }

    resp = requests.post(
        f"{API_BASE}/v2/detector",
        headers={
            "Content-Type": "application/json",
            "X-SF-Token": TOKEN,
        },
        data=json.dumps(detector),
        timeout=30,
    )

    if resp.status_code == 200:
        result = resp.json()
        print(f"Detector created: {result['id']}")
        print(f"  Name: {result['name']}")
        print(f"  URL:  https://app.{REALM}.signalfx.com/#/detector/{result['id']}/edit")
    else:
        print(f"ERROR {resp.status_code}: {resp.text}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    create_detector()
