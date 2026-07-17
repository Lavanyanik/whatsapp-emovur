"""Candidate response persistence for inbound WhatsApp button replies."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Candidate
from ..utils.logger import get_logger

logger = get_logger(__name__)

_RESPONSE_MAPPING = {
    "interested": ("interested", "Interested"),
    "not interested": ("not_interested", "Not Interested"),
    "not-interested": ("not_interested", "Not Interested"),
    "not_interested": ("not_interested", "Not Interested"),
    "opt out": ("opt_out", "Opt Out"),
    "opt-out": ("opt_out", "Opt Out"),
    "opt_out": ("opt_out", "Opt Out"),
}


def _map_button(button_title: Optional[str], button_payload: Optional[str]) -> tuple[Optional[str], Optional[str]]:
    for value in (button_payload, button_title):
        key = " ".join(str(value or "").strip().lower().replace("_", " ").replace("-", " ").split())
        mapped = _RESPONSE_MAPPING.get(key)
        if mapped:
            return mapped
    return None, None


def _timestamp(value: Any) -> datetime:
    try:
        return datetime.fromtimestamp(float(value), tz=timezone.utc)
    except (TypeError, ValueError, OverflowError, OSError):
        return datetime.now(tz=timezone.utc)


async def update_candidate_response(
    *,
    db: AsyncSession,
    phone: str,
    message_id: Optional[str],
    button_title: Optional[str],
    button_payload: Optional[str],
    timestamp: Any,
) -> dict[str, Any]:
    """Persist a recognized candidate button response.

    This is the existing candidate-response business operation; dispatching is
    deliberately kept outside this service.
    """

    status, response_text = _map_button(button_title, button_payload)
    if not status or not response_text:
        logger.info("candidate_service: ignored unrecognized button phone=%s", phone)
        return {"status": "ignored_unrecognized_button"}

    try:
        exact = await db.execute(
            select(Candidate).where(Candidate.phone == str(phone)).order_by(Candidate.id.desc())
        )
        candidate = exact.scalars().first()

        if candidate is None:
            incoming = "".join(filter(str.isdigit, str(phone)))[-10:]
            if incoming:
                candidates = await db.execute(select(Candidate).order_by(Candidate.id.desc()))
                candidate = next(
                    (
                        item
                        for item in candidates.scalars()
                        if "".join(filter(str.isdigit, str(item.phone)))[-10:] == incoming
                    ),
                    None,
                )

        if candidate is None:
            logger.warning("candidate_service: candidate not found phone=%s", phone)
            return {"status": "candidate_not_found"}

        candidate.candidate_response = response_text
        candidate.response_received_at = _timestamp(timestamp)
        candidate.status = status
        if message_id:
            candidate.message_id = str(message_id)
        await db.commit()
        logger.info("candidate_service: response updated candidate_id=%s status=%s", candidate.id, status)
        return {
            "status": "processed",
            "candidate_id": candidate.id,
            "candidate_status": status,
            "candidate_response": response_text,
        }
    except SQLAlchemyError as exc:
        await db.rollback()
        logger.exception("candidate_service: database error phone=%s", phone)
        return {"status": "database_error", "detail": str(exc)}


# Compatibility with the previously used handler name.
update_candidate_response_from_button = update_candidate_response
