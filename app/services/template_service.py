"""Template discovery and caching for WhatsApp message templates.

Production requirements implemented:
- Fetch templates using the configured provider's fetch_templates()
- Persist essential template fields in memory
- Find templates by display name (case-insensitive)
- Auto-select if API returns a single approved template similar to requested name
- Cache lookup results for 30 minutes with refresh on expiry
- Never crash send flow when lookup fails; log approved templates instead
- Detect Emovur error code 132001 (template name does not exist) and refresh+retry once
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
import asyncio

from ..providers.factory import ProviderFactory
from ..utils.logger import get_logger


logger = get_logger(__name__)


@dataclass(frozen=True)
class TemplateRecord:
    id: str
    name: str
    language: str
    status: str
    category: Optional[str]
    components: Optional[Any]


class TemplateLookupError(Exception):
    """Raised when a matching template cannot be found."""


# In-memory cache (single-process)
_TEMPLATE_CACHE: Optional[List[TemplateRecord]] = None
_CACHE_EXPIRES_AT: Optional[datetime] = None
_CACHE_LOCK = asyncio.Lock()


def _normalize_name(s: str) -> str:
    return (s or "").strip().lower()


def _looks_similar(requested: str, candidate: str) -> bool:
    """Heuristic similarity: equality after common transformations.

    Emovur display names often differ only by snake_case vs title case.
    """

    req = _normalize_name(requested)
    cand = _normalize_name(candidate)

    if not req or not cand:
        return False

    # Exact after stripping common punctuation/underscores/spaces
    def compact(x: str) -> str:
        return "".join(ch for ch in x if ch.isalnum())

    return compact(req) == compact(cand)


def _dict_to_template_record(t: Dict[str, Any]) -> TemplateRecord:
    return TemplateRecord(
        id=str(t.get("id") or ""),
        name=str(t.get("name") or ""),
        language=str(t.get("language") or ""),
        status=str(t.get("status") or ""),
        category=str(t["category"]) if t.get("category") is not None else None,
        components=t.get("components"),
    )


async def _fetch_all_templates(timeout: int = 10) -> List[TemplateRecord]:
    """Fetch templates from the configured provider."""
    provider = ProviderFactory.create()
    raw_templates = await provider.fetch_templates(timeout=timeout)
    return [_dict_to_template_record(t) for t in raw_templates]


async def refresh_templates_if_needed(force: bool = False) -> List[TemplateRecord]:
    global _TEMPLATE_CACHE, _CACHE_EXPIRES_AT

    async with _CACHE_LOCK:
        now = datetime.utcnow()
        if not force and _TEMPLATE_CACHE is not None and _CACHE_EXPIRES_AT is not None:
            if now < _CACHE_EXPIRES_AT:
                return _TEMPLATE_CACHE

        templates = await _fetch_all_templates()

        _TEMPLATE_CACHE = templates
        _CACHE_EXPIRES_AT = now + timedelta(minutes=30)

        return templates


async def get_template(requested_display_name: str, preferred_language: Optional[str] = None) -> Dict[str, str]:
    """Return template_name and language_code for a matching approved template.

    - Case-insensitive match on display name.
    - If multiple languages exist, preferred_language is used when present.
    - If the API returns only one approved template and name is similar, auto-select.
    - If no approved templates available, raises TemplateLookupError with helpful message.
    """

    templates = await refresh_templates_if_needed(force=False)

    approved = [t for t in templates if str(t.status).lower() == "approved"]

    if not approved:
        _log_approved_templates(templates)
        all_templates_info = [f"- name={t.name} status={t.status}" for t in templates]
        error_msg = f"No approved templates available. Total templates found: {len(templates)}. "
        if all_templates_info:
            error_msg += f"Available templates: {', '.join(all_templates_info)}"
        else:
            error_msg += "No templates found in cache. Check Emovur API connection and template approval status."
        raise TemplateLookupError(error_msg)

    target_norm = _normalize_name(requested_display_name)

    # Step 3: exact match by display name equivalence
    exact_matches: List[TemplateRecord] = []
    for t in approved:
        if _normalize_name(t.name) == target_norm:
            exact_matches.append(t)

    if exact_matches:
        chosen = _select_by_preferred_language(exact_matches, preferred_language)
        return {"template_name": chosen.name, "language_code": chosen.language}

    # Step 4: if only one approved template and name looks similar, use it
    if len(approved) == 1:
        only = approved[0]
        if _looks_similar(requested_display_name, only.name) or _looks_similar(requested_display_name, only.id):
            logger.info(
                "Auto-selecting only approved template: requested=%s found=%s",
                requested_display_name,
                only.name,
            )
            return {"template_name": only.name, "language_code": only.language}

    # Step 5: provide helpful error with available approved templates
    approved_names = [t.name for t in approved]
    _log_approved_templates(approved)
    raise TemplateLookupError(
        f"Template '{requested_display_name}' not found. "
        f"Available approved templates: {', '.join(approved_names)}. "
        f"Please check template name spelling and approval status in Emovur."
    )


def _select_by_preferred_language(candidates: List[TemplateRecord], preferred_language: Optional[str]) -> TemplateRecord:
    if not preferred_language:
        return candidates[0]
    pref = preferred_language.strip().lower()
    for c in candidates:
        if str(c.language).strip().lower() == pref:
            return c
    return candidates[0]


def _log_approved_templates(templates: List[TemplateRecord]) -> None:
    approved = [t for t in templates if str(t.status).lower() == "approved"]
    if not approved:
        logger.warning("Approved templates: <none>")
        return

    logger.warning("Approved templates:")
    for t in approved:
        logger.warning("- name=%s language=%s status=%s", t.name, t.language, t.status)


def _is_emovur_132001(error_body: Any) -> bool:
    # Emovur error formats can vary; we check common shapes.
    if not isinstance(error_body, dict):
        return False

    # Common: {"error":{"code":132001,...}}
    err = error_body.get("error")
    if isinstance(err, dict):
        code = err.get("code")
        if str(code) == "132001":
            return True

    # Common: top-level code
    code = error_body.get("code")
    if str(code) == "132001":
        return True

    # Fallback: string containment
    msg = str(error_body)
    return "132001" in msg


async def refresh_templates_once_and_get_template(requested_display_name: str, preferred_language: Optional[str] = None) -> Dict[str, str]:
    # Force refresh and attempt lookup again.
    await refresh_templates_if_needed(force=True)
    return await get_template(requested_display_name, preferred_language=preferred_language)


async def list_approved_templates() -> List[Dict[str, str]]:
    templates = await refresh_templates_if_needed(force=False)
    approved = [t for t in templates if str(t.status).lower() == "approved"]
    return [
        {"id": t.id, "name": t.name, "language": t.language, "status": t.status}
        for t in approved
    ]


__all__ = [
    "get_template",
    "refresh_templates_if_needed",
    "refresh_templates_once_and_get_template",
    "list_approved_templates",
    "TemplateLookupError",
    "_is_emovur_132001",
]

