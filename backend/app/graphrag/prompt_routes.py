"""
AMASCI Prompt Composer REST API Routes
=======================================
Endpoints for composing structured 10-component deterministic prompts for LLM reasoning.
Guarantees zero raw graph data leakage.
"""

import logging
from typing import Any
from fastapi import APIRouter, HTTPException, Query, Body

from app.graphrag.prompt_composer import PromptComposerService
from app.graphrag.context_builder.service import ContextBuilderService
from app.schemas import BaseResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/prompt-composer", tags=["Prompt Composer"])

_composer: PromptComposerService | None = None
_context_builder: ContextBuilderService | None = None


def _get_composer() -> PromptComposerService:
    global _composer
    if _composer is None:
        _composer = PromptComposerService()
    return _composer


def _get_context_builder() -> ContextBuilderService:
    global _context_builder
    if _context_builder is None:
        _context_builder = ContextBuilderService()
    return _context_builder


@router.get("/compose", response_model=BaseResponse[dict[str, Any]])
async def compose_prompt_get(
    query: str = Query(default="Why is supplier delay elevated?", description="User query"),
    entity_id: str = Query(default="SUP_001", description="Entity node ID"),
    entity_label: str = Query(default="Supplier", description="Entity label"),
) -> BaseResponse[dict[str, Any]]:
    """Compose structured 10-component prompt (GET)."""
    try:
        cb = _get_context_builder()
        context = await cb.build_unified_context(entity_id=entity_id, entity_label=entity_label, query=query)
        composer = _get_composer()
        payload = composer.compose_prompt(query=query, intent="root_cause", context_dict=context.to_dict())
        return BaseResponse(
            success=True,
            message="Composed deterministic prompt successfully",
            data=payload.to_dict(),
        )
    except Exception as e:
        logger.error(f"Prompt composition failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/compose", response_model=BaseResponse[dict[str, Any]])
async def compose_prompt_post(
    payload_in: dict[str, Any] = Body(...),
) -> BaseResponse[dict[str, Any]]:
    """Compose structured 10-component prompt (POST)."""
    query = payload_in.get("query", "Why is supplier delay elevated?")
    entity_id = payload_in.get("entity_id", "SUP_001")
    entity_label = payload_in.get("entity_label", "Supplier")
    try:
        cb = _get_context_builder()
        context = await cb.build_unified_context(entity_id=entity_id, entity_label=entity_label, query=query)
        composer = _get_composer()
        payload = composer.compose_prompt(query=query, intent="root_cause", context_dict=context.to_dict())
        return BaseResponse(
            success=True,
            message="Composed deterministic prompt successfully",
            data=payload.to_dict(),
        )
    except Exception as e:
        logger.error(f"Prompt composition failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
