import hashlib
import hmac

import httpx
import pytest
from fastapi import Request
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch, MagicMock

from app.config import Settings
from app.providers.emovur_provider import EmovurProvider
from app.providers.factory import ProviderFactory
from app.providers.meta_provider import MetaProvider
from app.routes.messages import _check_token, require_messages_auth
from app.routes.webhook import _verify_signature
from app.services.webhook_service import parse_whatsapp_webhook_payload, process_event


class FakeDB:
    def __init__(self):
        self.processed = set()
        self.added = []
        self.commits = 0
        self.rollbacks = 0

    async def execute(self, *_args, **_kwargs):
        db = self

        class Result:
            def scalar_one_or_none(self):
                return object() if db.processed else None

        return Result()

    def add(self, row):
        self.added.append(row)

    async def flush(self):
        return None

    async def commit(self):
        self.commits += 1
        self.processed.update(row.message_id for row in self.added)

    async def rollback(self):
        self.rollbacks += 1


def test_provider_factory_uses_meta_without_aggregator():
    settings = type("Settings", (), {"whatsapp_provider": None})()
    assert isinstance(ProviderFactory.create(settings), MetaProvider)


def test_provider_factory_uses_emovur_when_configured():
    settings = type("Settings", (), {"whatsapp_provider": "emovur"})()
    assert isinstance(ProviderFactory.create(settings), EmovurProvider)


def test_signature_verification_and_default_are_enabled():
    body = b"payload"
    secret = "secret"
    signature = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    assert _verify_signature(signature, secret, body)
    assert Settings.model_fields["enable_webhook_signature_verification"].default is True


# ===========================================================================
# Messages auth — direct unit tests of _check_token()
# ===========================================================================

def _patch_settings(monkeypatch, **kwargs):
    """Helper: patch get_settings to return a Settings-like object with *kwargs*."""
    defaults = {
        "messages_auth_token": None,
        "api_key": None,
        "whatsapp_provider": "emovur",
        "emovur_api_url": "https://api.emovur.com/v1",
        "phone_number_id": "test-phone",
        "waba_id": "test-waba",
        "verify_token": "abc",
    }
    defaults.update(kwargs)
    from app.routes import messages as msg_mod
    monkeypatch.setattr(msg_mod, "get_settings", lambda: type("Settings", (), defaults)())


def test_messages_auth_valid_token(monkeypatch):
    """X-API-Key matching MESSAGES_AUTH_TOKEN → passes."""
    _patch_settings(monkeypatch, messages_auth_token="valid-token", api_key="fallback")
    _check_token(api_key="valid-token")  # should not raise


def test_messages_auth_missing_token(monkeypatch):
    """No X-API-Key → 401."""
    _patch_settings(monkeypatch, messages_auth_token="required-token", api_key="fallback")
    with pytest.raises(Exception) as exc_info:
        _check_token(api_key=None)
    assert exc_info.value.status_code == 401


def test_messages_auth_invalid_token(monkeypatch):
    """Wrong X-API-Key → 401."""
    _patch_settings(monkeypatch, messages_auth_token="valid-token", api_key="fallback")
    with pytest.raises(Exception) as exc_info:
        _check_token(api_key="wrong-token")
    assert exc_info.value.status_code == 401


def test_messages_auth_falls_back_to_api_key(monkeypatch):
    """When MESSAGES_AUTH_TOKEN is unset, API_KEY is accepted."""
    _patch_settings(monkeypatch, messages_auth_token=None, api_key="fallback-api-key")
    _check_token(api_key="fallback-api-key")


def test_messages_auth_rejects_api_key_when_token_set(monkeypatch):
    """When MESSAGES_AUTH_TOKEN is set, API_KEY is NOT accepted as fallback."""
    _patch_settings(monkeypatch, messages_auth_token="token-only", api_key="api-key-fallback")
    with pytest.raises(Exception) as exc_info:
        _check_token(api_key="api-key-fallback")
    assert exc_info.value.status_code == 401


def test_messages_auth_server_misconfigured(monkeypatch):
    """Neither MESSAGES_AUTH_TOKEN nor API_KEY set → 500."""
    _patch_settings(monkeypatch, messages_auth_token=None, api_key=None)
    with pytest.raises(Exception) as exc_info:
        _check_token(api_key="anything")
    assert exc_info.value.status_code == 500


# ===========================================================================
# Messages auth — integration tests via TestClient
# ===========================================================================

