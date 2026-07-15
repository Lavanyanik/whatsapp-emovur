from __future__ import annotations

from typing import List, Dict

from fastapi import APIRouter

from ..services.template_service import list_approved_templates



router = APIRouter()


@router.get("/templates", tags=["templates"], summary="List approved Emovur templates")
async def list_templates() -> List[Dict[str, str]]:
    return await list_approved_templates()

