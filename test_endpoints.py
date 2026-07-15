#!/usr/bin/env python
"""Quick endpoint tests."""
import httpx
import json

print("=" * 80)
print("Testing /health")
print("=" * 80)
r = httpx.get('http://localhost:8000/health', timeout=5)
print(f"Status: {r.status_code}")
print(json.dumps(r.json(), indent=2))

print("\n" + "=" * 80)
print("Testing GET /webhook")
print("=" * 80)
r = httpx.get('http://localhost:8000/webhook?hub.mode=subscribe&hub.challenge=test123&hub.verify_token=test_token', timeout=5)
print(f"Status: {r.status_code}")
print(f"Body: {r.text}")

print("\n" + "=" * 80)
print("Testing /templates")
print("=" * 80)
r = httpx.get('http://localhost:8000/templates', timeout=10)
print(f"Status: {r.status_code}")
templates = r.json()
print(f"Templates found: {len(templates)}")
for t in templates:
    print(f"  - {t['name']} ({t['language']}) - {t['status']}")

print("\n" + "=" * 80)
print("Testing POST /messages with template")
print("=" * 80)
payload = {
    "type": "template",
    "to": "+919999999996",
    "template_name": "candidate_screening_invitation",
    "language": "en",
    "components": [
        {
            "type": "body",
            "parameters": [
                {"type": "text", "text": "TestCandidate"},
                {"type": "text", "text": "Engineer"},
                {"type": "text", "text": "TechCorp"},
                {"type": "text", "text": "HRTeam"}
            ]
        }
    ]
}
r = httpx.post('http://localhost:8000/messages', json=payload, timeout=15)
print(f"Status: {r.status_code}")
print(json.dumps(r.json(), indent=2))

print("\n" + "=" * 80)
print("Testing POST /messages with text")
print("=" * 80)
payload = {
    "type": "text",
    "to": "+919999999996",
    "text": "Hello from WhatsApp Backend!"
}
r = httpx.post('http://localhost:8000/messages', json=payload, timeout=15)
print(f"Status: {r.status_code}")
print(json.dumps(r.json(), indent=2))

print("\n" + "=" * 80)
print("Testing POST /webhook with button click")
print("=" * 80)
webhook_payload = {
    "entry": [
        {
            "id": "123",
            "changes": [
                {
                    "value": {
                        "messages": [
                            {
                                "from": "919999999996",
                                "id": "msg123",
                                "interactive": {
                                    "button_reply": {
                                        "id": "interested",
                                        "title": "Interested"
                                    },
                                    "type": "button_reply"
                                },
                                "type": "interactive"
                            }
                        ]
                    }
                }
            ]
        }
    ],
    "object": "whatsapp_business_account"
}
r = httpx.post('http://localhost:8000/webhook', json=webhook_payload, timeout=5)
print(f"Status: {r.status_code}")
print(f"Body: {r.text}")

print("\n" + "=" * 80)
print("PASS: All endpoint tests completed")
print("=" * 80)
