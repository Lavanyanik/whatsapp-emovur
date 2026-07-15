#!/usr/bin/env python
"""Test if POST /webhook route exists and responds."""
import httpx
import json

print("Testing POST /webhook route...")

payload = {
    "test": "data"
}

try:
    r = httpx.post('http://localhost:8000/webhook', json=payload, timeout=5)
    print(f"Status: {r.status_code}")
    print(f"Response: {r.text[:200]}")
except Exception as e:
    print(f"Error: {e}")

print("\nTesting GET /webhook...")
try:
    r = httpx.get('http://localhost:8000/webhook?hub.mode=subscribe&hub.challenge=test123&hub.verify_token=suprhire_webhook_verify_token', timeout=5)
    print(f"Status: {r.status_code}")
    print(f"Response: {r.text[:200]}")
except Exception as e:
    print(f"Error: {e}")
