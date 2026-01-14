"""
Messages API routes.
"""

import logging
from datetime import datetime, date, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from api.auth import verify_api_key
from services.database import db

logger = logging.getLogger(__name__)

router = APIRouter()


class MessageResponse(BaseModel):
    """Ответ с сообщением."""
    id: int
    chat_id: int
    user_id: int
    text: Optional[str] = None
    message_type: str
    timestamp: datetime
    username: Optional[str] = None
    first_name: Optional[str] = None
    chat_name: Optional[str] = None
    # Новые поля для ролевой модели
    role: Optional[str] = None
    is_automatic: bool = False
    intent: Optional[str] = None
    intent_confidence: Optional[float] = None
    is_reply: bool = False
    reply_to_message_id: Optional[int] = None


class MessageDetailResponse(BaseModel):
    """Детальный ответ с сообщением и связанными данными."""
    id: int
    chat_id: int
    chat_name: Optional[str] = None
    user_id: int
    user: Optional[dict] = None
    role: Optional[str] = None
    text: Optional[str] = None
    message_type: str
    intent: Optional[dict] = None
    sentiment: Optional[str] = None
    is_automatic: bool = False
    is_reply: bool = False
    reply_to_message_id: Optional[int] = None
    timestamp: datetime


class MessagesListResponse(BaseModel):
    """Ответ со списком сообщений."""
    count: int
    total: Optional[int] = None
    messages: list[MessageResponse]
    pagination: Optional[dict] = None


# ВАЖНО: Статические роуты ПЕРЕД динамическими!
@router.get("/messages/stats/total")
async def get_messages_stats(
    api_key: str = Depends(verify_api_key),
    days: int | None = Query(None, ge=1, le=365, description="Количество дней назад"),
    since: datetime | None = Query(None, description="Начало периода (ISO format)"),
):
    """Статистика по сообщениям.
    
    Можно использовать либо days, либо since (days имеет приоритет).
    """
    from datetime import timedelta
    
    # days имеет приоритет над since
    if days is not None:
        since = datetime.utcnow() - timedelta(days=days)
    
    count = await db.get_message_count(since=since)
    return {"total_messages": count, "days": days, "since": since.isoformat() if since else None}


@router.get("/messages/stats/by-role")
async def get_messages_stats_by_role(
    api_key: str = Depends(verify_api_key),
    days: int | None = Query(None, ge=1, le=365, description="Количество дней назад"),
    since: datetime | None = Query(None),
    until: datetime | None = Query(None),
):
    """Статистика сообщений по ролям.
    
    Можно использовать либо days, либо since (days имеет приоритет).
    """
    from datetime import timedelta
    
    # days имеет приоритет над since
    if days is not None:
        since = datetime.utcnow() - timedelta(days=days)
    
    query = """
        SELECT
            COALESCE(m.role, ur.role_name, 'UNKNOWN') as role,
            COUNT(*) as message_count,
            COUNT(DISTINCT m.chat_id) as active_chats,
            COUNT(DISTINCT m.user_id) as active_users
        FROM messages m
        LEFT JOIN users u ON m.user_id = u.id
        LEFT JOIN user_roles ur ON u.role_id = ur.id
        WHERE 1=1
    """
    params = []
    param_idx = 1
    
    if since is not None:
        if since.tzinfo is not None:
            since = since.replace(tzinfo=None)
        query += f" AND m.timestamp >= ${param_idx}"
        params.append(since)
        param_idx += 1
    
    if until is not None:
        if until.tzinfo is not None:
            until = until.replace(tzinfo=None)
        query += f" AND m.timestamp <= ${param_idx}"
        params.append(until)
        param_idx += 1
    
    query += " GROUP BY COALESCE(m.role, ur.role_name, 'UNKNOWN') ORDER BY message_count DESC"
    
    rows = await db.fetch(query, *params)
    stats = {
        "by_role": [dict(row) for row in rows],
        "total_messages": sum(row["message_count"] for row in rows)
    }
    return stats


