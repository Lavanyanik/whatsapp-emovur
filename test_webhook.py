import requests
import json

# Test payload simulating WhatsApp Cloud API interactive button click
test_payload = {
    "object": "whatsapp_business_account",
    "entry": [
        {
            "id": "123456789",
            "changes": [
                {
                    "value": {
                        "messaging_product": "whatsapp",
                        "metadata": {
                            "display_phone_number": "+1234567890",
                            "phone_number_id": "123456789"
                        },
                        "contacts": [
                            {
                                "profile": {
                                    "name": "Test User"
                                },
                                "wa_id": "919876543210"
                            }
                        ],
                        "messages": [
                            {
                                "from": "919876543210",
                                "id": "wamid.HBgLNzk4NzY1NDMyMTAFQTIyRjI2M0U4QTlFQ0ZCMThBNDQ=",
                                "timestamp": "1720939200",
                                "type": "interactive",
                                "interactive": {
                                    "type": "button_reply",
                                    "button_reply": {
                                        "id": "interested",
                                        "title": "Interested"
                                    }
                                }
                            }
                        ]
                    },
                    "field": "messages"
                }
            ]
        }
    ]
}

print("Sending test POST request to webhook...")
print(f"Payload: {json.dumps(test_payload, indent=2)}")

response = requests.post(
    "http://127.0.0.1:8000/webhook",
    json=test_payload,
    headers={"Content-Type": "application/json"}
)

print(f"\nResponse status: {response.status_code}")
print(f"Response body: {response.text}")
