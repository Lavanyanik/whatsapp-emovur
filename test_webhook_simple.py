#!/usr/bin/env python
"""Simple webhook test to verify button click processing."""
import httpx
import json

print("Testing webhook button click...")

webhook_payload = {
    "entry": [
        {
            "id": "123",
            "changes": [
                {
                    "value": {
                        "messages": [
                            {
                                "from": "919999888877",
                                "id": "msg_test_001",
                                "type": "interactive",
                                "timestamp": "1626261319",
                                "interactive": {
                                    "button_reply": {
                                        "id": "interested",
                                        "title": "Interested"
                                    },
                                    "type": "button_reply"
                                }
                            }
                        ]
                    }
                }
            ]
        }
    ],
    "object": "whatsapp_business_account"
}

print("Payload:")
print(json.dumps(webhook_payload, indent=2))

try:
    r = httpx.post('http://localhost:8000/webhook', json=webhook_payload, timeout=5)
    print(f"\nStatus: {r.status_code}")
    print(f"Response: {r.json()}")
except Exception as e:
    print(f"Error: {e}")
