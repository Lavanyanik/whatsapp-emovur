from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession
from ..models import WebhookEvent
from ..utils.logger import get_logger
from .event_dispatcher import dispatch
from .candidate_service import map_button_to_status

logger = get_logger(__name__)


def _utc_from_unix(ts: Any) -> Optional[datetime]:
    try:
        if ts is None:
            return None
        if isinstance(ts, (int, float)):
            return datetime.fromtimestamp(float(ts), tz=timezone.utc)
        return datetime.fromtimestamp(float(str(ts)), tz=timezone.utc)
    except Exception:
        return None


async def process_event(*, payload: Dict[str, Any], db: AsyncSession) -> Dict[str, Any]:
    """Layered webhook entrypoint.

    Responsibilities:
      - normalize payload into one or more events
      - determine event type
      - call dispatcher
    """

    # Normalize (reuse existing parser from legacy module)
    from .webhook_service import parse_whatsapp_webhook_payload

    try:
        events = parse_whatsapp_webhook_payload(payload)
    except Exception as exc:
        logger.exception("process_event: normalization failed: %s", exc)
        return {"status": "no_supported_events", "detail": str(exc)}

    if not events:
        return {"status": "no_supported_events"}

    # For now: dispatch each event independently
    results: List[Dict[str, Any]] = []
    for ev in events:
        message_id = ev.get("message_id")
        if not message_id:
            results.append({"status": "ignored_missing_message_id"})
            continue

        # idempotency (reuse legacy idempotency table)
        payload_hash = hashlib.sha256(repr(payload).encode("utf-8")).hexdigest()
        is_dup = False
        try:
            existing = await db.execute(
                __import__("sqlalchemy").select(WebhookEvent).where(WebhookEvent.message_id == str(message_id))
            )
            row = existing.scalar_one_or_none()
            if row is not None:
                is_dup = True
        except Exception:
            # If idempotency fails, continue to avoid blocking webhook processing
            is_dup = False

        if is_dup:
            results.append({"status": "duplicate_ignored", "message_id": str(message_id)})
            continue

        timestamp = _utc_from_unix(ev.get("timestamp")) or datetime.now(tz=timezone.utc)

        normalized_event: Dict[str, Any] = {
            "message_id": str(message_id),
            "phone": ev.get("phone"),
            "timestamp": timestamp,
            "message_type": ev.get("message_type"),
            "button_title": ev.get("button_title"),
            "button_payload": ev.get("button_payload"),
            "button_id": ev.get("button_id"),
        }

        # Dispatch to handlers
        res = await dispatch(event=normalized_event, db=db)
        results.append(res)

        # Insert idempotency row after successful dispatch attempt (best-effort)
        try:
            db.add(WebhookEvent(message_id=str(message_id), payload_hash=payload_hash))
            await db.commit()
        except Exception:
            try:
                await db.rollback()
            except Exception:
                pass

    return {"status": "ok", "results": results}

