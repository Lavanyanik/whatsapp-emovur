"""Database models for the WhatsApp integration."""

from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, String
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class WebhookEvent(Base):
    """Records processed WhatsApp message IDs for idempotency."""

    __tablename__ = "webhook_events"

    id = Column(Integer, primary_key=True, index=True)
    message_id = Column(String(128), nullable=False, unique=True, index=True)
    payload_hash = Column(String(64), nullable=True)
    processed_at = Column(DateTime, nullable=False, default=datetime.utcnow)
