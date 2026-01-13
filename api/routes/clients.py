"""
Clients API routes.
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from api.auth import verify_api_key
from services.database import db

logger = logging.getLogger(__name__)

router = APIRouter()


class ClientResponse(BaseModel):
    """Ответ с клиентом."""
    id: int
    username: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    is_manager: bool
    first_seen: str
    last_seen: str


class ClientsListResponse(BaseModel):
    """Ответ со списком клиентов."""
    count: int
    clients: list[ClientResponse]


@router.get("/clients", response_model=ClientsListResponse)
async def list_clients(
    api_key: str = Depends(verify_api_key),
    include_managers: bool = Query(False),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
):
    """
    Получение списка клиентов/пользователей.
    
    Args:
        include_managers: Включить менеджеров
        limit: Максимум записей
        offset: Сдвиг для пагинации
    """
    # Получаем всех пользователей из БД
    all_users = await db.fetch(
        "SELECT * FROM users ORDER BY last_seen DESC LIMIT $1 OFFSET $2",
        limit, offset
    )
    
    users = []
    for user in all_users:
        if not include_managers and user.get("is_manager"):
            continue
        users.append(ClientResponse(
            id=user["id"],
            username=user.get("username"),
            first_name=user.get("first_name"),
            last_name=user.get("last_name"),
            is_manager=user.get("is_manager", False),
            first_seen=user.get("first_seen", "").isoformat() if user.get("first_seen") else "",
            last_seen=user.get("last_seen", "").isoformat() if user.get("last_seen") else "",
        ))
    
    return ClientsListResponse(count=len(users), clients=users)


@router.get("/clients/{client_id}/messages")
async def get_client_messages(
    client_id: int,
    api_key: str = Depends(verify_api_key),
    limit: int = Query(50, ge=1, le=500),
):
    """Получение сообщений конкретного клиента."""
    from api.routes.messages import MessagesListResponse, MessageResponse
    
    messages_list = await db.get_messages(
        user_id=client_id,
        limit=limit,
    )
    
    return MessagesListResponse(
        count=len(messages_list),
        messages=[MessageResponse(**msg) for msg in messages_list],
    )


@router.get("/clients/stats/active")
async def get_active_clients(
    api_key: str = Depends(verify_api_key),
    days: int = Query(7, ge=1, le=365),
):
    """Статистика активных клиентов за период."""
    # Подсчёт уникальных пользователей за период
    query = """
        SELECT COUNT(DISTINCT user_id) as active_users
        FROM messages
        WHERE timestamp >= NOW() - INTERVAL '$1 days'
    """
    result = await db.fetchval(query, days)
    
    return {"active_clients": result or 0}
