import json
import urllib.request
import sys

url = 'http://127.0.0.1:8001/messages'
body = {
    "to": "+919876543210",
    "type": "text",
    "text": {"body": "Hello from SuprHire demo"}
}

data = json.dumps(body).encode('utf-8')
req = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json'})
try:
    with urllib.request.urlopen(req, timeout=30) as resp:
        resp_body = resp.read().decode('utf-8')
        print('Status:', resp.status)
        print('Body:', resp_body)
except Exception as e:
    print('Request failed:', e)
    sys.exit(1)
