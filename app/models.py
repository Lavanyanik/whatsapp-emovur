"""SQLAlchemy models for whatsapp-emovur.

Defines the Candidate table required by the project.
"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Text
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class Candidate(Base):
    """Represents a candidate entry for screening invitation flow."""

    __tablename__ = "candidates"

    id = Column(Integer, primary_key=True, index=True)
    candidate_name = Column(String(255), nullable=False)
    phone = Column(String(50), nullable=False, index=True)
    role = Column(String(255), nullable=True)
    company = Column(String(255), nullable=True)

    # Existing flow status field.
    status = Column(String(50), nullable=False, default="pending")

    # Existing response storage (legacy name).
    response = Column(Text, nullable=True)

    # Webhook-required fields.
    candidate_response = Column(Text, nullable=True)
    response_received_at = Column(DateTime, nullable=True)
    message_id = Column(String(128), nullable=True)

    invite_sent_at = Column(DateTime, nullable=True)
    followup_sent_at = Column(DateTime, nullable=True)
    final_sent_at = Column(DateTime, nullable=True)
    responded_at = Column(DateTime, nullable=True)

    reminder1_sent = Column(Integer, nullable=False, default=0)
    reminder2_sent = Column(Integer, nullable=False, default=0)

    def mark_invited(self) -> None:
        self.status = "invited"
        self.invite_sent_at = datetime.utcnow()

    def mark_followup_sent(self) -> None:
        self.status = "followup_sent"
        self.followup_sent_at = datetime.utcnow()

    def mark_final_sent(self) -> None:
        self.status = "final_sent"
        self.final_sent_at = datetime.utcnow()

    def mark_responded(self, response_text: str) -> None:
        self.status = "responded"
        self.response = response_text
        self.responded_at = datetime.utcnow()

    def __repr__(self) -> str:
        return (
            f"<Candidate id={self.id} name={self.candidate_name} phone={self.phone} "
            f"status={self.status}>"
        )


class WebhookEvent(Base):
    """Idempotency table to prevent duplicate processing of WhatsApp webhook events."""

    __tablename__ = "webhook_events"

    id = Column(Integer, primary_key=True, index=True)
    message_id = Column(String(128), nullable=False, unique=True, index=True)
    payload_hash = Column(String(64), nullable=True)
    processed_at = Column(DateTime, nullable=False, default=datetime.utcnow)

