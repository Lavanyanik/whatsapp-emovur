from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse

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
settings = get_settings()


def require_messages_auth(request: Request) -> None:
    expected_token = getattr(settings, "messages_auth_token", None) or getattr(settings, "api_key", None)
    if not expected_token:
        raise HTTPException(status_code=500, detail="server_misconfigured")

    provided = request.headers.get("X-API-Key")
    if not provided:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            provided = auth_header[len("Bearer "):].strip()

    if provided != expected_token:
        raise HTTPException(status_code=401, detail="unauthorized")


@router.post(
    "/messages",
    response_model=MessageResponse,
    status_code=status.HTTP_200_OK,
    summary="Send a WhatsApp message through Emovur",
    description="Generic capability-based endpoint for sending WhatsApp template, text, image, document, video, audio, and interactive messages via Emovur.",
)
async def send_message_route(payload: MessageRequest, _auth: None = Depends(require_messages_auth)):
    logger.info("/messages route entered payload=%s", payload)

    try:
        if payload.type == "template":
            logger.info(
                "Template send request to=%s template_name=%s language=%s components=%s",
                payload.to,
                payload.template_name,
                payload.language,
                payload.components,
            )
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
        logger.exception("Emovur request failed for to=%s: %s", payload.to, exc)
        return JSONResponse(
            status_code=504,
            content={"detail": "emovur_request_timeout", "error": str(exc)},
        )
    except TemplateLookupError as exc:
        logger.exception("Template lookup failed for to=%s template=%s: %s", payload.to, payload.template_name, exc)
        return JSONResponse(
            status_code=404,
            content={"detail": "template_not_found", "error": str(exc)},
        )
    except EmovurError as exc:
        logger.exception("Emovur API returned an error for to=%s: %s", payload.to, exc)
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
