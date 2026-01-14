"""
Intents API routes — статистика и аналитика по интентам.
"""

import logging

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from api.auth import verify_api_key
from services.database import db

logger = logging.getLogger(__name__)

router = APIRouter()


class IntentStatsResponse(BaseModel):
    """Статистика по интентам."""
    period_days: int
    total_analyzed: int
    by_intent: dict
    by_sentiment: dict


@router.get("/intents", response_model=IntentStatsResponse)
async def get_intent_stats(
    api_key: str = Depends(verify_api_key),
    days: int = Query(7, ge=1, le=365),
):
    """
    Получение статистики по интентам за период.
    
    Returns:
        - by_intent: {question: count, order: count, complaint: count, ...}
        - by_sentiment: {positive: count, neutral: count, negative: count}
    """
    # Проверяем есть ли таблица message_analysis
    try:
        result = await db.fetch(
            """
            SELECT 
                COALESCE(intent, 'unknown') as intent,
                COALESCE(sentiment, 'unknown') as sentiment,
                COUNT(*) as count
            FROM message_analysis
            WHERE created_at >= NOW() - INTERVAL '$1 days'
            GROUP BY 1, 2
            """,
            days
        )
    except Exception:
        # Таблица ещё не создана
        return IntentStatsResponse(
            period_days=days,
            total_analyzed=0,
            by_intent={},
            by_sentiment={},
        )
    
    by_intent = {}
    by_sentiment = {}
    
    for row in result:
        intent = row.get("intent", "unknown")
        sentiment = row.get("sentiment", "unknown")
        count = row.get("count", 0)
        
        by_intent[intent] = by_intent.get(intent, 0) + count
        by_sentiment[sentiment] = by_sentiment.get(sentiment, 0) + count
    
    total = sum(by_intent.values())
    
    return IntentStatsResponse(
        period_days=days,
        total_analyzed=total,
        by_intent=by_intent,
        by_sentiment=by_sentiment,
    )


@router.get("/intents/daily")
async def get_daily_intent_stats(
    api_key: str = Depends(verify_api_key),
    days: int = Query(7, ge=1, le=30),
):
    """Ежедневная статистика по интентам."""
    try:
        result = await db.fetch(
            """
            SELECT 
                DATE(created_at) as date,
                COALESCE(intent, 'unknown') as intent,
                COUNT(*) as count
            FROM message_analysis
            WHERE created_at >= NOW() - INTERVAL '$1 days'
            GROUP BY 1, 2
            ORDER BY 1 DESC, 3 DESC
            """,
            days
        )
    except Exception:
        return {"daily": []}
    
    daily = []
    for row in result:
        daily.append({
            "date": str(row.get("date")),
            "intent": row.get("intent", "unknown"),
            "count": row.get("count", 0),
        })
    
    return {"daily": daily}


@router.get("/intents/urgent")
async def get_urgent_messages(
    api_key: str = Depends(verify_api_key),
    limit: int = Query(20, ge=1, le=100),
):
    """Получение срочных сообщений (жалобы, негативный sentiment)."""
    try:
        result = await db.fetch(
            """
            SELECT ma.*, m.text, m.timestamp, c.name as chat_name
            FROM message_analysis ma
            JOIN messages m ON ma.message_id = m.id
            JOIN chats c ON m.chat_id = c.id
            WHERE (ma.intent = 'complaint' OR ma.sentiment = 'negative')
            ORDER BY ma.created_at DESC
            LIMIT $1
            """,
            limit
        )
    except Exception:
        return {"urgent": []}
    
    urgent = []
    for row in result:
        urgent.append({
            "id": row.get("message_id"),
            "text": row.get("text", "")[:200],
            "intent": row.get("intent"),
            "sentiment": row.get("sentiment"),
            "chat_name": row.get("chat_name"),
            "timestamp": str(row.get("timestamp")),
        })
    
    return {"urgent": urgent}
