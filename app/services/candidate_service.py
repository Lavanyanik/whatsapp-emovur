from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any, Optional, Tuple

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Candidate
from ..utils.logger import get_logger
from .message_service import send_candidate_response


# NOTE: Candidate response handling is intentionally button-scoped.
# Any outbound WhatsApp send should be performed after DB commit.


logger = get_logger(__name__)


RESPONSE_MAPPING = {
    "interested": ("interested", "Interested"),
    "not interested": ("not_interested", "Not Interested"),
    "not-interested": ("not_interested", "Not Interested"),
    "not_interested": ("not_interested", "Not Interested"),
    "opt out": ("opt_out", "Opt Out"),
    "opt_out": ("opt_out", "Opt Out"),
    "opt-out": ("opt_out", "Opt Out"),
}


def _normalize_button_text(s: Any) -> str:
    if s is None:
        return ""
    return str(s).strip().lower()


def map_button_to_status(button_title: Optional[str], button_payload: Optional[str]) -> Tuple[Optional[str], Optional[str]]:
    """Return (candidate_status, candidate_response_text)."""

    candidates = [button_title, button_payload]
    for c in candidates:
        norm = _normalize_button_text(c)
        if not norm:
            continue
        mapped = RESPONSE_MAPPING.get(norm)
        if mapped:
            return mapped[0], mapped[1]

    for c in candidates:
        norm = _normalize_button_text(c)
        if not norm:
            continue
        if "interested" in norm:
            return RESPONSE_MAPPING["interested"]
        if "not" in norm and "interested" in norm:
            return RESPONSE_MAPPING["not interested"]
        if "opt" in norm and "out" in norm:
            return RESPONSE_MAPPING["opt out"]

    return None, None


def _utc_from_timestamp(ts: Any) -> Optional[datetime]:
    try:
        if ts is None:
            return None
        if isinstance(ts, (int, float)):
            return datetime.fromtimestamp(float(ts), tz=timezone.utc)
        return datetime.fromtimestamp(float(str(ts)), tz=timezone.utc)
    except Exception:
        return None


async def update_candidate_response_from_button(
    *,
    db: AsyncSession,
    phone: str,
    message_id: Optional[str],
    button_title: Optional[str],
    button_payload: Optional[str],
    timestamp: Any,
) -> dict[str, Any]:
    """Update candidate status based on button payload and send WhatsApp reply.

    IMPORTANT BUG FIX:
    After updating candidate response/status, send reply via message_service.
    """

    try:
        status, candidate_response_text = map_button_to_status(button_title, button_payload)
        if status is None or candidate_response_text is None:
            logger.info(
                "candidate_service: unrecognized button phone=%s button_title=%s button_payload=%s",
                phone,
                button_title,
                button_payload,
            )
            return {"status": "ignored_unrecognized_button"}

        logger.info("candidate_service: Incoming phone=%s", phone)

        # Debug: dump all candidate phone numbers to compare against incoming phone.
        try:
            res_all = await db.execute(select(Candidate))
            for c in res_all.scalars():
                logger.info("candidate_service: DB Candidate id=%s phone=%s", c.id, c.phone)
        except Exception:
            logger.exception("candidate_service: failed to dump candidates for phone debug")

        # Normalize phone formats: compare by last 10 digits (keeps prior behavior intent).
        incoming_normalized = ''.join(filter(str.isdigit, str(phone)))
        incoming_normalized = incoming_normalized[-10:] if incoming_normalized else ''

        # Also normalize stored candidate phones for last-10-digit comparison.
        # We still query using the normalized incoming value by comparing after stripping digits.
        ts_dt = _utc_from_timestamp(timestamp) or datetime.now(tz=timezone.utc)

        # Prefer an exact match first (preserves existing behavior when format matches).
        res = await db.execute(
            select(Candidate).where(Candidate.phone == str(phone)).order_by(Candidate.id.desc())
        )
        candidate = res.scalars().first()

        if candidate is None and incoming_normalized:
            # Fallback: match by last 10 digits.
            res_all = await db.execute(select(Candidate).order_by(Candidate.id.desc()))
            for c in res_all.scalars():
                stored_digits = ''.join(filter(str.isdigit, str(c.phone)))
                stored_normalized = stored_digits[-10:] if stored_digits else ''
                if stored_normalized == incoming_normalized:
                    candidate = c
                    break

        if candidate is None:
            logger.warning("candidate_service: candidate not found phone=%s", phone)
            return {"status": "candidate_not_found"}


        candidate.candidate_response = candidate_response_text
        candidate.response_received_at = ts_dt
        candidate.status = status
        if message_id:
            candidate.message_id = str(message_id)

        await db.commit()

        logger.info(
            "candidate_service: DB commit done candidate_id=%s phone=%s next_send_text=%s",
            getattr(candidate, "id", None),
            phone,
            candidate_response_text,
        )

        # Send WhatsApp reply (reuse existing implementation)
        try:
            logger.info(
                "candidate_service: sending confirmation reply candidate_id=%s phone=%s response_text=%s",
                getattr(candidate, "id", None),
                phone,
                candidate_response_text,
            )
            send_result = await send_candidate_response(phone=phone, text=candidate_response_text)
            logger.info(
                "candidate_service: send_candidate_response success candidate_id=%s result_status_code=%s send_result=%s",
                getattr(candidate, "id", None),
                getattr(send_result, "get", lambda *_: None)("status_code"),
                send_result,
            )
        except Exception as exc:
            logger.exception(
                "candidate_service: send_candidate_response failed candidate_id=%s phone=%s error=%s",
                getattr(candidate, "id", None),
                phone,
                exc,
            )
            # Root fix expectation: DB commit must not be rolled back if reply sending fails.
            # At this stage DB is already committed, so just report failure.
            return {
                "status": "processed",
                "reply_sent": False,
                "candidate_id": candidate.id,
                "candidate_status": status,
                "candidate_response": candidate_response_text,
                "detail": str(exc),
            }

        return {
            "status": "processed",
            "candidate_id": candidate.id,
            "candidate_status": status,
            "candidate_response": candidate_response_text,
        }

    except SQLAlchemyError as exc:
        try:
            await db.rollback()
        except Exception:
            pass
        logger.exception("candidate_service: db error phone=%s: %s", phone, exc)
        return {"status": "database_error", "detail": str(exc)}
    except Exception as exc:
        try:
            await db.rollback()
        except Exception:
            pass
        logger.exception("candidate_service: unexpected error phone=%s: %s", phone, exc)
        return {"status": "unexpected_error", "detail": str(exc)}

