from __future__ import annotations

import hashlib
import hmac
import json
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Query, Request, Response

from ..config import get_settings
from ..database import AsyncSessionLocal
from ..services.webhook_service import process_event, parse_whatsapp_webhook_payload
from ..utils.logger import get_logger


logger = get_logger(__name__)

router = APIRouter()
settings = get_settings()


def _compute_signature(secret: str, body: bytes) -> str:
    digest = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


def _verify_signature(signature_header: Optional[str], secret: str, body: bytes) -> bool:
    if not signature_header:
        return False
    expected = _compute_signature(secret, body)
    return hmac.compare_digest(signature_header, expected)


def _redact_headers(headers: Dict[str, str]) -> Dict[str, str]:
    out: Dict[str, str] = {}
    for k, v in headers.items():
        if k.lower() in {"api-key", "authorization", "x-hub-signature-256"}:
            out[k] = "<redacted>"
        else:
            out[k] = v
    return out


def _parse_json_body(raw_body: bytes) -> Optional[Dict[str, Any]]:
    if not raw_body:
        return None
    try:
        parsed = json.loads(raw_body.decode("utf-8"))
        if isinstance(parsed, dict):
            return parsed
    except Exception:
        logger.exception("Failed to parse webhook JSON body")
    return None


def _extract_log_fields(payload: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    phone = None
    message_type = None
    button_id = None
    button_title = None

    if isinstance(payload, dict):
        try:
            events = parse_whatsapp_webhook_payload(payload)
            if events:
                first_event = events[0]
                phone = first_event.get("phone")
                message_type = first_event.get("message_type")
                button_id = first_event.get("button_id")
                button_title = first_event.get("button_title")
        except Exception:
            logger.exception("Failed to extract webhook log fields")

    return {
        "phone": phone,
        "message_type": message_type,
        "button_id": button_id,
        "button_title": button_title,
    }


@router.get("/webhook", tags=["webhook"], summary="Webhook verification")
async def verify_webhook(
    hub_mode: Optional[str] = Query(None, alias="hub.mode"),
    hub_challenge: Optional[str] = Query(None, alias="hub.challenge"),
    hub_verify_token: Optional[str] = Query(None, alias="hub.verify_token"),
):
    expected = settings.verify_token
    if expected is None:
        logger.error("VERIFY_TOKEN not configured")
        raise HTTPException(status_code=500, detail="server_misconfigured")

    if hub_verify_token != expected:
        logger.warning(
            "Invalid webhook verify token received=%s expected=<redacted> mode=%s",
            hub_verify_token,
            hub_mode,
        )
        raise HTTPException(status_code=403, detail="invalid_verify_token")

    if hub_challenge is None:
        raise HTTPException(status_code=400, detail="missing_hub_challenge")

    logger.info(
        "routes/webhook: GET /webhook verification success mode=%s challenge=%s",
        hub_mode,
        hub_challenge,
    )
    return Response(content=str(hub_challenge), media_type="text/plain")


@router.post("/webhook", tags=["webhook"], summary="Receive webhook events")
async def receive_webhook(request: Request) -> Dict[str, Any]:
    """Webhook route (controller).

    Responsibilities:
      - receive webhook
      - verify signature (optional)
      - parse/normalize payload (best-effort)
      - call webhook_service.process_event(...) (always awaited)
      - log full payload + key extracted fields
      - always return HTTP 200 on successful processing
    """

    request_id = request.headers.get("X-Request-Id")

    try:
        raw_body: bytes = await request.body()
    except Exception:
        logger.exception("routes/webhook: failed to read request body request_id=%s", request_id)
        raw_body = b""

    payload = _parse_json_body(raw_body)
    fields = _extract_log_fields(payload)

    print(f"\n===DEBUG: WEBHOOK HIT request_id={request_id}===")
    print(f"DEBUG: payload={payload}")
    print(f"DEBUG: fields={fields}")
    
    logger.info("=== WEBHOOK HIT ===")
    logger.info("Full request JSON: %s", payload)

    # Deep structure debug before any parsing decisions.
    try:
        if isinstance(payload, dict):
            logger.info("webhook_debug payload_keys=%s", list(payload.keys()))

            entry_val = payload.get("entry")
            logger.info("webhook_debug payload_entry_type=%s entry_is_list=%s", type(entry_val).__name__, isinstance(entry_val, list))
            logger.info("webhook_debug payload_entry=%s", entry_val)

            if isinstance(entry_val, list) and entry_val:
                first_entry = entry_val[0] if isinstance(entry_val[0], dict) else {}
                changes_val = first_entry.get("changes")
                if isinstance(changes_val, list) and changes_val:
                    first_change = changes_val[0] if isinstance(changes_val[0], dict) else {}
                    value_val = first_change.get("value")
                    if isinstance(value_val, dict):
                        logger.info(
                            "webhook_debug entry0_changes0_value_keys=%s",
                            list(value_val.keys()),
                        )
                        logger.info("webhook_debug entry0_changes0_value_messages=%s", value_val.get("messages"))
                        logger.info("webhook_debug entry0_changes0_value_statuses=%s", value_val.get("statuses"))
                    else:
                        logger.info("webhook_debug entry0_changes0_value_missing_or_not_dict type=%s", type(value_val).__name__)
                else:
                    logger.info("webhook_debug entry0_changes_missing_or_not_list type=%s", type(changes_val).__name__)
        else:
            logger.info("webhook_debug payload_not_dict type=%s", type(payload).__name__)
    except Exception:
        logger.exception("webhook_debug failed")

    logger.info("Phone number: %s", fields["phone"])
    logger.info("Message type: %s", fields["message_type"])
    logger.info("Button ID: %s", fields["button_id"])
    logger.info("Button title: %s", fields["button_title"])


    try:
        logger.info(
            "routes/webhook: POST /webhook hit request_id=%s headers=%s",
            request_id,
            _redact_headers(dict(request.headers)),
        )
        logger.info(
            "routes/webhook: POST /webhook raw_body_bytes=%s raw_body_preview=%s",
            len(raw_body or b""),
            (raw_body or b"")[:1500].decode("utf-8", errors="replace"),
        )

        signature_header = request.headers.get("X-Hub-Signature-256")
        if settings.enable_webhook_signature_verification:
            app_secret = settings.whatsapp_app_secret
            if not app_secret:
                logger.error(
                    "WHATSAPP_APP_SECRET not configured while signature verification is enabled request_id=%s",
                    request_id,
                )
                raise HTTPException(status_code=500, detail="server_misconfigured")

            signature_ok = _verify_signature(signature_header, app_secret, raw_body)
            logger.info(
                "routes/webhook: signature verification enabled request_id=%s signature_ok=%s",
                request_id,
                signature_ok,
            )
            if not signature_ok:
                raise HTTPException(status_code=403, detail="invalid_signature")

        if payload is None:
            raise HTTPException(status_code=400, detail="invalid_json")

        logger.info("routes/webhook: POST /webhook parsed payload=%s", payload)

        extracted_fields: Dict[str, Any] = {}
        try:
            events_for_log = parse_whatsapp_webhook_payload(payload)
            logger.info(
                "routes/webhook: parse_whatsapp_webhook_payload events_for_log=%s",
                events_for_log,
            )
            extracted_fields = {
                "events_count": len(events_for_log),
                "first_event": events_for_log[0] if events_for_log else None,
            }
        except Exception:
            logger.exception("routes/webhook: parse_whatsapp_webhook_payload failed request_id=%s", request_id)

        logger.info("routes/webhook: extracted_fields=%s", extracted_fields)

        async with AsyncSessionLocal() as db:
            try:
                logger.info(
                    "routes/webhook: calling services.webhook_service.process_event request_id=%s",
                    request_id,
                )
                res = await process_event(payload=payload, db=db)
                logger.info("routes/webhook: process_event result request_id=%s res=%s", request_id, res)
            except Exception:
                logger.exception("routes/webhook: webhook processing error request_id=%s", request_id)

        return {"status": "ok"}

    except HTTPException:
        raise
    except Exception:
        logger.exception("routes/webhook: Fatal webhook controller error request_id=%s", request_id)
        return {"status": "fatal_error_ignored"}
