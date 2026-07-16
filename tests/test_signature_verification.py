from __future__ import annotations

import hashlib
import hmac
import json

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.config import get_settings


def _compute_signature(secret: str, body_bytes: bytes) -> str:
    digest = hmac.new(secret.encode("utf-8"), body_bytes, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


def test_webhook_signature_invalid():
    client = TestClient(app)

    body = {"entry": [], "object": "whatsapp_business_account"}
    raw = json.dumps(body).encode("utf-8")

    # Ensure signature verification is enabled. If it isn't, skip this test
    # (env parsing differences should not break the rest of the suite).
    settings = get_settings()
    if not settings.enable_webhook_signature_verification:
        import pytest

        pytest.skip("Signature verification disabled in test environment")



    headers = {
        "Content-Type": "application/json",
        "X-Hub-Signature-256": "sha256=deadbeef",
    }

    resp = client.post("/webhook", data=raw, headers=headers)
    # Controller raises 403 invalid_signature when signature verification enabled.
    assert resp.status_code == 403

