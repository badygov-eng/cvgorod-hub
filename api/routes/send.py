"""
Send API routes — песочница для отправки сообщений клиентам.
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from datetime import datetime

from api.auth import verify_api_key
from config import settings, ADMIN_IDS
from services.database import db

logger = logging.getLogger(__name__)

router = APIRouter()


class SendMessageRequest(BaseModel):
    """Запрос на отправку сообщения."""
    chat_id: int
    text: str
    context: Optional[str] = None


class SendMessageResponse(BaseModel):
    """Ответ на запрос отправки."""
    pending_id: int
    chat_id: int
    status: str
    created_at: str


class PendingResponse(BaseModel):
    """Ожидающее сообщение."""
    id: int
    chat_id: int
    client_name: Optional[str] = None
    response_text: str
    context: Optional[str] = None
    status: str
    created_at: str


@router.post("/send", response_model=SendMessageResponse)
async def send_message(
    request: SendMessageRequest,
    api_key: str = Depends(verify_api_key),
):
    """
    Создание запроса на отправку сообщения в песочницу.
    
    Сообщение не отправляется сразу — требует одобрения администратора.
    """
    # Получаем имя чата
    chat = await db.get_chat(request.chat_id)
    client_name = chat.get("name") if chat else None
    
    # Сохраняем в pending_responses
    result = await db.execute(
        """
        INSERT INTO pending_responses (chat_id, client_name, response_text, context, status, created_at)
        VALUES ($1, $2, $3, $4, 'pending', NOW())
        RETURNING id
        """,
        request.chat_id,
        client_name,
        request.text,
        request.context,
    )
    
    pending_id = result.split()[-1]  # Получаем ID из результата
    
    logger.info(f"Created pending response {pending_id} for chat {request.chat_id}")
    
    return SendMessageResponse(
        pending_id=pending_id,
        chat_id=request.chat_id,
        status="pending",
        created_at=datetime.now().isoformat(),
    )


@router.get("/sandbox/pending", response_model=list[PendingResponse])
async def get_pending_responses(
    api_key: str = Depends(verify_api_key),
):
    """Получение всех ожидающих сообщений."""
    try:
        result = await db.fetch(
            """
            SELECT id, chat_id, client_name, response_text, context, status, created_at
            FROM pending_responses
            WHERE status = 'pending'
            ORDER BY created_at DESC
            """
        )
    except Exception:
        return []
    
    return [
        PendingResponse(
            id=row["id"],
            chat_id=row["chat_id"],
            client_name=row.get("client_name"),
            response_text=row["response_text"],
            context=row.get("context"),
            status=row["status"],
            created_at=str(row["created_at"]),
        )
        for row in result
    ]


@router.post("/sandbox/{pending_id}/approve")
async def approve_response(
    pending_id: int,
    api_key: str = Depends(verify_api_key),
):
    """
    Одобрение отправки сообщения.
    
    После одобрения сообщение отправляется в чат.
    """
    # Получаем pending response
    result = await db.fetch(
        """
        SELECT id, chat_id, response_text, status
        FROM pending_responses
        WHERE id = $1 AND status = 'pending'
        """,
        pending_id
    )
    
    if not result:
        raise HTTPException(status_code=404, detail="Pending response not found")
    
    pending = result[0]
    
    # Здесь должен быть код отправки сообщения в Telegram
    # Это будет реализовано в bot/sender.py
    from bot.sandbox_manager import sandbox_manager
    await sandbox_manager.send_approved_message(
        chat_id=pending["chat_id"],
        text=pending["response_text"],
    )
    
    # Обновляем статус
    await db.execute(
        """
        UPDATE pending_responses
        SET status = 'sent', sent_at = NOW()
        WHERE id = $1
        """,
        pending_id
    )
    
    logger.info(f"Approved and sent pending response {pending_id}")
    
    return {"status": "sent", "pending_id": pending_id}


@router.post("/sandbox/{pending_id}/reject")
async def reject_response(
    pending_id: int,
    reason: str = None,
    api_key: str = Depends(verify_api_key),
):
    """Отклонение отправки сообщения."""
    result = await db.execute(
        """
        UPDATE pending_responses
        SET status = 'rejected'
        WHERE id = $1 AND status = 'pending'
        """,
        pending_id
    )
    
    logger.info(f"Rejected pending response {pending_id}")
    
    return {"status": "rejected", "pending_id": pending_id, "reason": reason}


@router.delete("/sandbox/{pending_id}")
async def delete_pending(
    pending_id: int,
    api_key: str = Depends(verify_api_key),
):
    """Удаление ожидающего сообщения."""
    await db.execute(
        "DELETE FROM pending_responses WHERE id = $1 AND status = 'pending'",
        pending_id
    )
    
    return {"status": "deleted", "pending_id": pending_id}
