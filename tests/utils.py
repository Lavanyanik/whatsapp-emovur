from __future__ import annotations

import hashlib
import hmac
from typing import Any, Dict


def compute_signature(secret: str, body_bytes: bytes) -> str:
    digest = hmac.new(secret.encode("utf-8"), body_bytes, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


def make_webhook_payload_interactive_button_reply(*, phone_wa_id: str, message_id: str, button_id: str, button_title: str, ts: str = "1626261319") -> Dict[str, Any]:
    return {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "123",
                "changes": [
                    {
                        "value": {
                            "messages": [
                                {
                                    "from": phone_wa_id,
                                    "id": message_id,
                                    "type": "interactive",
                                    "timestamp": ts,
                                    "interactive": {
                                        "button_reply": {
                                            "id": button_id,
                                            "title": button_title,
                                        },
                                        "type": "button_reply",
                                    },
                                }
                            ]
                        },
                        "field": "messages",
                    }
                ],
            }
        ],
    }

