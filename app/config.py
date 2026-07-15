"""Application configuration using pydantic-settings (Pydantic v2).

Reads all values from .env at the project root (parent of the app package).
"""
from functools import lru_cache
from pathlib import Path
from typing import Any

import logging

from pydantic_settings import BaseSettings, SettingsConfigDict

# Resolve .env relative to project root (parent of app/), not CWD.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_ENV_FILE = _PROJECT_ROOT / ".env"


class Settings(BaseSettings):
    """Application settings read from environment (and .env file).

    Environment variables expected (examples):
      - EMOVUR_API_URL
      - API_KEY
      - PHONE_NUMBER_ID
      - WABA_ID
      - FOLLOWUP_DELAY_HOURS
      - FINAL_REMINDER_DELAY_HOURS
      - LOG_LEVEL

    Webhook (Meta WhatsApp Cloud API) expected settings:
      - VERIFY_TOKEN
      - WHATSAPP_APP_SECRET
      - ENABLE_WEBHOOK_SIGNATURE_VERIFICATION
    """

    # Emovur API settings
    emovur_api_url: str
    api_key: str
    phone_number_id: str
    waba_id: str

    # Meta webhook verification settings
    verify_token: str | None = None
    whatsapp_app_secret: str | None = None
    enable_webhook_signature_verification: bool = False




    # Emovur client resiliency settings
    emovur_max_retries: int = 2
    emovur_backoff_base: int = 2

    log_level: str = "INFO"
    # When true, Emovur calls are simulated and no external network calls are made.
    emovur_dry_run: bool = False

    model_config = SettingsConfigDict(
        env_file=str(_ENV_FILE),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    def __repr_args__(self) -> "tuple[tuple[str, Any], ...]":
        # Do not print API key in repr
        return (
            ("emovur_api_url", self.emovur_api_url),
            ("phone_number_id", self.phone_number_id),
            ("waba_id", self.waba_id),
            ("followup_delay_hours", self.followup_delay_hours),
            ("final_reminder_delay_hours", self.final_reminder_delay_hours),
            ("log_level", self.log_level),
        )




@lru_cache()
def get_settings() -> Settings:
    """Return cached Settings instance and configure basic logging level."""
    settings = Settings()
    # Configure root logger level based on settings
    logging.getLogger().setLevel(settings.log_level)
    return settings


def validate_settings(s: Settings) -> None:

    """Validate required environment settings and raise RuntimeError on missing ones.

    This function avoids printing sensitive values (like API keys) and instead
    reports which variables are missing.
    """
    missing = []
    if not s.emovur_api_url:
        missing.append("EMOVUR_API_URL")
    if not s.api_key:
        missing.append("API_KEY")
    if not s.phone_number_id:
        missing.append("PHONE_NUMBER_ID")
    if not s.waba_id:
        missing.append("WABA_ID")

    if missing:
        raise RuntimeError(f"Missing required environment variables: {', '.join(missing)}")