def test_messages_endpoint_valid_key(monkeypatch):
    """POST /messages with valid X-API-Key → 200 (mock response)."""
    from app import main

    async def no_op_init_db():
        return None

    async def no_op_templates(*_args, **_kwargs):
        return []

    monkeypatch.setattr(main, "validate_settings", lambda _settings: None)
    monkeypatch.setattr(main, "init_db", no_op_init_db)
    monkeypatch.setattr(main, "refresh_templates_if_needed", no_op_templates)

    with TestClient(main.app) as client:
        import app.routes.messages as msg_mod
        import app.providers.factory as provider_factory
        import app.providers.emovur_provider as emovur_mod
        import app.providers.base as base_mod

        test_settings = type(
            "Settings",
            (),
            {
                "messages_auth_token": "test-auth-token",
                "api_key": "fallback",
                "whatsapp_provider": "emovur",
                "emovur_api_url": "https://api.emovur.com/v1",
                "phone_number_id": "test-phone-id",
                "emovur_dry_run": True,
                "emovur_max_retries": 1,
                "emovur_backoff_base": 1,
                "graph_api_version": "v25.0",
            },
        )()

        monkeypatch.setattr(msg_mod, "get_settings", lambda: test_settings)
        monkeypatch.setattr(provider_factory, "get_settings", lambda: test_settings)
        monkeypatch.setattr(emovur_mod, "get_settings", lambda: test_settings)
        monkeypatch.setattr(base_mod, "get_settings", lambda: test_settings)

        resp = client.post(
            "/messages",
            json={"type": "text", "to": "+1234567890", "text": "hello"},
            headers={"X-API-Key": "test-auth-token"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"


def test_messages_endpoint_missing_key(monkeypatch):
    """POST /messages without X-API-Key → 401."""
    from app import main

    async def no_op_init_db():
        return None

    async def no_op_templates(*_args, **_kwargs):
        return []

    monkeypatch.setattr(main, "validate_settings", lambda _settings: None)
    monkeypatch.setattr(main, "init_db", no_op_init_db)
    monkeypatch.setattr(main, "refresh_templates_if_needed", no_op_templates)

    with TestClient(main.app) as client:
        import app.routes.messages as msg_mod

        monkeypatch.setattr(
            msg_mod,
            "get_settings",
            lambda: type(
                "Settings",
                (),
                {
                    "messages_auth_token": "test-auth-token",
                    "api_key": "fallback",
                    "whatsapp_provider": "meta",
                    "emovur_api_url": "https://api.emovur.com/v1",
                    "phone_number_id": "test-phone-id",
                    "emovur_dry_run": True,
                    "emovur_max_retries": 1,
                    "emovur_backoff_base": 1,
                    "graph_api_version": "v25.0",
                },
            )(),
        )

        resp = client.post(
            "/messages",
            json={"type": "text", "to": "+1234567890", "text": "hello"},
        )
        assert resp.status_code == 401


def test_messages_endpoint_invalid_key(monkeypatch):
    """POST /messages with wrong X-API-Key → 401."""
    from app import main

    async def no_op_init_db():
        return None

    async def no_op_templates(*_args, **_kwargs):
        return []

    monkeypatch.setattr(main, "validate_settings", lambda _settings: None)
    monkeypatch.setattr(main, "init_db", no_op_init_db)
    monkeypatch.setattr(main, "refresh_templates_if_needed", no_op_templates)

    with TestClient(main.app) as client:
        import app.routes.messages as msg_mod

        monkeypatch.setattr(
            msg_mod,
            "get_settings",
            lambda: type(
                "Settings",
                (),
                {
                    "messages_auth_token": "test-auth-token",
                    "api_key": "fallback",
                    "whatsapp_provider": "meta",
                    "emovur_api_url": "https://api.emovur.com/v1",
                    "phone_number_id": "test-phone-id",
                    "emovur_dry_run": True,
                    "emovur_max_retries": 1,
                    "emovur_backoff_base": 1,
                    "graph_api_version": "v25.0",
                },
            )(),
        )

        resp = client.post(
            "/messages",
            json={"type": "text", "to": "+1234567890", "text": "hello"},
            headers={"X-API-Key": "wrong-token"},
        )
        assert resp.status_code == 401


def test_messages_endpoint_misconfigured(monkeypatch):
    """POST /messages when neither token nor key is set → 500."""
    from app import main

    async def no_op_init_db():
        return None

    async def no_op_templates(*_args, **_kwargs):
        return []

    monkeypatch.setattr(main, "validate_settings", lambda _settings: None)
    monkeypatch.setattr(main, "init_db", no_op_init_db)
    monkeypatch.setattr(main, "refresh_templates_if_needed", no_op_templates)

    with TestClient(main.app) as client:
        import app.routes.messages as msg_mod

        monkeypatch.setattr(
            msg_mod,
            "get_settings",
            lambda: type(
                "Settings",
                (),
                {
                    "messages_auth_token": None,
                    "api_key": None,
                    "whatsapp_provider": "meta",
                    "emovur_api_url": "https://api.emovur.com/v1",
                    "phone_number_id": "test-phone-id",
                    "emovur_dry_run": True,
                    "emovur_max_retries": 1,
                    "emovur_backoff_base": 1,
                    "graph_api_version": "v25.0",
                },
            )(),
        )

        resp = client.post(
            "/messages",
            json={"type": "text", "to": "+1234567890", "text": "hello"},
            headers={"X-API-Key": "anything"},
        )
        assert resp.status_code == 500


def test_signature_verification_and_default_are_enabled():
    body = b"payload"
    secret = "secret"
    signature = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    assert _verify_signature(signature, secret, body)
    assert Settings.model_fields["enable_webhook_signature_verification"].default is True


@pytest.mark.asyncio
async def test_callback_runs_before_idempotency_record_is_added():
    db = FakeDB()
    observed = []

    async def on_reply(event):
        observed.append((event, list(db.added)))

    payload = {
        "messages": [
            {
                "id": "message-1",
                "from": "15551234567",
                "type": "button",
                "button": {"payload": "Not Interested", "text": "Not Interested"},
            }
        ]
    }
    result = await process_event(payload=payload, db=db, on_reply=on_reply)

    assert result["results"][0]["status"] == "ok"
    assert observed[0][0]["reply_key"] == "not_interested"
    assert observed[0][1] == []
    assert db.commits == 1


@pytest.mark.asyncio
async def test_failed_callback_does_not_mark_event_processed():
    db = FakeDB()

    async def on_reply(_event):
        raise RuntimeError("callback failed")

    payload = {
        "messages": [
            {
                "id": "message-2",
                "from": "15551234567",
                "type": "button",
                "button": {},
            }
        ]
    }
    result = await process_event(payload=payload, db=db, on_reply=on_reply)

    assert result["status"] == "fatal_error"
    assert db.added == []
    assert db.rollbacks == 1


@pytest.mark.asyncio
async def test_default_callback_dispatches_normalized_button_event(monkeypatch):
    db = FakeDB()
    dispatched = []

    from app.services import event_dispatcher

    async def fake_dispatch_event(*, event, db):
        dispatched.append((event, db))
        return {"status": "processed"}

    monkeypatch.setattr(event_dispatcher, "dispatch_event", fake_dispatch_event)
    payload = {
        "messages": [
            {
                "id": "message-dispatch-1",
                "from": "15551234567",
                "type": "button",
                "button": {"payload": "Interested", "text": "Interested"},
            }
        ]
    }

    result = await process_event(payload=payload, db=db)

    assert result["results"][0]["status"] == "ok"
    assert len(dispatched) == 1
    event, dispatched_db = dispatched[0]
    assert dispatched_db is db
    assert event["message_type"] == "button"
    assert event["reply_key"] == "interested"


@pytest.mark.asyncio
async def test_button_dispatch_reaches_candidate_response_service(monkeypatch):
    from app.handlers import button_handler
    from app.services.event_dispatcher import dispatch_event

    calls = []

    async def fake_update_candidate_response(**kwargs):
        calls.append(kwargs)
        return {"status": "processed"}

    monkeypatch.setattr(button_handler, "update_candidate_response", fake_update_candidate_response)
    result = await dispatch_event(
        event={
            "message_id": "message-handler-1",
            "phone": "+15551234567",
            "timestamp": None,
            "message_type": "button",
            "button_title": "Interested",
            "button_payload": "Interested",
        },
        db=FakeDB(),
    )

    assert result == {"status": "processed"}
    assert calls[0]["phone"] == "+15551234567"
    assert calls[0]["button_payload"] == "Interested"


def test_webhook_parser_normalizes_interactive_reply():
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
                                    "interactive": {
                                        "button_reply": {
                                            "id": "btn-1",
                                            "title": "Interested",
                                        }
                                    },
                                }
                            ],
                        }
                    }
                ]
            }
        ]
    }
    event = parse_whatsapp_webhook_payload(payload)[0]
    assert event["button_payload"] == "btn-1"
    assert event["phone"] == "+15551234567"


def test_fastapi_app_starts(monkeypatch):
    from app import main

    async def no_op_init_db():
        return None

    async def no_op_templates(*_args, **_kwargs):
        return []

    monkeypatch.setattr(main, "validate_settings", lambda _settings: None)
    monkeypatch.setattr(main, "init_db", no_op_init_db)
    monkeypatch.setattr(main, "refresh_templates_if_needed", no_op_templates)

    with TestClient(main.app) as client:
        assert client.get("/health").status_code == 200
