#!/usr/bin/env python3
"""Debug: показать что уходит в DeepSeek для конкретного клиента."""

import asyncio
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from services.database import db


async def debug_context(sync_id: str = "КА-00000573"):
    await db.connect()
    
    # Найдём chat_id
    chat_row = await db.fetchrow(
        """
        SELECT c.id as chat_id, c.name as chat_name, cu.name as customer_name
        FROM chats c
        LEFT JOIN customers cu ON c.customer_id = cu.id
        WHERE cu.sync_id = $1
        """,
        sync_id,
    )
    
    if not chat_row:
        print(f"Чат с sync_id={sync_id} не найден")
        return
    
    chat_id = chat_row["chat_id"]
    print(f"Chat ID: {chat_id}")
    print(f"Chat name: {chat_row['chat_name']}")
    print(f"Customer: {chat_row['customer_name']}")
    print()
    
    # Параметры как в analyze_expectations
    since = datetime.utcnow() - timedelta(days=3)
    limit = 50
    
    role_expr = """
        CASE
            WHEN COALESCE(ur.is_bot, FALSE) = TRUE THEN 'BOT'
            WHEN COALESCE(ur.role_name, '') = 'director' THEN 'DIRECTOR'
            WHEN COALESCE(ur.role_name, '') = 'manager'
                OR COALESCE(u.is_manager, FALSE) = TRUE THEN 'MANAGER'
            ELSE 'CLIENT'
        END
    """
    
    query = f"""
        WITH recent AS (
            SELECT
                m.id,
                m.timestamp,
                m.text,
                u.username,
                u.first_name,
                u.last_name,
                {role_expr} AS role
            FROM messages m
            LEFT JOIN users u ON m.user_id = u.id
            LEFT JOIN user_roles ur ON u.role_id = ur.id
            WHERE m.chat_id = $1
                AND m.timestamp >= $2
                AND m.text IS NOT NULL
                AND m.text != ''
            ORDER BY m.timestamp DESC
            LIMIT $3
        )
        SELECT * FROM recent
        ORDER BY timestamp ASC
    """
    
    rows = await db.fetch(query, chat_id, since, limit)
    
    print("=" * 70)
    print("ЧТО УХОДИТ В DEEPSEEK (формат как в промпте)")
    print("=" * 70)
    
    for row in rows:
        role = row["role"]
        first = row["first_name"] or ""
        last = row["last_name"] or ""
        name = f"{first} {last}".strip()
        if not name:
            name = row["username"] or role
        text = (row["text"] or "").strip()
        ts = row["timestamp"].strftime("%d.%m %H:%M")
        
        print(f"[{role}] {name}: {text}")
    
    print("=" * 70)
    print(f"Всего сообщений: {len(rows)}")
    print(f"Since: {since}")
    print()
    
    # Покажем последнее сообщение
    if rows:
        last = rows[-1]
        print(f"ПОСЛЕДНЕЕ сообщение от: {last['role']}")
        print(f"  Текст: {last['text'][:100]}")
    
    await db.disconnect()


if __name__ == "__main__":
    sync_id = sys.argv[1] if len(sys.argv) > 1 else "КА-00000573"
    asyncio.run(debug_context(sync_id))
