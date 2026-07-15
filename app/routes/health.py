from __future__ import annotations

from fastapi import APIRouter

router = APIRouter()


@router.get("/", tags=["health"], summary="Root status")
async def root():
    return {"status": "ok", "service": "whatsapp-backend", "message": "WhatsApp integration backend is running"}


@router.get("/health", tags=["health"], summary="Health check")
async def health():
    return {"status": "ok", "service": "whatsapp-backend"}


@router.get("/version", tags=["health"], summary="Application version")
async def version():
    return {"status": "ok", "version": "0.1.0"}

