"""
Users and Clients API routes.
"""

import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from api.auth import verify_api_key
from services.database import db

logger = logging.getLogger(__name__)

router = APIRouter()


class UserResponse(BaseModel):
    """Ответ с пользователем."""
    id: int
    username: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    role: str
    is_manager: bool = False
    is_active: bool = True
    chats_count: int = 0
    messages_count: int = 0
    first_seen: Optional[str] = None
    last_seen: Optional[str] = None


class UsersListResponse(BaseModel):
    """Ответ со списком пользователей."""
    count: int
    total: Optional[int] = None
    users: list[UserResponse]


class ManagerResponse(BaseModel):
    """Ответ с менеджером."""
    id: int
    username: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    chats_count: int
    messages_count: int
    last_seen: Optional[str] = None
    is_active: bool = True


class ManagersListResponse(BaseModel):
    """Ответ со списком менеджеров."""
    count: int
    total: int
    managers: list[ManagerResponse]


class UserStatisticsResponse(BaseModel):
    """Ответ со статистикой пользователя."""
    user_id: int
    role: str
    statistics: dict
    by_role: list[dict]
    mailings: dict


class UserRoleUpdateRequest(BaseModel):
    """Запрос на изменение роли пользователя."""
    role: str = Field(..., pattern="^(CLIENT|MANAGER|DIRECTOR|BOT)$")


class UserRoleUpdateResponse(BaseModel):
    """Ответ на изменение роли."""
    success: bool
    user_id: int
    role: str
    updated_at: str


class ChatParticipantsResponse(BaseModel):
    """Ответ с участниками чата."""
    chat_id: int
    chat_name: Optional[str] = None
    participants: list[dict]


class MailingCampaignResponse(BaseModel):
    """Ответ с кампанией рассылки."""
    id: int
    name: str
    description: Optional[str] = None
    message_template: str
    sent_by: Optional[dict] = None
    sent_at: Optional[str] = None
    status: str
    total_recipients: int = 0
    successful_deliveries: int = 0
    failed_deliveries: int = 0


class MailingsListResponse(BaseModel):
    """Ответ со списком рассылок."""
    count: int
    total: int
    mailings: list[MailingCampaignResponse]


class ConversationAnalyticsResponse(BaseModel):
    """Ответ с аналитикой диалогов."""
    period: dict
    statistics: dict
    manager_performance: list[dict]


# ============================================================
# USERS ENDPOINTS
# ============================================================

@router.get("/users", response_model=UsersListResponse)
async def list_users(
    api_key: str = Depends(verify_api_key),
    role: str | None = Query(
        None,
        description="Фильтр по роли: CLIENT, MANAGER, DIRECTOR, BOT"
    ),
    include_inactive: bool = Query(False),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
):
    """
    Получение списка пользователей с фильтрацией по роли.

    Args:
        role: Фильтр по роли пользователя (case-insensitive)
        include_inactive: Включить неактивных пользователей
        limit: Максимум записей
        offset: Сдвиг для пагинации
    """
    valid_roles = ["CLIENT", "MANAGER", "DIRECTOR", "BOT"]
    
    # Нормализуем роль к верхнему регистру
    if role is not None:
        role = role.upper()
        if role not in valid_roles:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid role. Must be one of: {valid_roles}"
            )

    users_list = await db.get_users(
        role=role,
        include_inactive=include_inactive,
        limit=limit,
        offset=offset,
    )

    users = []
    for user in users_list:
        users.append(UserResponse(
            id=user["id"],
            username=user.get("username"),
            first_name=user.get("first_name"),
            last_name=user.get("last_name"),
            role=user.get("role", "CLIENT"),
            is_manager=user.get("is_manager", False),
            is_active=user.get("is_active", True),
            chats_count=user.get("chats_count", 0),
            messages_count=user.get("messages_count", 0),
            first_seen=user.get("first_seen", "").isoformat() if user.get("first_seen") else None,
            last_seen=user.get("last_seen", "").isoformat() if user.get("last_seen") else None,
        ))

    return UsersListResponse(
        count=len(users),
        users=users,
        pagination={"limit": limit, "offset": offset}
    )


