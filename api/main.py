"""
FastAPI приложение для cvgorod-hub.
REST API для работы с сообщениями, клиентами и песочницей ответов.
"""

import logging
import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes import clients, intents, messages, send
from config import settings

logger = logging.getLogger(__name__)


def get_cors_origins() -> list[str]:
    """Получить разрешённые origins в зависимости от среды."""
    env = os.getenv("ENVIRONMENT", "development")

    if env == "production":
        # Production: настраивается через nginx с заголовками
        # API доступен только через прокси
        return []

    if env == "staging":
        # Staging: локальный доступ + разрешённые домены
        return [
            "http://localhost:8309",
            "http://127.0.0.1:8309",
        ]

    # Development: широкий доступ для разработки
    return [
        "http://localhost:8308",
        "http://localhost:3000",
        "http://127.0.0.1:8308",
        "http://127.0.0.1:3000",
    ]


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Startup и shutdown events."""
    logger.info("cvgorod-hub API starting...")

    # Подключение к базе данных
    from services.database import db
    try:
        await db.connect()
        logger.info("Database connected")
    except Exception as e:
        logger.error(f"Failed to connect to database: {e}")

    yield

    # Закрытие соединений
    await db.close()
    logger.info("cvgorod-hub API stopped")


app = FastAPI(
    title="cvgorod-hub API",
    description="CRM Message Hub — сбор сообщений, LLM-обработка, REST API",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS - настраивается в зависимости от среды
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Health check
@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "ok", "service": "cvgorod-hub"}


# API v1 routes
app.include_router(messages, prefix="/api/v1")
app.include_router(clients, prefix="/api/v1")
app.include_router(intents, prefix="/api/v1")
app.include_router(send, prefix="/api/v1")


def run():
    """Запуск через uvicorn."""
    import uvicorn
    uvicorn.run(
        "main:app",
        host=settings.HUB_API_HOST,
        port=settings.HUB_API_PORT,
        reload=False,
    )


if __name__ == "__main__":
    run()
