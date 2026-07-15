#!/usr/bin/env python
"""Test webhook payload parsing directly."""
import sys
sys.path.insert(0, "C:\\Users\\LAVANYA\\whatapp_emovur")

from app.services.webhook_service import parse_whatsapp_webhook_payload

payload = {
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

print("Parsing webhook payload...")
print(f"Input payload: {payload}")

try:
    events = parse_whatsapp_webhook_payload(payload)
    print(f"\nParsed events: {events}")
    print(f"Event count: {len(events)}")
    if events:
        for i, ev in enumerate(events):
            print(f"\nEvent {i}:")
            for k, v in ev.items():
                print(f"  {k}: {v}")
except Exception as e:
    import traceback
    print(f"Error: {e}")
    traceback.print_exc()
