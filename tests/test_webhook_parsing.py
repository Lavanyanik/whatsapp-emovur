from __future__ import annotations

from app.services.webhook_service import parse_whatsapp_webhook_payload


def test_parse_interactive_button_reply():
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
                                            "title": "Interested",
                                        },
                                        "type": "button_reply",
                                    },
                                }
                            ]
                        }
                    }
                ],
            }
        ],
        "object": "whatsapp_business_account",
    }

    events = parse_whatsapp_webhook_payload(payload)
    assert len(events) == 1
    ev = events[0]
    assert ev["phone"]
    assert ev["phone"].endswith("919999888877"[-10:])
    assert ev["message_id"] == "msg_test_001"
    assert ev["message_type"] == "interactive"
    assert ev["button_id"] == "interested"
    assert ev["button_title"] == "Interested"
    assert ev["button_payload"] == "interested"