@router.get("/messages", response_model=MessagesListResponse)
async def list_messages(
    api_key: str = Depends(verify_api_key),
    chat_id: int | None = Query(None),
    user_id: int | None = Query(None),
    role: str | None = Query(
        None,
        description="Фильтр по роли отправителя: CLIENT, MANAGER, DIRECTOR, BOT"
    ),
    exclude_automatic: bool = Query(
        False,
        description="Исключить автоматические сообщения (боты)"
    ),
    has_intent: str | None = Query(
        None,
        description="Фильтр по интенту сообщения"
    ),
    clients_only: bool = Query(
        False,
        description="Только сообщения клиентов (исключает ботов и сотрудников)"
    ),
    days: int | None = Query(None, ge=1, le=365, description="Количество дней назад"),
    since: datetime | None = Query(None),
    until: datetime | None = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
):
    """
    Получение списка сообщений с фильтрами.

    Args:
        chat_id: Фильтр по ID чата
        user_id: Фильтр по ID пользователя
        role: Фильтр по роли отправителя (CLIENT, MANAGER, DIRECTOR, BOT)
        exclude_automatic: Исключить автоматические сообщения от ботов
        has_intent: Фильтр по интенту сообщения
        clients_only: Только сообщения клиентов
        days: Количество дней назад (приоритет над since)
        since: Начало периода
        until: Конец периода
        limit: Максимум записей
        offset: Сдвиг для пагинации
    """
    from datetime import timedelta
    
    # days имеет приоритет над since
    if days is not None:
        since = datetime.utcnow() - timedelta(days=days)
    
    messages_list = await db.get_messages(
        chat_id=chat_id,
        user_id=user_id,
        role=role,
        exclude_automatic=exclude_automatic,
        has_intent=has_intent,
        clients_only=clients_only,
        since=since,
        until=until,
        limit=limit,
        offset=offset,
    )
    
    # Получаем общее количество для пагинации
    total = await db.get_message_count(since=since, role=role)

    return MessagesListResponse(
        count=len(messages_list),
        total=total,
        messages=[MessageResponse(**msg) for msg in messages_list],
        pagination={
            "limit": limit,
            "offset": offset,
            "total": total,
            "has_more": offset + len(messages_list) < total
        }
    )



@router.get("/messages/data")
async def get_messages_report_data(
    report_date: date = Query(default=None, description="Дата отчёта (YYYY-MM-DD)"),
    _: str = Depends(verify_api_key),
):
    """
    Получить данные сообщений за указанную дату для отчёта.
    Если дата не указана — возвращает данные за вчера.
    """
    if report_date is None:
        report_date = date.today() - timedelta(days=1)
    
    start_dt = datetime.combine(report_date, datetime.min.time())
    end_dt = datetime.combine(report_date + timedelta(days=1), datetime.min.time())
    
    query = """
        SELECT 
            m.id,
            to_char(m.timestamp, 'HH24:MI:SS') as time,
            m.timestamp,
            m.text,
            m.message_type,
            m.chat_id,
            c.name as chat_name,
            m.user_id,
            COALESCE(u.username, '') as username,
            COALESCE(u.first_name, '') as first_name,
            COALESCE(u.last_name, '') as last_name,
            COALESCE(u.is_manager, false) as is_manager,
            COALESCE(ur.role_name, 'client') as user_role
        FROM messages m
        LEFT JOIN chats c ON m.chat_id = c.id
        LEFT JOIN users u ON m.user_id = u.id
        LEFT JOIN user_roles ur ON u.role_id = ur.id
        WHERE m.timestamp >= $1 AND m.timestamp < $2
        ORDER BY m.chat_id, m.timestamp ASC
    """
    
    rows = await db.fetch(query, start_dt, end_dt)
    messages = [dict(row) for row in rows]
    
    for msg in messages:
        if msg.get('timestamp'):
            msg['timestamp'] = msg['timestamp'].isoformat()
    
    total = len(messages)
    bot_count = sum(1 for m in messages if m['user_role'] == 'assistant_bot')
    client_count = sum(1 for m in messages if m['user_role'] == 'client')
    unique_chats = len(set(m['chat_id'] for m in messages))
    
    return {
        "date": report_date.isoformat(),
        "stats": {
            "total": total,
            "bot_messages": bot_count,
            "client_messages": client_count,
            "unique_chats": unique_chats,
        },
        "messages": messages,
    }


