"""
FastAPI приложение для cvgorod-hub.
REST API для работы с сообщениями, клиентами и песочницей ответов.
"""

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import settings
from api.routes import messages, clients, intents, send

logger = logging.getLogger(__name__)


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

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
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
app.include_router(messages.router, prefix="/api/v1")
app.include_router(clients.router, prefix="/api/v1")
app.include_router(intents.router, prefix="/api/v1")
app.include_router(send.router, prefix="/api/v1")


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
