from __future__ import annotations

"""Webhook processing layer.

This module keeps backward-compatible exports:
  - parse_whatsapp_webhook_payload
  - process_whatsapp_events

and introduces the layered entrypoint:
  - async process_event(...)

"""

# NOTE: We keep most legacy logic in this file for compatibility.
# The new layered code uses process_event for routing to handlers.

import hashlib
import hmac
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from ..config import get_settings
from ..models import WebhookEvent
from ..utils.logger import get_logger


logger = get_logger(__name__)


@dataclass(frozen=True)
class WebhookProcessResult:
    status: str
    message_id: Optional[str] = None
    phone: Optional[str] = None
    timestamp: Optional[datetime] = None
    button_title: Optional[str] = None
    button_payload: Optional[str] = None
    button_id: Optional[str] = None
    candidate_id: Optional[int] = None
    detail: Optional[str] = None


# ------------------------- Normalization helpers (legacy) -------------------------

RESPONSE_MAPPING: Dict[str, Tuple[str, str]] = {
    "interested": ("interested", "Interested"),
    "not interested": ("not_interested", "Not Interested"),
    "not_interested": ("not_interested", "Not Interested"),
    "not-interested": ("not_interested", "Not Interested"),
    "opt out": ("opt_out", "Opt Out"),
    "opt_out": ("opt_out", "Opt Out"),
    "opt-out": ("opt_out", "Opt Out"),
}


def _normalize_phone(phone: Optional[str]) -> str:
    """Normalize phone number to include + prefix. E.164 format."""
    if not phone:
        return ""
    phone_str = str(phone).strip()
    if not phone_str:
        return ""
    # Remove any existing + and add one
    phone_str = phone_str.lstrip("+")
    return f"+{phone_str}"


def _utc_from_unix(ts: Any) -> Optional[datetime]:
    try:
        if ts is None:
            return None
        if isinstance(ts, (int, float)):
            return datetime.fromtimestamp(float(ts), tz=timezone.utc)
        return datetime.fromtimestamp(float(str(ts)), tz=timezone.utc)
    except Exception:
        return None


