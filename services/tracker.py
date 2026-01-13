"""
cvgorod-hub Tracker Integration - Автоматическое логирование в Yandex Tracker

Использование:
    from services.tracker import tracker

    # При ошибке (создаст задачу в TGBOTCG)
    await tracker.error("Описание ошибки", {"error": str(e), "context": {...}})

    # При событии (добавит комментарий к задаче)
    await tracker.info("Описание события", {"data": {...}})
"""

import os
import sys
from pathlib import Path

# Add paths to find MCP shared modules
_project_root = Path(__file__).resolve().parent.parent
_mcp_path = Path("/Users/danielbadygov/MCP")

# Add both paths
for p in [_project_root, _mcp_path]:
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

# Import shared tracker events module directly
from shared.tracker_events import TrackerEvents, Priority

# ========================================
# НАСТРОЙКА ПРОЕКТА
# ========================================

PROJECT_NAME = "cvgorod-hub"
COMPONENT_NAME = "Hub"  # Компонент в очереди TGBOTCG

# ========================================
# ИНИЦИАЛИЗАЦИЯ
# ========================================

tracker = TrackerEvents(
    project=PROJECT_NAME,
    component=COMPONENT_NAME,
    enabled=os.getenv("TRACKER_ENABLED", "true").lower() == "true",
)


# ========================================
# ХЕЛПЕРЫ ДЛЯ CVGOROD-HUB
# ========================================

async def log_startup() -> None:
    """Логирует запуск Hub API."""
    await tracker.deploy(
        summary=f"{PROJECT_NAME} запущен",
        data={
            "version": os.getenv("APP_VERSION", "1.0.0"),
            "environment": os.getenv("ENVIRONMENT", "development"),
            "port": os.getenv("HUB_API_PORT", "8000"),
        },
    )


async def log_shutdown(reason: str = "normal") -> None:
    """Логирует остановку Hub API."""
    await tracker.info(
        summary=f"{PROJECT_NAME} остановлен",
        data={"reason": reason},
    )


async def log_api_error(
    endpoint: str,
    error: str,
    status_code: int = None,
    context: dict = None,
) -> None:
    """Логирует ошибку API."""
    await tracker.error(
        summary=f"API Error: {endpoint}",
        data={
            "error": error,
            "status_code": status_code,
            "endpoint": endpoint,
            **(context or {}),
        },
        priority=Priority.HIGH if status_code and status_code >= 500 else Priority.NORMAL,
    )


async def log_telegram_message(
    chat_id: int,
    message_type: str,
    has_intent: bool = True,
    intent_type: str = None,
) -> None:
    """Логирует обработку сообщения из Telegram."""
    await tracker.info(
        summary=f"Telegram сообщение: {message_type}",
        data={
            "chat_id": chat_id,
            "message_type": message_type,
            "has_intent": has_intent,
            "intent_type": intent_type,
        },
    )


async def log_intent_classification(
    message_id: int,
    intent: str,
    sentiment: str,
    confidence: float,
    processing_time_ms: int,
) -> None:
    """Логирует результат классификации интента."""
    await tracker.info(
        summary=f"Intent classified: {intent}",
        data={
            "message_id": message_id,
            "intent": intent,
            "sentiment": sentiment,
            "confidence": confidence,
            "processing_time_ms": processing_time_ms,
        },
    )


async def log_sandbox_action(
    action: str,
    pending_id: int,
    user_id: int = None,
    approved: bool = None,
) -> None:
    """Логирует действие с песочницей."""
    await tracker.info(
        summary=f"Sandbox {action}",
        data={
            "pending_id": pending_id,
            "action": action,
            "user_id": user_id,
            "approved": approved,
        },
    )


async def log_database_operation(
    operation: str,
    table: str,
    success: bool = True,
    duration_ms: int = None,
    error: str = None,
) -> None:
    """Логирует операцию с базой данных."""
    if not success:
        await tracker.error(
            summary=f"DB Error: {operation} на {table}",
            data={
                "operation": operation,
                "table": table,
                "duration_ms": duration_ms,
                "error": error,
            },
            priority=Priority.HIGH,
        )
    else:
        await tracker.info(
            summary=f"DB Operation: {operation}",
            data={
                "operation": operation,
                "table": table,
                "duration_ms": duration_ms,
            },
        )


async def log_deploy(
    version: str,
    environment: str,
    success: bool = True,
    error: str = None,
) -> None:
    """Логирует деплой."""
    if success:
        await tracker.deploy(
            summary=f"Деплой {PROJECT_NAME} v{version}",
            data={
                "version": version,
                "environment": environment,
                "success": True,
            },
        )
    else:
        await tracker.error(
            summary=f"Failed deploy {PROJECT_NAME} v{version}",
            data={
                "version": version,
                "environment": environment,
                "success": False,
                "error": error,
            },
            priority=Priority.HIGH,
        )


# ========================================
# ИНИЦИАЛИЗАЦИЯ ПРИ ЗАПУСКЕ
# ========================================

async def init_tracker() -> None:
    """Инициализирует трекер при запуске приложения."""
    if tracker.enabled:
        await log_startup()


async def shutdown_tracker() -> None:
    """Останавливает трекер при завершении."""
    if tracker.enabled:
        await log_shutdown()
