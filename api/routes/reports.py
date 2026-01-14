"""
Reports API routes — отчёты по сообщениям.
"""

from datetime import date, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, Query
from fastapi.responses import HTMLResponse

from api.auth import verify_api_key
from services.database import db

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/messages/data")
async def get_messages_report_data(
    report_date: date = Query(default=None, description="Дата отчёта (YYYY-MM-DD)"),
    _: str = Depends(verify_api_key),
) -> dict[str, Any]:
    """
    Получить данные сообщений за указанную дату для отчёта.
    
    Если дата не указана — возвращает данные за вчера.
    """
    if report_date is None:
        report_date = date.today() - timedelta(days=1)
    
    start_dt = datetime.combine(report_date, datetime.min.time())
    end_dt = datetime.combine(report_date + timedelta(days=1), datetime.min.time())
    
    # Получаем сообщения с информацией о пользователях и чатах
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
    
    # Конвертируем timestamp в строку для JSON
    for msg in messages:
        if msg.get('timestamp'):
            msg['timestamp'] = msg['timestamp'].isoformat()
    
    # Статистика
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
) -> dict[str, Any]:
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
