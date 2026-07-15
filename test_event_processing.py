#!/usr/bin/env python
"""Test complete webhook event processing."""
import sys
import asyncio
import sqlite3
sys.path.insert(0, "C:\\Users\\LAVANYA\\whatapp_emovur")

from app.database import AsyncSessionLocal
from app.services.webhook_service import process_event

async def test_event_processing():
    # First insert a test candidate
    db_path = "C:\\Users\\LAVANYA\\whatapp_emovur\\whatsapp_emovur.db"
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Check if candidate exists
    cursor.execute("SELECT * FROM candidates WHERE phone = ?", ("+919999888877",))
    row = cursor.fetchone()
    if row:
        print(f"Found candidate: {row}")
    else:
        print("No candidate found, inserting...")
        cursor.execute("""
            INSERT INTO candidates (candidate_name, phone, role, company, status)
            VALUES (?, ?, ?, ?, ?)
        """, ("Test User", "+919999888877", "Engineer", "TechCorp", "pending"))
        conn.commit()
    
    conn.close()
    
    # Now test webhook processing
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
    
    print(f"\nProcessing webhook event...")
    async with AsyncSessionLocal() as db:
        try:
            result = await process_event(payload=payload, db=db)
            print(f"Result: {result}")
        except Exception as e:
            import traceback
            print(f"Error: {e}")
            traceback.print_exc()
    
    # Check if candidate was updated
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM candidates WHERE phone = ?", ("+919999888877",))
    row = cursor.fetchone()
    if row:
        print(f"\nCandidate after processing:")
        for key in row.keys():
            print(f"  {key}: {row[key]}")
    conn.close()

asyncio.run(test_event_processing())
