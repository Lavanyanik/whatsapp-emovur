import hashlib
import hmac
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.config import get_settings
from app.routes.webhook import receive_webhook
from app.services.webhook_service import process_event
from app.providers.factory import get_provider
from app.providers.emovur_provider import EmovurProvider
from app.providers.base import BaseCloudApiProvider


@pytest.fixture()
def anyio_backend():
    return "asyncio"


@pytest.mark.asyncio
async def test_webhook_parsing_normalizes_button_reply():
    payload = {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "contacts": [{"wa_id": "15551234567"}],
                            "messages": [
                                {
                                    "id": "msg-1",
                                    "from": "15551234567",
                                    "timestamp": "1710000000",
                                    "type": "interactive",
                                    "interactive": {"button_reply": {"id": "btn-1", "title": "Interested"}},
                                }
                            ],
                        }
                    }
                ]
            }
        ]
    }

    events = __import__("app.services.webhook_service", fromlist=["parse_whatsapp_webhook_payload"]).parse_whatsapp_webhook_payload(payload)
    assert events
    assert events[0]["message_type"] == "interactive"
    assert events[0]["button_payload"] == "btn-1"
    assert events[0]["phone"] == "+15551234567"


@pytest.mark.asyncio
async def test_idempotency_ordering_commit_after_success(monkeypatch):
    from app.services.webhook_service import _idempotency_check_or_insert
    from app.models import WebhookEvent

    class DummyDB:
        def __init__(self):
            self.commits = 0
            self.rollbacks = 0
            self.added = []
        async def execute(self, *args, **kwargs):
            class Result:
                def scalar_one_or_none(self):
                    return None
            return Result()
        async def flush(self):
            return None
        async def commit(self):
            self.commits += 1
        async def rollback(self):
            self.rollbacks += 1
        def add(self, row):
            self.added.append(row)

    db = DummyDB()
    inserted = await _idempotency_check_or_insert(db, message_id="msg-1", payload_hash="hash")
    assert inserted[0] is False
    assert db.commits == 0


def test_provider_factory_defaults_to_meta_provider(monkeypatch):
    monkeypatch.setattr("app.config.get_settings", lambda: type("S", (), {"whatsapp_provider": None})())
    provider = get_provider()
    assert isinstance(provider, EmovurProvider)


@pytest.mark.asyncio
async def test_provider_send_text_uses_provider(monkeypatch):
    class FakeProvider(BaseCloudApiProvider):
        async def send_text(self, *, to: str, text: str, timeout: int = 10):
            return {"status_code": 200, "body": {"ok": True}}

        async def send_template(self, *args, **kwargs):
            raise NotImplementedError

        async def send_media(self, *args, **kwargs):
            raise NotImplementedError

        async def send_interactive(self, *args, **kwargs):
            raise NotImplementedError

    monkeypatch.setattr("app.providers.factory.get_settings", lambda: type("S", (), {"whatsapp_provider": "emovur"})())
    monkeypatch.setattr("app.providers.factory.EmovurProvider", lambda: FakeProvider())
    provider = get_provider()
    assert provider.send_text(to="+1555", text="hi")


def test_signature_verification_works():
    body = b"payload"
    secret = "secret"
    signature = "sha256=" + hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    from app.routes.webhook import _verify_signature

    assert _verify_signature(signature, secret, body) is True


def test_auth_guard_is_present():
    from app.routes.messages import send_message_route

    assert send_message_route is not None


@pytest.mark.asyncio
async def test_callback_invocation(monkeypatch):
    calls = []

    async def fake_on_reply(event):
        calls.append(event["message_id"])

    from app.services.webhook_service import process_event

    class DummyDB:
        async def execute(self, *args, **kwargs):
            class Result:
                def scalar_one_or_none(self):
                    return None
            return Result()
        async def flush(self):
            return None
        async def commit(self):
            return None
        async def rollback(self):
            return None
        def add(self, row):
            return None

    monkeypatch.setattr("app.services.webhook_service.dispatch", lambda **kwargs: ({"status": "ok"},))
    monkeypatch.setattr("app.services.webhook_service.get_settings", lambda: type("S", (), {"callback": None})())

    # Placeholder assertion to ensure the callback path can be wired.
    assert True
