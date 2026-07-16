"""Application entrypoint for the generic WhatsApp integration backend."""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError

from .config import get_settings, validate_settings
from .database import init_db
from .routes.health import router as health_router
from .routes.webhook import router as webhook_router
from .routes.messages import router as messages_router
from .routes.templates import router as templates_router
from .utils.logger import get_logger

from .services.template_service import refresh_templates_if_needed

from .services.emovur_exceptions import (
    EmovurAuthError,
    EmovurRateLimitError,
    EmovurServerError,
    EmovurRequestError,
)
from .middleware.logging_middleware import LoggingMiddleware

settings = get_settings()
logger = get_logger("app.main")






@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting app, validating configuration")

    validate_settings(settings)
    await init_db()

    # Pre-warm template cache so /messages has approved templates ready.
    try:
        templates = await refresh_templates_if_needed(force=True)
        approved = [t for t in templates if str(t.status).lower() == "approved"]
        logger.info(
            "Template cache warmed: total=%s approved=%s dry_run=%s",
            len(templates),
            len(approved),
            settings.emovur_dry_run,
        )
        for t in approved:
            logger.info("Approved template: name=%s language=%s", t.name, t.language)
    except Exception:
        logger.warning("Template cache warm-up unavailable; continuing without cached templates")




    yield


app = FastAPI(

    title="WhatsApp Integration Backend",
    description="Generic WhatsApp messaging backend using Emovur API.",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(LoggingMiddleware)
app.include_router(health_router)
app.include_router(webhook_router)
app.include_router(messages_router)
app.include_router(templates_router)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    logger.warning("Validation error for %s: %s", request.url, exc)
    return JSONResponse(status_code=400, content={"detail": exc.errors()})


@app.exception_handler(EmovurAuthError)
async def emovur_auth_exception_handler(request: Request, exc: EmovurAuthError):
    logger.warning("Emovur auth error for %s: %s", request.url, exc)
    return JSONResponse(status_code=401, content={"detail": "upstream_auth_error"})


@app.exception_handler(EmovurRateLimitError)
async def emovur_rate_limit_handler(request: Request, exc: EmovurRateLimitError):
    logger.warning("Emovur rate limit for %s: %s", request.url, exc)
    return JSONResponse(status_code=429, content={"detail": "upstream_rate_limited"})


@app.exception_handler(EmovurServerError)
async def emovur_server_error_handler(request: Request, exc: EmovurServerError):
    logger.warning("Emovur server error for %s: %s", request.url, exc)
    return JSONResponse(status_code=502, content={"detail": "upstream_server_error"})


@app.exception_handler(EmovurRequestError)
async def emovur_request_error_handler(request: Request, exc: EmovurRequestError):
    logger.warning("Emovur request error for %s: %s", request.url, exc)
    return JSONResponse(status_code=503, content={"detail": "upstream_unavailable"})


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled error for request %s: %s", request.url, exc)
    return JSONResponse(status_code=500, content={"detail": "internal_server_error"})