@router.get("/users/managers", response_model=ManagersListResponse)
async def list_managers(
    api_key: str = Depends(verify_api_key),
):
    """
    Получение списка всех менеджеров.

    Returns:
        Список менеджеров с информацией о количестве чатов и сообщений.
    """
    managers_list = await db.get_all_managers()

    managers = []
    for manager in managers_list:
        managers.append(ManagerResponse(
            id=manager["id"],
            username=manager.get("username"),
            first_name=manager.get("first_name"),
            last_name=manager.get("last_name"),
            chats_count=manager.get("chats_count", 0),
            messages_count=manager.get("messages_count", 0),
            last_seen=manager.get("last_seen", "").isoformat() if manager.get("last_seen") else None,
            is_active=manager.get("is_active", True),
        ))

    return ManagersListResponse(
        count=len(managers),
        total=len(managers),
        managers=managers,
    )


@router.get("/users/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: int,
    api_key: str = Depends(verify_api_key),
):
    """Получение информации о конкретном пользователе."""
    user = await db.get_user(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    stats = await db.get_user_statistics(user_id, days=30)

    return UserResponse(
        id=user["id"],
        username=user.get("username"),
        first_name=user.get("first_name"),
        last_name=user.get("last_name"),
        role=user.get("role", "CLIENT"),
        is_manager=user.get("is_manager", False),
        is_active=user.get("is_active", True),
        chats_count=stats.get("chats_count", 0),
        messages_count=stats.get("messages_count", 0),
        first_seen=user.get("first_seen", "").isoformat() if user.get("first_seen") else None,
        last_seen=user.get("last_seen", "").isoformat() if user.get("last_seen") else None,
    )


@router.get("/users/{user_id}/statistics", response_model=UserStatisticsResponse)
async def get_user_statistics(
    user_id: int,
    api_key: str = Depends(verify_api_key),
    days: int = Query(30, ge=1, le=365),
):
    """Получение детальной статистики пользователя."""
    user = await db.get_user(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    stats = await db.get_user_statistics(user_id, days=days)

    if not stats:
        raise HTTPException(status_code=404, detail="Statistics not found")

    return UserStatisticsResponse(
        user_id=user_id,
        role=user.get("role", "CLIENT"),
        statistics={
            "total_messages": stats.get("messages_count", 0),
            "total_chats": stats.get("chats_count", 0),
            "first_message": stats.get("first_message", "").isoformat() if stats.get("first_message") else None,
            "last_message": stats.get("last_message", "").isoformat() if stats.get("last_message") else None,
        },
        by_role=stats.get("by_role", []),
        mailings=stats.get("mailings", {}),
    )


@router.patch("/users/{user_id}/role", response_model=UserRoleUpdateResponse)
async def update_user_role(
    user_id: int,
    request: UserRoleUpdateRequest,
    api_key: str = Depends(verify_api_key),
):
    """Изменение роли пользователя (требует прав DIRECTOR)."""
    user = await db.get_user(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    success = await db.update_user_role(user_id, request.role)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to update role")

    return UserRoleUpdateResponse(
        success=True,
        user_id=user_id,
        role=request.role,
        updated_at=datetime.utcnow().isoformat(),
    )


# ============================================================
# CLIENTS ENDPOINTS (устаревшие, но совместимые)
# ============================================================

class ClientResponse(BaseModel):
    """Ответ с клиентом."""
    id: int
    username: str | None = None
    first_name: str | None = None
    last_name: str | None = None
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
    Получение списка клиентов/пользователей (устаревший endpoint).

    Рекомендуется использовать /users вместо этого endpoint'а.
    """
    # Получаем всех пользователей из БД
    all_users = await db.get_users(limit=limit + offset)

    users = []
    for user in all_users[offset:offset + limit]:
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
    """Получение сообщений конкретного клиента (устаревший endpoint)."""
    from api.routes.messages import MessageResponse, MessagesListResponse

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
    from datetime import timedelta
    since = datetime.utcnow() - timedelta(days=days)
    
    query = """
        SELECT COUNT(DISTINCT user_id) as active_users
        FROM messages
        WHERE timestamp >= $1
            AND UPPER(role) = 'CLIENT'
    """
    result = await db.fetchval(query, since)

    return {"active_clients": result or 0, "days": days}


# ============================================================
# CHATS ENDPOINTS
# ============================================================

@router.get("/chats/{chat_id}/participants", response_model=ChatParticipantsResponse)
async def get_chat_participants(
    chat_id: int,
    api_key: str = Depends(verify_api_key),
):
    """Получение участников чата с ролями."""
    chat = await db.get_chat(chat_id)
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")

    participants = await db.get_chat_participants(chat_id)

    return ChatParticipantsResponse(
        chat_id=chat_id,
        chat_name=chat.get("name"),
        participants=participants,
    )


# ============================================================
# MAILINGS ENDPOINTS
# ============================================================

@router.get("/mailings", response_model=MailingsListResponse)
async def list_mailings(
    api_key: str = Depends(verify_api_key),
    status: str | None = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
):
    """Получение списка кампаний рассылок."""
    campaigns = await db.get_mailing_campaigns(status=status, limit=limit, offset=offset)

    mailings = []
    for campaign in campaigns:
        sent_by = None
        if campaign.get("sent_by_user_id"):
            sent_by = {
                "id": campaign["sent_by_user_id"],
                "first_name": campaign.get("sent_by_first_name"),
                "username": campaign.get("sent_by_username"),
            }

        mailings.append(MailingCampaignResponse(
            id=campaign["id"],
            name=campaign["name"],
            description=campaign.get("description"),
            message_template=campaign["message_template"],
            sent_by=sent_by,
            sent_at=campaign.get("sent_at", "").isoformat() if campaign.get("sent_at") else None,
            status=campaign.get("status", "DRAFT"),
            total_recipients=campaign.get("total_recipients", 0),
            successful_deliveries=campaign.get("successful_deliveries", 0),
            failed_deliveries=campaign.get("failed_deliveries", 0),
        ))

    return MailingsListResponse(
        count=len(mailings),
        total=len(mailings),
        mailings=mailings,
    )


# ============================================================
# ANALYTICS ENDPOINTS
# ============================================================

@router.get("/analytics/conversations", response_model=ConversationAnalyticsResponse)
async def get_conversation_analytics(
    api_key: str = Depends(verify_api_key),
    days: int | None = Query(None, ge=1, le=365, description="Количество дней назад"),
    since: datetime | None = Query(None),
    until: datetime | None = Query(None),
):
    """Аналитика диалогов с учётом ролей.
    
    Можно использовать либо days, либо since (days имеет приоритет).
    """
    from datetime import timedelta
    
    # days имеет приоритет над since
    if days is not None:
        since = datetime.utcnow() - timedelta(days=days)
    
    analytics = await db.get_conversation_analytics(since=since, until=until)

    return ConversationAnalyticsResponse(
        period={
            "start": since.isoformat() if since else None,
            "end": until.isoformat() if until else None,
        },
        statistics=analytics.get("statistics", {}),
        manager_performance=analytics.get("manager_performance", []),
    )


@router.get("/analytics/unanswered")
async def get_unanswered_questions(
    api_key: str = Depends(verify_api_key),
    hours: int = Query(24, ge=1, le=168),
    limit: int = Query(100, ge=1, le=500),
):
    """Получение вопросов клиентов без ответов."""
    questions = await db.get_unanswered_questions(hours=hours, limit=limit)

    return {
        "count": len(questions),
        "hours_threshold": hours,
        "questions": questions,
    }
