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
    digest = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


def _verify_signature(signature_header: Optional[str], secret: str, body: bytes) -> bool:
    if not signature_header:
        return False
    expected = _compute_signature(secret, body)
    return hmac.compare_digest(signature_header, expected)


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


@router.get("/webhook", tags=["webhook"], summary="Webhook verification")
async def verify_webhook(
    hub_mode: Optional[str] = Query(None, alias="hub.mode"),
    hub_challenge: Optional[str] = Query(None, alias="hub.challenge"),
    hub_verify_token: Optional[str] = Query(None, alias="hub.verify_token"),
):
    expected = get_settings().verify_token
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
      - verify the Meta signature
      - parse/normalize payload (best-effort)
      - call webhook_service.process_event(...) (always awaited)
      - log request metadata and extracted fields
      - always return HTTP 200 on successful processing
    """

    request_id = request.headers.get("X-Request-Id")

    try:
        raw_body: bytes = await request.body()
    except Exception:
        logger.exception("routes/webhook: failed to read request body request_id=%s", request_id)
        raw_body = b""

    payload = _parse_json_body(raw_body)

    try:
        logger.info("routes/webhook: POST /webhook hit request_id=%s", request_id)
        signature_header = request.headers.get("X-Hub-Signature-256")
        settings = get_settings()
        if settings.enable_webhook_signature_verification:
            app_secret = settings.whatsapp_app_secret or getattr(settings, "api_key", None)
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

        async with AsyncSessionLocal() as db:
            try:
                await process_event(payload=payload, db=db)
            except Exception:
                logger.exception("routes/webhook: webhook processing error request_id=%s", request_id)

        return {"status": "ok"}

    except HTTPException:
        raise
    except Exception:
        logger.exception("routes/webhook: Fatal webhook controller error request_id=%s", request_id)
        return {"status": "fatal_error_ignored"}

