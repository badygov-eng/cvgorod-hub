"""
Send API routes — песочница для отправки сообщений клиентам.

Поддерживает:
- Одиночные сообщения (POST /send)
- Пакетную отправку (POST /send/batch)
- Управление песочницей (approve/reject/delete)
"""

import logging
import uuid
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from api.auth import verify_api_key
from services.database import db

logger = logging.getLogger(__name__)

router = APIRouter()


# ============================================================
# MODELS
# ============================================================

class SendMessageRequest(BaseModel):
    """Запрос на отправку одного сообщения."""
    chat_id: int | None = None  # telegram chat_id
    cvgorod_chat_id: int | None = None  # альтернативный ID из CVGorod API
    text: str
    context: str | None = None


class SendMessageResponse(BaseModel):
    """Ответ на запрос отправки."""
    pending_id: int
    chat_id: int
    status: str
    created_at: str


class BatchMessageItem(BaseModel):
    """Элемент пакета сообщений."""
    chat_id: int | None = None
    cvgorod_chat_id: int | None = None
    text: str
    context: str | None = None


class SendBatchRequest(BaseModel):
    """Запрос на пакетную отправку."""
    messages: list[BatchMessageItem] = Field(..., min_length=1, max_length=300)
    batch_name: str | None = None
    delay_between_sec: int = Field(default=2, ge=1, le=60)


class BatchResponse(BaseModel):
    """Ответ на пакетный запрос."""
    batch_id: str
    pending_ids: list[int]
    total_messages: int
    status: str
    estimated_duration_sec: int


class PendingResponse(BaseModel):
    """Ожидающее сообщение."""
    id: int
    chat_id: int
    client_name: str | None = None
    response_text: str
    context: str | None = None
    status: str
    created_at: str
    batch_id: str | None = None
    batch_name: str | None = None
    send_order: int = 0
    scheduled_at: str | None = None


class BatchInfo(BaseModel):
    """Информация о пакете."""
    batch_id: str
    batch_name: str | None
    total_messages: int
    pending_count: int
    sent_count: int
    rejected_count: int
    created_at: str


# ============================================================
# HELPER FUNCTIONS
# ============================================================

async def resolve_chat_id(chat_id: int | None, cvgorod_chat_id: int | None) -> int:
    """Получить telegram chat_id по cvgorod_chat_id если нужно."""
    if chat_id:
        return chat_id
    
    if cvgorod_chat_id:
        row = await db.fetchrow(
            "SELECT id FROM chats WHERE cvgorod_chat_id = $1",
            cvgorod_chat_id
        )
        if row:
            return row["id"]
        raise HTTPException(
            status_code=404, 
            detail=f"Chat with cvgorod_chat_id={cvgorod_chat_id} not found"
        )
    
    raise HTTPException(
        status_code=400,
        detail="Either chat_id or cvgorod_chat_id must be provided"
    )


# ============================================================
# SINGLE MESSAGE ENDPOINTS
# ============================================================

@router.post("/send", response_model=SendMessageResponse)
async def send_message(
    request: SendMessageRequest,
    api_key: str = Depends(verify_api_key),
):
    """
    Создание запроса на отправку сообщения в песочницу.
    
    Сообщение НЕ отправляется сразу — требует одобрения администратора.
    
    Можно указать либо chat_id (telegram), либо cvgorod_chat_id.
    """
    # Резолвим chat_id
    telegram_chat_id = await resolve_chat_id(request.chat_id, request.cvgorod_chat_id)
    
    # Получаем имя чата
    chat = await db.get_chat(telegram_chat_id)
    client_name = chat.get("name") if chat else None

    # Сохраняем в pending_responses
    pending_id = await db.fetchval(
        """
        INSERT INTO pending_responses (chat_id, client_name, response_text, context, status, created_at)
        VALUES ($1, $2, $3, $4, 'pending', NOW())
        RETURNING id
        """,
        telegram_chat_id,
        client_name,
        request.text,
        request.context,
    )

    logger.info(f"Created pending response {pending_id} for chat {telegram_chat_id}")

    return SendMessageResponse(
        pending_id=pending_id,
        chat_id=telegram_chat_id,
        status="pending",
        created_at=datetime.now().isoformat(),
    )


# ============================================================
# BATCH ENDPOINTS
# ============================================================

