from __future__ import annotations

import hashlib
import hmac
import json
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Query, Request, Response

from ..config import get_settings
from ..database import AsyncSessionLocal
from ..services.webhook_service import process_event
from ..utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter()


def _compute_signature(secret: str, body: bytes) -> str:
    digest = hmac.new(
        secret.encode("utf-8"),
        body,
        hashlib.sha256,
    ).hexdigest()
    return f"sha256={digest}"


def _verify_signature(
    signature_header: Optional[str],
    secret: str,
    body: bytes,
) -> bool:
    if not signature_header:
        return False

    expected = _compute_signature(secret, body)
    return hmac.compare_digest(signature_header, expected)


def _parse_json_body(raw_body: bytes) -> Optional[Dict[str, Any]]:
    if not raw_body:
        return None

    try:
        payload = json.loads(raw_body.decode("utf-8"))
        if isinstance(payload, dict):
            return payload
    except Exception:
        logger.exception("Failed to parse webhook payload")

    return None


# --------------------------------------------------------------------------
# GET /webhook
# Meta verification endpoint
# --------------------------------------------------------------------------
@router.get("/webhook", tags=["webhook"])
async def verify_webhook(
    hub_mode: Optional[str] = Query(None, alias="hub.mode"),
    hub_challenge: Optional[str] = Query(None, alias="hub.challenge"),
    hub_verify_token: Optional[str] = Query(None, alias="hub.verify_token"),
):
    settings = get_settings()
    expected = settings.verify_token

    logger.info("========== WEBHOOK VERIFICATION ==========")
    logger.info("Expected token present: %s", expected is not None)
    logger.info("Received token present: %s", hub_verify_token is not None)
    logger.info("Mode           : %r", hub_mode)
    logger.info("Challenge      : %r", hub_challenge)

    if expected is None or expected == "":
        logger.error("VERIFY_TOKEN is not configured.")
        raise HTTPException(
            status_code=500,
            detail="VERIFY_TOKEN not configured",
        )

    if hub_verify_token != expected:
        logger.error("Webhook verification failed (tokens do not match)")

        raise HTTPException(
            status_code=403,
            detail="invalid_verify_token",
        )

    logger.info("Webhook verification successful.")

    return Response(
        content=str(hub_challenge),
        media_type="text/plain",
    )


# --------------------------------------------------------------------------
# POST /webhook
# Receive WhatsApp events
# --------------------------------------------------------------------------
@router.post("/webhook", tags=["webhook"])
async def receive_webhook(request: Request):

    request_id = request.headers.get("X-Request-Id")

    try:
        raw_body = await request.body()
    except Exception:
        logger.exception(
            "Failed reading request body request_id=%s",
            request_id,
        )
        raise HTTPException(status_code=400, detail="invalid_request")

    payload = _parse_json_body(raw_body)

    if payload is None:
        raise HTTPException(
            status_code=400,
            detail="invalid_json",
        )

    settings = get_settings()

    if settings.enable_webhook_signature_verification:

        app_secret = settings.whatsapp_app_secret

        if not app_secret:
            logger.error("WHATSAPP_APP_SECRET is missing.")
            raise HTTPException(
                status_code=500,
                detail="missing_app_secret",
            )

        signature = request.headers.get("X-Hub-Signature-256")

        signature_ok = _verify_signature(
            signature,
            app_secret,
            raw_body,
        )

        logger.info(
            "Signature verification result: %s",
            signature_ok,
        )

        if not signature_ok:
            raise HTTPException(
                status_code=403,
                detail="invalid_signature",
            )

    try:
        async with AsyncSessionLocal() as db:
            await process_event(
                payload=payload,
                db=db,
            )

    except Exception:
        logger.exception("Webhook processing failed")

    return {"status": "ok"}