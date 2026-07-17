"""Database models for the WhatsApp integration."""

from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, String, Text
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class Candidate(Base):
    """Candidate record used by the inbound response workflow."""

    __tablename__ = "candidates"

    id = Column(Integer, primary_key=True, index=True)
    candidate_name = Column(String(255), nullable=False)
    phone = Column(String(50), nullable=False, index=True)
    role = Column(String(255), nullable=True)
    company = Column(String(255), nullable=True)
    status = Column(String(50), nullable=False, default="pending")
    response = Column(Text, nullable=True)
    candidate_response = Column(Text, nullable=True)
    response_received_at = Column(DateTime, nullable=True)
    message_id = Column(String(128), nullable=True)


class WebhookEvent(Base):
    """Records processed WhatsApp message IDs for idempotency."""

    __tablename__ = "webhook_events"

    id = Column(Integer, primary_key=True, index=True)
    message_id = Column(String(128), nullable=False, unique=True, index=True)
    payload_hash = Column(String(64), nullable=True)
    processed_at = Column(DateTime, nullable=False, default=datetime.utcnow)