@router.post("/send/batch", response_model=BatchResponse)
async def send_batch(
    request: SendBatchRequest,
    api_key: str = Depends(verify_api_key),
):
    """
    Создание пакета сообщений для отправки.
    
    Все сообщения попадают в песочницу и требуют одобрения.
    После одобрения отправляются с заданной задержкой между сообщениями.
    """
    batch_id = str(uuid.uuid4())
    pending_ids = []
    
    for idx, msg in enumerate(request.messages):
        # Резолвим chat_id
        try:
            telegram_chat_id = await resolve_chat_id(msg.chat_id, msg.cvgorod_chat_id)
        except HTTPException as e:
            logger.warning(f"Skipping message {idx}: {e.detail}")
            continue
        
        # Получаем имя чата
        chat = await db.get_chat(telegram_chat_id)
        client_name = chat.get("name") if chat else None
        
        # Сохраняем с batch_id
        pending_id = await db.fetchval(
            """
            INSERT INTO pending_responses 
                (chat_id, client_name, response_text, context, status, created_at, 
                 batch_id, batch_name, send_order)
            VALUES ($1, $2, $3, $4, 'pending', NOW(), $5, $6, $7)
            RETURNING id
            """,
            telegram_chat_id,
            client_name,
            msg.text,
            msg.context,
            batch_id,
            request.batch_name,
            idx,
        )
        pending_ids.append(pending_id)
    
    if not pending_ids:
        raise HTTPException(status_code=400, detail="No valid messages in batch")
    
    estimated_duration = len(pending_ids) * request.delay_between_sec
    
    logger.info(f"Created batch {batch_id} with {len(pending_ids)} messages")
    
    return BatchResponse(
        batch_id=batch_id,
        pending_ids=pending_ids,
        total_messages=len(pending_ids),
        status="pending",
        estimated_duration_sec=estimated_duration,
    )


@router.get("/sandbox/batches", response_model=list[BatchInfo])
async def list_batches(
    api_key: str = Depends(verify_api_key),
    status: str | None = Query(None, description="Фильтр по статусу: pending, sent, rejected"),
):
    """Получение списка пакетов."""
    query = """
        SELECT 
            batch_id,
            batch_name,
            COUNT(*) as total_messages,
            COUNT(*) FILTER (WHERE status = 'pending') as pending_count,
            COUNT(*) FILTER (WHERE status = 'sent') as sent_count,
            COUNT(*) FILTER (WHERE status = 'rejected') as rejected_count,
            MIN(created_at) as created_at
        FROM pending_responses
        WHERE batch_id IS NOT NULL
        GROUP BY batch_id, batch_name
        ORDER BY MIN(created_at) DESC
    """
    
    rows = await db.fetch(query)
    
    result = []
    for row in rows:
        # Фильтрация по статусу если указан
        if status == "pending" and row["pending_count"] == 0:
            continue
        if status == "sent" and row["sent_count"] == 0:
            continue
            
        result.append(BatchInfo(
            batch_id=str(row["batch_id"]),
            batch_name=row["batch_name"],
            total_messages=row["total_messages"],
            pending_count=row["pending_count"],
            sent_count=row["sent_count"],
            rejected_count=row["rejected_count"],
            created_at=str(row["created_at"]),
        ))
    
    return result


@router.get("/sandbox/batch/{batch_id}", response_model=list[PendingResponse])
async def get_batch_messages(
    batch_id: str,
    api_key: str = Depends(verify_api_key),
):
    """Получение всех сообщений в пакете."""
    rows = await db.fetch(
        """
        SELECT id, chat_id, client_name, response_text, context, status, 
               created_at, batch_id, batch_name, send_order, scheduled_at
        FROM pending_responses
        WHERE batch_id = $1
        ORDER BY send_order
        """,
        batch_id
    )
    
    if not rows:
        raise HTTPException(status_code=404, detail="Batch not found")
    
    return [
        PendingResponse(
            id=row["id"],
            chat_id=row["chat_id"],
            client_name=row.get("client_name"),
            response_text=row["response_text"],
            context=row.get("context"),
            status=row["status"],
            created_at=str(row["created_at"]),
            batch_id=str(row["batch_id"]) if row["batch_id"] else None,
            batch_name=row.get("batch_name"),
            send_order=row.get("send_order", 0),
            scheduled_at=str(row["scheduled_at"]) if row.get("scheduled_at") else None,
        )
        for row in rows
    ]


