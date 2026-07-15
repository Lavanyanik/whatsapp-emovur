"""Test script to verify /messages endpoint functionality."""
import requests
import json

# Test template message sending
test_payload = {
    "type": "template",
    "to": "919876543210",
    "template_name": "test_template",
    "language": "en",
    "components": []
}

print("Testing /messages endpoint with template message...")
print(f"Payload: {json.dumps(test_payload, indent=2)}")

try:
    response = requests.post(
        "http://127.0.0.1:8000/messages",
        json=test_payload,
        headers={"Content-Type": "application/json"}
    )
    
    print(f"\nResponse status: {response.status_code}")
    print(f"Response body: {response.text}")
    
    if response.status_code == 200:
        print("✓ /messages endpoint is working")
    else:
        print(f"✗ /messages endpoint returned error status: {response.status_code}")
        
except Exception as e:
    print(f"✗ Error calling /messages endpoint: {e}")

# Test text message sending
test_text_payload = {
    "type": "text",
    "to": "919876543210",
    "text": "Test message from backend"
}

print("\n\nTesting /messages endpoint with text message...")
print(f"Payload: {json.dumps(test_text_payload, indent=2)}")

try:
    response = requests.post(
        "http://127.0.0.1:8000/messages",
        json=test_text_payload,
        headers={"Content-Type": "application/json"}
    )
    
    print(f"\nResponse status: {response.status_code}")
    print(f"Response body: {response.text}")
    
    if response.status_code == 200:
        print("✓ Text message sending is working")
    else:
        print(f"✗ Text message sending returned error status: {response.status_code}")
        
except Exception as e:
    print(f"✗ Error sending text message: {e}")