@router.get("/messages/dates")
async def get_available_dates(
    _: str = Depends(verify_api_key),
):
    """Получить список дат с сообщениями."""
    query = """
        SELECT 
            DATE(timestamp) as msg_date,
            COUNT(*) as count
        FROM messages
        GROUP BY DATE(timestamp)
        ORDER BY msg_date DESC
        LIMIT 90
    """
    rows = await db.fetch(query)
    
    dates = [
        {"date": row['msg_date'].isoformat(), "count": row['count']}
        for row in rows
    ]
    
    return {"dates": dates}


@router.get("/messages/{message_id}", response_model=MessageDetailResponse)
async def get_message(
    message_id: int,
    api_key: str = Depends(verify_api_key),
):
    """Получение конкретного сообщения по ID с полной информацией."""
    query = """
        SELECT
            m.*,
            u.username,
            u.first_name,
            u.role as user_role,
            c.name as chat_name,
            ma.intent,
            ma.sentiment,
            ma.confidence
        FROM messages m
        LEFT JOIN users u ON m.user_id = u.id
        LEFT JOIN chats c ON m.chat_id = c.id
        LEFT JOIN message_analysis ma ON m.id = ma.message_id
        WHERE m.id = $1
    """
    
    row = await db.fetchrow(query, message_id)
    if not row:
        raise HTTPException(status_code=404, detail="Message not found")
    
    row_dict = dict(row)
    
    # Формируем ответ с детальной информацией
    user_info = None
    if row_dict.get("user_id"):
        user_info = {
            "id": row_dict["user_id"],
            "username": row_dict.get("username"),
            "first_name": row_dict.get("first_name"),
            "role": row_dict.get("user_role"),
            "is_active": True
        }
    
    intent_info = None
    if row_dict.get("intent"):
        intent_info = {
            "name": row_dict["intent"],
            "confidence": row_dict.get("confidence")
        }
    
    return MessageDetailResponse(
        id=row_dict["id"],
        chat_id=row_dict["chat_id"],
        chat_name=row_dict.get("chat_name"),
        user_id=row_dict["user_id"],
        user=user_info,
        role=row_dict.get("role"),
        text=row_dict.get("text"),
        message_type=row_dict.get("message_type", "text"),
        intent=intent_info,
        sentiment=row_dict.get("sentiment"),
        is_automatic=row_dict.get("is_automatic", False),
        is_reply=row_dict.get("is_reply", False),
        reply_to_message_id=row_dict.get("reply_to_message_id"),
        timestamp=row_dict["timestamp"]
    )


@router.get("/messages/{message_id}/context")
async def get_message_context(
    message_id: int,
    api_key: str = Depends(verify_api_key),
    limit: int = Query(20, ge=1, le=100),
):
    """Получение контекста сообщения (соседние сообщения в чате)."""
    # Получаем timestamp сообщения
    msg = await db.fetchrow(
        "SELECT chat_id, timestamp FROM messages WHERE id = $1",
        message_id
    )
    if not msg:
        raise HTTPException(status_code=404, detail="Message not found")
    
    # Получаем соседние сообщения
    query = """
        SELECT
            m.*,
            u.username,
            u.first_name,
            u.role as user_role,
            c.name as chat_name
        FROM messages m
        LEFT JOIN users u ON m.user_id = u.id
        LEFT JOIN chats c ON m.chat_id = c.id
        WHERE m.chat_id = $1
            AND ABS(EXTRACT(EPOCH FROM (m.timestamp - $2))) < 86400
        ORDER BY m.timestamp
        LIMIT $3
    """
    
    rows = await db.fetch(query, msg["chat_id"], msg["timestamp"], limit * 2)
    
    # Фильтруем сообщения вокруг целевого
    context_messages = []
    target_idx = None
    for i, row in enumerate(rows):
        if row["id"] == message_id:
            target_idx = i
            break
    
    if target_idx is not None:
        start_idx = max(0, target_idx - limit // 2)
        end_idx = min(len(rows), target_idx + limit // 2 + 1)
        context_messages = [dict(rows[i]) for i in range(start_idx, end_idx)]
    
    return {
        "message_id": message_id,
        "context": [MessageResponse(**msg) for msg in context_messages],
        "context_size": len(context_messages)
    }