@router.post("/sandbox/batch/{batch_id}/approve")
async def approve_batch(
    batch_id: str,
    delay_between_sec: int = Query(default=3, ge=1, le=60),
    api_key: str = Depends(verify_api_key),
):
    """
    Одобрение всего пакета сообщений.
    
    Сообщения будут отправлены последовательно с указанной задержкой.
    """
    # Получаем все pending сообщения пакета
    rows = await db.fetch(
        """
        SELECT id, chat_id, response_text, send_order
        FROM pending_responses
        WHERE batch_id = $1 AND status = 'pending'
        ORDER BY send_order
        """,
        batch_id
    )
    
    if not rows:
        raise HTTPException(status_code=404, detail="No pending messages in batch")
    
    from bot.sandbox_manager import sandbox_manager
    
    sent_count = 0
    failed_count = 0
    
    for idx, row in enumerate(rows):
        # Устанавливаем scheduled_at
        scheduled_at = datetime.utcnow() + timedelta(seconds=idx * delay_between_sec)
        
        await db.execute(
            "UPDATE pending_responses SET scheduled_at = $1 WHERE id = $2",
            scheduled_at,
            row["id"]
        )
        
        # Отправляем сообщение
        try:
            success = await sandbox_manager.send_approved_message(
                chat_id=row["chat_id"],
                text=row["response_text"],
            )
            
            if success:
                await db.execute(
                    "UPDATE pending_responses SET status = 'sent', sent_at = NOW() WHERE id = $1",
                    row["id"]
                )
                sent_count += 1
            else:
                await db.execute(
                    "UPDATE pending_responses SET status = 'failed' WHERE id = $1",
                    row["id"]
                )
                failed_count += 1
                
        except Exception as e:
            logger.error(f"Failed to send message {row['id']}: {e}")
            await db.execute(
                "UPDATE pending_responses SET status = 'failed' WHERE id = $1",
                row["id"]
            )
            failed_count += 1
        
        # Задержка между сообщениями (кроме последнего)
        if idx < len(rows) - 1:
            import asyncio
            await asyncio.sleep(delay_between_sec)
    
    logger.info(f"Batch {batch_id} approved: {sent_count} sent, {failed_count} failed")
    
    return {
        "status": "completed",
        "batch_id": batch_id,
        "sent_count": sent_count,
        "failed_count": failed_count,
    }


@router.post("/sandbox/batch/{batch_id}/reject")
async def reject_batch(
    batch_id: str,
    reason: str | None = None,
    api_key: str = Depends(verify_api_key),
):
    """Отклонение всего пакета сообщений."""
    result = await db.execute(
        """
        UPDATE pending_responses
        SET status = 'rejected'
        WHERE batch_id = $1 AND status = 'pending'
        """,
        batch_id
    )
    
    logger.info(f"Batch {batch_id} rejected: {reason}")
    
    return {"status": "rejected", "batch_id": batch_id, "reason": reason}


@router.delete("/sandbox/batch/{batch_id}")
async def delete_batch(
    batch_id: str,
    api_key: str = Depends(verify_api_key),
):
    """Удаление всего пакета (только pending сообщения)."""
    await db.execute(
        "DELETE FROM pending_responses WHERE batch_id = $1 AND status = 'pending'",
        batch_id
    )
    
    return {"status": "deleted", "batch_id": batch_id}


# ============================================================
# SINGLE MESSAGE SANDBOX ENDPOINTS
# ============================================================

@router.get("/sandbox/pending", response_model=list[PendingResponse])
async def get_pending_responses(
    api_key: str = Depends(verify_api_key),
    batch_id: str | None = Query(None, description="Фильтр по batch_id"),
):
    """Получение всех ожидающих сообщений."""
    try:
        if batch_id:
            result = await db.fetch(
                """
                SELECT id, chat_id, client_name, response_text, context, status, 
                       created_at, batch_id, batch_name, send_order, scheduled_at
                FROM pending_responses
                WHERE status = 'pending' AND batch_id = $1
                ORDER BY send_order, created_at DESC
                """,
                batch_id
            )
        else:
            result = await db.fetch(
                """
                SELECT id, chat_id, client_name, response_text, context, status, 
                       created_at, batch_id, batch_name, send_order, scheduled_at
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
            batch_id=str(row["batch_id"]) if row.get("batch_id") else None,
            batch_name=row.get("batch_name"),
            send_order=row.get("send_order", 0),
            scheduled_at=str(row["scheduled_at"]) if row.get("scheduled_at") else None,
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

    # Отправляем сообщение в Telegram
    from bot.sandbox_manager import sandbox_manager
    success = await sandbox_manager.send_approved_message(
        chat_id=pending["chat_id"],
        text=pending["response_text"],
    )

    if success:
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
    else:
        await db.execute(
            "UPDATE pending_responses SET status = 'failed' WHERE id = $1",
            pending_id
        )
        raise HTTPException(status_code=500, detail="Failed to send message")


@router.post("/sandbox/{pending_id}/reject")
async def reject_response(
    pending_id: int,
    reason: str = None,
    api_key: str = Depends(verify_api_key),
):
    """Отклонение отправки сообщения."""
    await db.execute(
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