def _extract_events_emovur(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Emovur-style webhook payloads:
      - top-level messages: [{ type: "button", button: { payload, text }, ... }]
    Also handle best-effort fallbacks for phone/timestamp per-message.
    """
    out: List[Dict[str, Any]] = []

    if not isinstance(payload, dict):
        return out

    messages = payload.get("messages") or []
    if not isinstance(messages, list):
        return out

    msg_id = payload.get("message_id") or payload.get("id")
    phone = payload.get("from") or payload.get("phone") or payload.get("wa_id")
    ts = payload.get("timestamp")

    for msg in messages:
        if not isinstance(msg, dict):
            continue

        m_type = msg.get("type")
        button = msg.get("button") or {}

        btn_payload = button.get("payload")
        btn_text = button.get("text")

        # Fallback payload/text mapping for WhatsApp "button reply"
        # Incoming payload values look like:
        #   button.payload in {"Interested","Not Interested","Opt Out"}
        #   button.text in the same value
        if btn_payload is None and isinstance(btn_text, str):
            btn_payload = btn_text

        mid = msg.get("message_id") or msg.get("id") or msg_id
        mphone = msg.get("from") or msg.get("phone") or phone
        mts = msg.get("timestamp") or ts

        if m_type != "button":
            continue

        out.append(
            {
                "message_id": str(mid) if mid is not None else None,
                "phone": _normalize_phone(mphone),
                "timestamp": mts,
                # Dispatcher contract expects "button"
                "message_type": "button",
                "button_title": btn_text,
                "button_payload": btn_payload,
                "button_id": None,
            }
        )

    return out


def _extract_events_interactive_button_reply(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    WhatsApp Cloud "interactive" button replies:
      - entry[].changes[].value.messages[].type == "interactive"
      - messages[].interactive.button_reply.{ id, title }
    """
    out: List[Dict[str, Any]] = []

    if not isinstance(payload, dict):
        return out

    entries = payload.get("entry") or []
    if not isinstance(entries, list):
        return out

    for entry in entries:
        changes = entry.get("changes") or []
        if not isinstance(changes, list):
            continue

        for change in changes:
            value = change.get("value") or {}
            messages = value.get("messages") or []
            if not isinstance(messages, list):
                continue

            contacts = value.get("contacts") or []
            wa_id = None
            if isinstance(contacts, list) and contacts:
                wa_id = (contacts[0] or {}).get("wa_id")

            for msg in messages:
                if not isinstance(msg, dict):
                    continue

                msg_id = msg.get("id")
                mphone = msg.get("from") or wa_id
                ts = msg.get("timestamp")
                m_type = msg.get("type")

                button_reply_id = None
                button_reply_title = None
                button_payload = None

                if m_type == "interactive":
                    interactive = msg.get("interactive") or {}
                    button_reply = interactive.get("button_reply") or {}
                    # Meta sends:
                    #   interactive: { button_reply: { id, title } }
                    button_reply_id = button_reply.get("id")
                    button_reply_title = button_reply.get("title")
                    # Keep payload as id for mapping to candidate status.
                    button_payload = button_reply_id or button_reply.get("title")

                if m_type != "interactive":
                    continue

                out.append(
                    {
                        "message_id": str(msg_id) if msg_id is not None else None,
                        "phone": _normalize_phone(mphone),
                        "timestamp": ts,
                        # Dispatcher expects "interactive" in legacy path
                        "message_type": "interactive",
                        "button_title": button_reply_title,
                        "button_payload": (interactive.get("button_reply") or {}).get("id")
                        or button_payload,
                        "button_id": str(button_reply_id) if button_reply_id is not None else None,
                    }
                )

    return out


def _extract_events_whatsapp_cloud_button_reply(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    WhatsApp Cloud (non-interactive) button replies where:
      - entry[].changes[].value.messages[].type == "button"
      - messages[].button.payload and messages[].button.text are set
    """
    out: List[Dict[str, Any]] = []
    if not isinstance(payload, dict):
        return out

    entries = payload.get("entry") or []
    if not isinstance(entries, list):
        return out

    for entry in entries:
        changes = entry.get("changes") or []
        if not isinstance(changes, list):
            continue

        for change in changes:
            value = change.get("value") or {}
            messages = value.get("messages") or []
            if not isinstance(messages, list):
                continue

            contacts = value.get("contacts") or []
            wa_id = None
            if isinstance(contacts, list) and contacts:
                wa_id = (contacts[0] or {}).get("wa_id")

            for msg in messages:
                if not isinstance(msg, dict):
                    continue

                m_type = msg.get("type")
                if m_type != "button":
                    continue

                msg_id = msg.get("id")
                mphone = msg.get("from") or wa_id
                ts = msg.get("timestamp")

                button = msg.get("button") or {}
                btn_payload = button.get("payload")
                btn_text = button.get("text")
                if btn_payload is None and isinstance(btn_text, str):
                    btn_payload = btn_text

                out.append(
                    {
                        "message_id": str(msg_id) if msg_id is not None else None,
                        "phone": _normalize_phone(mphone),
                        "timestamp": ts,
                        # Dispatcher contract expects "button"
                        "message_type": "button",
                        "button_title": btn_text,
                        "button_payload": btn_payload,
                        "button_id": None,
                    }
                )

    return out


def _extract_events_whatsapp_text_message(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    """WhatsApp Cloud normal text messages.

    Shape:
      - entry[].changes[].value.messages[]
      - message["type"] == "text"

    For dispatcher/back-compat we normalize into a "button-like" event
    using the text body as both title and payload.
    """

    out: List[Dict[str, Any]] = []
    if not isinstance(payload, dict):
        return out

    entries = payload.get("entry") or []
    if not isinstance(entries, list):
        return out

    for entry in entries:
        changes = entry.get("changes") or []
        if not isinstance(changes, list):
            continue

        for change in changes:
            value = change.get("value") or {}
            messages = value.get("messages") or []
            if not isinstance(messages, list):
                continue

            contacts = value.get("contacts") or []
            wa_id = None
            if isinstance(contacts, list) and contacts:
                wa_id = (contacts[0] or {}).get("wa_id")

            for msg in messages:
                if not isinstance(msg, dict):
                    continue

                if msg.get("type") != "text":
                    continue

                msg_id = msg.get("id")
                mphone = msg.get("from") or wa_id
                ts = msg.get("timestamp")

                text = msg.get("text") or {}
                body = text.get("body")

                out.append(
                    {
                        "message_id": str(msg_id) if msg_id is not None else None,
                        "phone": _normalize_phone(mphone),
                        "timestamp": ts,
                        "message_type": "message",
                        "text": body,
                        # Treat these like button clicks so existing map_button_to_status works.
                        "button_title": body,
                        "button_payload": body,
                        "button_id": None,
                    }
                )

    return out



def parse_whatsapp_webhook_payload(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Parse inbound WhatsApp/Emovur payload into normalized events.

    IMPORTANT: This function is intentionally defensive and logs detailed
    diagnostics when no supported message events can be extracted.
    """

    import json

    events: List[Dict[str, Any]] = []

    attempted_parsers: List[str] = []
    parser_failures: List[Dict[str, Any]] = []

    def _record_failure(parser_name: str, reason: str, field: Optional[str] = None) -> None:
        attempted_parsers.append(parser_name)
        fail: Dict[str, Any] = {"parser": parser_name, "reason": reason}
        if field:
            fail["field"] = field
        parser_failures.append(fail)

    if not isinstance(payload, dict):
        _record_failure("root", "payload is not a dict")
        logger.warning("parse_whatsapp_webhook_payload: payload invalid type=%s", type(payload).__name__)
        return []

    # Log if we only receive statuses and nothing else.
    # Meta/Emovur can send many webhook notifications, including delivery/read statuses.
    only_statuses = isinstance(payload.get("statuses"), list) and not (
        isinstance(payload.get("messages"), list) or isinstance(payload.get("entry"), list)
    )

    # 1) Emovur-style: top-level messages[]
    try:
        attempted_parsers.append("_extract_events_emovur")
        if isinstance(payload, dict):
            events.extend(_extract_events_emovur(payload))
    except Exception as exc:
        _record_failure("_extract_events_emovur", f"exception: {exc.__class__.__name__}: {exc}")
        logger.exception("Failed to parse Emovur webhook events")

    # 2) WhatsApp Cloud interactive button replies
    try:
        attempted_parsers.append("_extract_events_interactive_button_reply")
        if isinstance(payload, dict) and payload.get("entry") is not None:
            events.extend(_extract_events_interactive_button_reply(payload))
        else:
            _record_failure(
                "_extract_events_interactive_button_reply",
                "missing entry/entry is None",
                field="entry",
            )
    except Exception as exc:
        _record_failure(
            "_extract_events_interactive_button_reply",
            f"exception: {exc.__class__.__name__}: {exc}",
        )
        logger.exception("Failed to parse WhatsApp Cloud interactive webhook events")

    # 3) WhatsApp Cloud non-interactive button replies
    try:
        attempted_parsers.append("_extract_events_whatsapp_cloud_button_reply")
        if isinstance(payload, dict) and payload.get("entry") is not None:
            events.extend(_extract_events_whatsapp_cloud_button_reply(payload))
        else:
            _record_failure(
                "_extract_events_whatsapp_cloud_button_reply",
                "missing entry/entry is None",
                field="entry",
            )
    except Exception as exc:
        _record_failure(
            "_extract_events_whatsapp_cloud_button_reply",
            f"exception: {exc.__class__.__name__}: {exc}",
        )
        logger.exception("Failed to parse WhatsApp Cloud button webhook events")

    # 4) WhatsApp Cloud normal text messages (button clicks converted to text)
    try:
        attempted_parsers.append("_extract_events_whatsapp_text_message")
        if isinstance(payload, dict) and payload.get("entry") is not None:
            events.extend(_extract_events_whatsapp_text_message(payload))
        else:
            _record_failure(
                "_extract_events_whatsapp_text_message",
                "missing entry/entry is None",
                field="entry",
            )
    except Exception as exc:
        _record_failure(
            "_extract_events_whatsapp_text_message",
            f"exception: {exc.__class__.__name__}: {exc}",
        )
        logger.exception("Failed to parse WhatsApp Cloud text webhook events")

    if events:

        logger.info(
            "parse_whatsapp_webhook_payload: matched parser(s) attempted=%s event_count=%s",
            attempted_parsers,
            len(events),
        )
        return events

    # If we reached here: no supported events parsed.
    # Requirement: If payload contains only "statuses", do not ignore silently.
    if only_statuses:
        try:
            logger.warning(
                "parse_whatsapp_webhook_payload: upstream sent only statuses; no incoming message/button events were found. payload_keys=%s statuses_count=%s",
                list(payload.keys()),
                len(payload.get("statuses") or []),
            )
            logger.warning(
                "parse_whatsapp_webhook_payload: full payload=%s",
                json.dumps(payload, indent=2, ensure_ascii=False),
            )
        except Exception:
            logger.warning("parse_whatsapp_webhook_payload: failed to json-dumps payload")

    # Detailed logging showing why parsing produced zero events.
    missing_fields: List[str] = []
    if "messages" not in payload:
        missing_fields.append("messages")
    if "entry" not in payload:
        missing_fields.append("entry")
    if "statuses" not in payload:
        missing_fields.append("statuses")

    try:
        logger.warning(
            "parse_whatsapp_webhook_payload: no_supported_events. attempted_parsers=%s failures=%s missing_fields=%s",
            attempted_parsers,
            parser_failures,
            missing_fields,
        )
        logger.warning(
            "parse_whatsapp_webhook_payload: full payload=%s",
            json.dumps(payload, indent=2, ensure_ascii=False),
        )
    except Exception:
        logger.warning("parse_whatsapp_webhook_payload: could not dump payload for diagnostics")

    return []





async def _idempotency_check_or_insert(

    db: AsyncSession, *, message_id: str, payload_hash: str
) -> Tuple[bool, Optional[WebhookEvent]]:
    try:
        res = await db.execute(select(WebhookEvent).where(WebhookEvent.message_id == message_id))
        row = res.scalar_one_or_none()
        if row is not None:
            return True, row
    except SQLAlchemyError:
        raise

    try:
        row = WebhookEvent(message_id=message_id, payload_hash=payload_hash)
        db.add(row)
        await db.flush()
        return False, row
    except IntegrityError:
        await db.rollback()
        return True, None


# ------------------------- Layered entrypoint -------------------------

async def process_event(*, payload: Dict[str, Any], db: AsyncSession) -> Dict[str, Any]:
    """Layered webhook entrypoint.

    Responsibilities:
      - normalize payload
      - determine event type
      - call dispatcher

    Note: handlers are responsible for sending WhatsApp replies.
    """

    from .event_dispatcher import dispatch

    logger.info(
        "services/webhook_service: process_event called payload_type=%s keys=%s",
        type(payload).__name__,
        list(payload.keys()) if isinstance(payload, dict) else None,
    )

    logger.info(
        "services/webhook_service: incoming payload received request_id=%s",
        payload.get("entry") if isinstance(payload, dict) else None,
    )

    async def _default_on_reply(event: Dict[str, Any]) -> None:
        logger.info("webhook callback invoked message_id=%s phone=%s", event.get("message_id"), event.get("phone"))

    async def _invoke_on_reply(event: Dict[str, Any]) -> None:
        callback = getattr(get_settings(), "on_reply_callback", None)
        if callable(callback):
            await callback(event)
            return
        await _default_on_reply(event)

    try:
        events = parse_whatsapp_webhook_payload(payload)
        logger.info(
            "services/webhook_service: normalized events count=%s",
            len(events) if events is not None else None,
        )


        if not events:
            return {"status": "no_supported_events"}

        results: List[Dict[str, Any]] = []
        for ev in events:
            message_id = ev.get("message_id")
            if not message_id:
                results.append({"status": "ignored_missing_message_id"})
                continue

            # Deduplicate by WhatsApp message_id only (true idempotency).
            # If a different webhook delivery arrives with a different message_id, it must NOT be ignored.
            payload_hash = hashlib.sha256(repr(payload).encode("utf-8")).hexdigest()
            is_dup, _ = await _idempotency_check_or_insert(db, message_id=str(message_id), payload_hash=payload_hash)
            if is_dup:
                results.append({"status": "duplicate_ignored", "message_id": str(message_id)})
                continue


            # IMPORTANT: persist idempotency only AFTER successful processing.
            # This ensures transient handler failures are retried instead of being
            # silently dropped forever.


            timestamp = _utc_from_unix(ev.get("timestamp")) or datetime.now(tz=timezone.utc)

            # Normalize/ensure dispatcher-compatible message_type.
            # Dispatcher expects exactly: "message" | "button" | "interactive" | "status".
            raw_message_type = ev.get("message_type")
            msg_type = raw_message_type
            if msg_type is None:
                # Infer from presence of button fields
                if ev.get("button_title") or ev.get("button_payload") or ev.get("button_id"):
                    # Prefer interactive if button_id exists (common for WhatsApp Cloud)
                    msg_type = "interactive" if ev.get("button_id") else "button"
                else:
                    msg_type = "message"

            # Best-effort mapping if upstream uses different casing
            if isinstance(msg_type, str):
                msg_type = msg_type.strip().lower()

            normalized_event = {
                "message_id": str(message_id),
                "phone": ev.get("phone"),
                "timestamp": timestamp,
                "message_type": msg_type,
                "button_title": ev.get("button_title"),
                "button_payload": ev.get("button_payload"),
                "button_id": ev.get("button_id"),
            }


            res = await dispatch(event=normalized_event, db=db)
            results.append(res)
            await _invoke_on_reply(normalized_event)

            # Only commit the idempotency row after the handler succeeds.
            # If dispatch raised, we will hit the outer exception handler and
            # the idempotency record will not be committed (so retries work).
            try:
                await db.commit()
            except SQLAlchemyError:
                await db.rollback()
                results.append({"status": "idempotency_commit_failed", "message_id": str(message_id)})


        return {"status": "ok", "results": results}

    except Exception as exc:
        await db.rollback()
        logger.exception("process_event fatal: %s", exc)
        return {"status": "fatal_error", "detail": str(exc)}


# ------------------------- Backward-compatible legacy API -------------------------

async def process_whatsapp_events(payload: Dict[str, Any], db: AsyncSession) -> List[WebhookProcessResult]:
    """Legacy API kept for backward compatibility.

    Internally delegates to the layered flow and maps results to the legacy
    WebhookProcessResult shape.
    """

    res = await process_event(payload=payload, db=db)
    results: List[WebhookProcessResult] = []

    if res.get("status") != "ok":
        return [WebhookProcessResult(status=res.get("status", "unknown"), detail=res.get("detail"))]

    for item in res.get("results") or []:
        results.append(
            WebhookProcessResult(
                status=item.get("status", "unknown"),
                message_id=item.get("message_id"),
                phone=item.get("phone"),
                button_title=item.get("button_title"),
                button_payload=item.get("button_payload"),
                button_id=item.get("button_id"),
                candidate_id=item.get("candidate_id"),
                detail=item.get("detail"),
            )
        )

    return results


__all__ = [
    "WebhookProcessResult",
    "parse_whatsapp_webhook_payload",
    "process_whatsapp_events",
    "process_event",
]

