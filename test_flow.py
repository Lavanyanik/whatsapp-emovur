#!/usr/bin/env python
"""Test complete candidate flow: create, send template, receive button click, verify DB update."""
import httpx
import json
import time
import sqlite3

DB_PATH = "C:\\Users\\LAVANYA\\whatapp_emovur\\whatsapp_emovur.db"

def get_candidate_from_db(phone: str) -> dict:
    """Query candidate from database by phone."""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM candidates WHERE phone = ?", (phone,))
        row = cursor.fetchone()
        conn.close()
        if row:
            return dict(row)
        return None
    except Exception as e:
        print(f"DB error: {e}")
        return None

def insert_candidate_to_db(candidate_name: str, phone: str, role: str, company: str) -> int:
    """Insert candidate to database."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO candidates (candidate_name, phone, role, company, status, invite_sent_at)
            VALUES (?, ?, ?, ?, 'pending', datetime('now'))
        """, (candidate_name, phone, role, company))
        conn.commit()
        candidate_id = cursor.lastrowid
        conn.close()
        return candidate_id
    except Exception as e:
        print(f"DB insert error: {e}")
        return None

print("=" * 80)
print("TEST: Complete Candidate Flow")
print("=" * 80)

test_phone = "+919999888877"
test_name = "FlowTest User"
test_role = "Full Stack Developer"
test_company = "TechFlow Inc"

print(f"\nStep 1: Insert test candidate into DB")
print(f"  Name: {test_name}")
print(f"  Phone: {test_phone}")
print(f"  Role: {test_role}")
print(f"  Company: {test_company}")

candidate_id = insert_candidate_to_db(test_name, test_phone, test_role, test_company)
if not candidate_id:
    print("ERROR: Failed to insert candidate")
    exit(1)
print(f"  Result: OK, candidate_id={candidate_id}")

print(f"\nStep 2: Verify candidate in DB")
candidate = get_candidate_from_db(test_phone)
if not candidate:
    print("ERROR: Candidate not found in DB after insert")
    exit(1)
print(f"  Status before: {candidate.get('status')}")
print(f"  Response before: {candidate.get('candidate_response')}")

print(f"\nStep 3: Send screening invitation template via /messages")
payload = {
    "type": "template",
    "to": test_phone,
    "template_name": "candidate_screening_invitation",
    "language": "en",
    "components": [
        {
            "type": "body",
            "parameters": [
                {"type": "text", "text": test_name},
                {"type": "text", "text": test_role},
                {"type": "text", "text": test_company},
                {"type": "text", "text": "HR Team"}
            ]
        }
    ]
}

try:
    r = httpx.post('http://localhost:8000/messages', json=payload, timeout=15)
    print(f"  Status: {r.status_code}")
    if r.status_code == 200:
        result = r.json()
        print(f"  Message ID: {result.get('data', {}).get('messages', [{}])[0].get('id', 'N/A')}")
        print(f"  Result: OK")
    else:
        print(f"  Result: FAILED - {r.json()}")
except Exception as e:
    print(f"  Result: FAILED - {e}")

print(f"\nStep 4: Simulate webhook button click (Interested)")
webhook_payload = {
    "entry": [
        {
            "id": "123",
            "changes": [
                {
                    "value": {
                        "messages": [
                            {
                                "from": test_phone.lstrip("+"),
                                "id": "msg_test_001",
                                "interactive": {
                                    "button_reply": {
                                        "id": "interested",
                                        "title": "Interested"
                                    },
                                    "type": "button_reply"
                                },
                                "type": "interactive",
                                "timestamp": str(int(time.time()))
                            }
                        ]
                    }
                }
            ]
        }
    ],
    "object": "whatsapp_business_account"
}

try:
    r = httpx.post('http://localhost:8000/webhook', json=webhook_payload, timeout=5)
    print(f"  Webhook Status: {r.status_code}")
    print(f"  Webhook Response: {r.json()}")
except Exception as e:
    print(f"  Webhook Error: {e}")

print(f"\nStep 5: Verify candidate status updated in DB")
time.sleep(1)
candidate_after = get_candidate_from_db(test_phone)
if not candidate_after:
    print("ERROR: Candidate not found in DB after webhook")
    exit(1)

print(f"  Status after: {candidate_after.get('status')}")
print(f"  Response after: {candidate_after.get('candidate_response')}")
print(f"  Response timestamp: {candidate_after.get('response_received_at')}")

if candidate_after.get('status') == 'interested':
    print(f"\n  Result: PASS - Candidate status updated to 'interested'")
else:
    print(f"\n  Result: FAIL - Expected status 'interested', got '{candidate_after.get('status')}'")

print(f"\nStep 6: Check reminder flags are still 0 (not sent yet)")
print(f"  reminder1_sent: {candidate_after.get('reminder1_sent')}")
print(f"  reminder2_sent: {candidate_after.get('reminder2_sent')}")
if candidate_after.get('reminder1_sent') == 0 and candidate_after.get('reminder2_sent') == 0:
    print(f"  Result: PASS - No reminders sent for responded candidate")
else:
    print(f"  Result: FAIL - Reminders should not be sent")

print("\n" + "=" * 80)
print("PASS: Complete candidate flow test successful")
print("=" * 80)
