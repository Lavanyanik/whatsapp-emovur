import os
from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def set_test_env(monkeypatch: pytest.MonkeyPatch):
    # Ensure deterministic settings loading.
    # Tests generally only exercise internal parsing/handler logic.
    monkeypatch.setenv("EMOVUR_API_URL", "http://example.invalid")
    monkeypatch.setenv("API_KEY", "test_key")
    monkeypatch.setenv("PHONE_NUMBER_ID", "123")
    monkeypatch.setenv("WABA_ID", "test_waba")

    # Webhook verify token / secret are used for signature verification tests.
    monkeypatch.setenv("VERIFY_TOKEN", "test_verify_token")
    monkeypatch.setenv("WHATSAPP_APP_SECRET", "test_secret")
    monkeypatch.setenv("ENABLE_WEBHOOK_SIGNATURE_VERIFICATION", "true")



    monkeypatch.setenv("LOG_LEVEL", "WARNING")
    monkeypatch.setenv("EMOVUR_DRY_RUN", "true")

