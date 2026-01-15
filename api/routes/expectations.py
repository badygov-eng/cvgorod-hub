"""
Expectations API routes.
"""

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query

from api.auth import verify_api_key
from services.expectations import analyze_expectations, load_cache

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chats", tags=["expectations"])


@router.get("/expectations")
async def get_expectations(
    _: str = Depends(verify_api_key),
) -> dict[str, Any]:
    """Get expectations cache for all chats."""
    cache = load_cache()
    return {
        "updated_at": cache.get("updated_at"),
        "stats": cache.get("stats", {}),
        "chats": cache.get("chats", {}),
    }


@router.get("/expectations/{chat_id}")
async def get_expectations_for_chat(
    chat_id: int,
    _: str = Depends(verify_api_key),
) -> dict[str, Any]:
    """Get expectations cache for a single chat."""
    cache = load_cache()
    chat_key = str(chat_id)
    if chat_key not in cache.get("chats", {}):
        raise HTTPException(status_code=404, detail="Chat expectation not found")
    return {
        "updated_at": cache.get("updated_at"),
        "chat_id": chat_id,
        "expectation": cache["chats"][chat_key],
    }


@router.post("/expectations/refresh")
async def refresh_expectations(
    force: bool = Query(False, description="Force re-analysis even without new messages"),
    limit: int | None = Query(None, ge=1, le=200, description="Limit number of chats"),
    dry_run: bool = Query(False, description="Run without saving cache"),
    _: str = Depends(verify_api_key),
) -> dict[str, Any]:
    """Trigger expectations refresh (for manual testing)."""
    try:
        result = await analyze_expectations(
            force=force,
            limit=limit,
            dry_run=dry_run,
        )
    except Exception as exc:
        logger.error("Expectations refresh failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to refresh expectations") from exc

    return {
        "updated_at": result.get("updated_at"),
        "stats": result.get("stats", {}),
        "chats_count": len(result.get("chats", {})),
        "dry_run": dry_run,
    }
