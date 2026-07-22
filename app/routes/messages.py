import hmac

from fastapi import APIRouter, Depends, HTTPException, Security, status
from fastapi.responses import JSONResponse
from fastapi.security import APIKeyHeader

from ..config import get_settings
from ..schemas import MessageRequest, MessageResponse
from ..services.emovur_service import (
    EmovurError,
    EmovurRequestError,
    send_audio,
    send_document,
    send_image,
    send_interactive,
    send_template,
    send_text,
    send_video,
)
from ..services.template_service import TemplateLookupError
from ..utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter()

# ------------------------------------------------------------------
# OpenAPI security scheme — enables the "Authorize" button in Swagger
# ------------------------------------------------------------------
_api_key_scheme = APIKeyHeader(
    name="X-API-Key",
    auto_error=False,
    description="Messages API token from MESSAGES_AUTH_TOKEN or API_KEY env var",
)


def _check_token(api_key: str | None) -> None:
    """Core authentication check — raise if *api_key* doesn't match the configured token."""
    settings = get_settings()
    expected_token = settings.messages_auth_token or settings.api_key
    logger.debug("Auth check: api_key_present=%s", api_key is not None)
    if not expected_token:
        raise HTTPException(status_code=500, detail="server_misconfigured")
    if not api_key or not hmac.compare_digest(api_key, expected_token):
        raise HTTPException(status_code=401, detail="unauthorized")


async def require_messages_auth(
    api_key: str | None = Security(_api_key_scheme),
) -> None:
    """FastAPI security dependency — validates ``X-API-Key`` header.

    Using ``Security()`` (instead of ``Depends()``) registers this scheme in
    OpenAPI so that Swagger UI shows an **Authorize** button where users can
    paste their token.  The token is compared (constant-time) against
    ``MESSAGES_AUTH_TOKEN``, falling back to ``API_KEY`` for backward
    compatibility.
    """
    logger.debug("Auth dependency: api_key_present=%s", api_key is not None)
    _check_token(api_key=api_key)


@router.post(
    "/messages",
    response_model=MessageResponse,
    status_code=status.HTTP_200_OK,
    summary="Send a WhatsApp message",
    description="Send a WhatsApp template, text, image, document, video, audio, or interactive message.",
)
async def send_message_route(
    payload: MessageRequest,
    _auth: None = Depends(require_messages_auth),
):
    logger.info("ENTER send_message_route")
    logger.info("Message send requested type=%s", payload.type)

    try:
        if payload.type == "template":
            result = await send_template(
                to=payload.to,
                template_name=payload.template_name,
                language=payload.language,
                components=payload.components,
            )
        elif payload.type == "text":
            result = await send_text(to=payload.to, text=payload.text)
        elif payload.type == "image":
            result = await send_image(to=payload.to, media_id=payload.media_id, caption=payload.caption)
        elif payload.type == "document":
            result = await send_document(to=payload.to, media_id=payload.media_id, caption=payload.caption)
        elif payload.type == "video":
            result = await send_video(to=payload.to, media_id=payload.media_id, caption=payload.caption)
        elif payload.type == "audio":
            result = await send_audio(to=payload.to, media_id=payload.media_id)
        elif payload.type == "interactive":
            result = await send_interactive(to=payload.to, interactive=payload.interactive)
        else:
            raise HTTPException(status_code=400, detail=f"unsupported message type: {payload.type}")
    except EmovurRequestError as exc:
        logger.exception("Emovur request failed")
        return JSONResponse(
            status_code=504,
            content={"detail": "emovur_request_timeout", "error": str(exc)},
        )
    except TemplateLookupError as exc:
        logger.exception("Template lookup failed")
        return JSONResponse(
            status_code=404,
            content={"detail": "template_not_found", "error": str(exc)},
        )
    except EmovurError as exc:
        logger.exception("Emovur API returned an error")
        status_code = getattr(exc, "status_code", 502) or 502
        if status_code == 404:
            status_code = 502
        return JSONResponse(
            status_code=status_code,
            content={
                "detail": "emovur_api_error",
                "error": str(exc),
                "upstream_status_code": getattr(exc, "status_code", None),
                "upstream_body": getattr(exc, "body", None),
            },
        )

    return MessageResponse(status="ok", upstream_status_code=result["status_code"], data=result["body"])
