"""Application configuration using pydantic-settings (Pydantic v2).

Reads all values from .env at the project root (parent of the app package).
"""

from functools import lru_cache
from pathlib import Path
import logging

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import model_validator

# Resolve .env relative to project root
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_ENV_FILE = _PROJECT_ROOT / ".env"


class Settings(BaseSettings):
    # ------------------------------------------------------------------
    # Emovur Configuration
    # ------------------------------------------------------------------
    emovur_api_url: str
    api_key: str
    phone_number_id: str
    waba_id: str

    # ------------------------------------------------------------------
    # Meta WhatsApp Cloud API
    # ------------------------------------------------------------------
    whatsapp_access_token: str | None = None
    whatsapp_phone_number_id: str | None = None
    whatsapp_business_account_id: str | None = None
    graph_api_version: str = "v25.0"

    # ------------------------------------------------------------------
    # Webhook Configuration
    # ------------------------------------------------------------------
    verify_token: str | None = None
    whatsapp_app_secret: str | None = None
    enable_webhook_signature_verification: bool = True

    @model_validator(mode="after")
    def apply_provider_defaults(self):
        """Auto-configure settings based on the selected provider."""
        # When provider is emovur, disable signature verification (preserve existing behavior).
        # Meta provider users should explicitly configure WHATSAPP_APP_SECRET if needed.
        if self.whatsapp_provider == "emovur":
            self.enable_webhook_signature_verification = False
        return self

    # ------------------------------------------------------------------
    # Provider Configuration
    # ------------------------------------------------------------------
    whatsapp_provider: str = "meta"

    meta_api_url: str = "https://graph.facebook.com"

    messages_auth_token: str | None = None

    # ------------------------------------------------------------------
    # Retry Configuration
    # ------------------------------------------------------------------
    emovur_max_retries: int = 2
    emovur_backoff_base: int = 2

    # ------------------------------------------------------------------
    # Logging
    # ------------------------------------------------------------------
    log_level: str = "INFO"
    emovur_dry_run: bool = False

    model_config = SettingsConfigDict(
        env_file=str(_ENV_FILE),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    def __repr_args__(self):
        return (
            ("emovur_api_url", self.emovur_api_url),
            ("phone_number_id", self.phone_number_id),
            ("waba_id", self.waba_id),
            ("whatsapp_provider", self.whatsapp_provider),
            ("meta_api_url", self.meta_api_url),
            (
                "enable_webhook_signature_verification",
                self.enable_webhook_signature_verification,
            ),
            ("log_level", self.log_level),
        )


@lru_cache()
def get_settings() -> Settings:
    settings = Settings()
    logging.getLogger().setLevel(settings.log_level)
    return settings


def validate_settings(settings: Settings) -> None:
    """Validate required configuration.
    
    When provider is 'meta' (default), only Emovur legacy fields are optional.
    When provider is 'emovur', all Emovur fields are required.
    """

    missing = []

    # Fields required by Emovur (legacy) — only validated when emovur is the provider
    if settings.whatsapp_provider == "emovur":
        if not settings.emovur_api_url:
            missing.append("EMOVUR_API_URL")
        if not settings.api_key:
            missing.append("API_KEY")
        if not settings.phone_number_id:
            missing.append("PHONE_NUMBER_ID")
        if not settings.waba_id:
            missing.append("WABA_ID")
    else:
        # Meta provider — these are not strictly required at startup,
        # but will produce runtime errors if missing when sending messages.
        pass

    # Common required fields across all providers
    if not settings.verify_token:
        missing.append("VERIFY_TOKEN")

    if missing:
        raise RuntimeError(
            f"Missing required environment variables: {', '.join(missing)}"
        )
