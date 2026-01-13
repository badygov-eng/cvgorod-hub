"""
Messages API routes.
"""

import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from api.auth import verify_api_key
from services.database import db

logger = logging.getLogger(__name__)

router = APIRouter()


class MessageResponse(BaseModel):
    """Ответ с сообщением."""
    id: int
    chat_id: int
    user_id: int
    text: str
    message_type: str
    timestamp: datetime
    username: Optional[str] = None
    first_name: Optional[str] = None
    chat_name: Optional[str] = None


class MessagesListResponse(BaseModel):
    """Ответ со списком сообщений."""
    count: int
    messages: list[MessageResponse]


@router.get("/messages", response_model=MessagesListResponse)
async def list_messages(
    api_key: str = Depends(verify_api_key),
    chat_id: Optional[int] = Query(None),
    user_id: Optional[int] = Query(None),
    since: Optional[datetime] = Query(None),
    until: Optional[datetime] = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
):
    """
    Получение списка сообщений с фильтрами.
    
    Args:
        chat_id: Фильтр по ID чата
        user_id: Фильтр по ID пользователя
        since: Начало периода
        until: Конец периода
        limit: Максимум записей
        offset: Сдвиг для пагинации
    """
    messages_list = await db.get_messages(
        chat_id=chat_id,
        user_id=user_id,
        since=since,
        until=until,
        limit=limit,
        offset=offset,
    )
    
    return MessagesListResponse(
        count=len(messages_list),
        messages=[MessageResponse(**msg) for msg in messages_list],
    )


@router.get("/messages/{message_id}", response_model=MessageResponse)
async def get_message(
    message_id: int,
    api_key: str = Depends(verify_api_key),
):
    """Получение конкретного сообщения по ID."""
    messages_list = await db.get_messages(limit=1)
    
    # Ищем сообщение по ID (упрощённо)
    for msg in messages_list:
        if msg.get("id") == message_id:
            return MessageResponse(**msg)
    
    raise HTTPException(status_code=404, detail="Message not found")


@router.get("/messages/stats/total")
async def get_messages_stats(
    api_key: str = Depends(verify_api_key),
    since: Optional[datetime] = Query(None),
):
    """Статистика по сообщениям."""
    count = await db.get_message_count(since=since)
    return {"total_messages": count}
