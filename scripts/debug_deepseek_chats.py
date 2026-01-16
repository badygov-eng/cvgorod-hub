#!/usr/bin/env python3
"""Debug: показать что уходит в DeepSeek для проблемных чатов."""
import asyncio
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from services.database import db
from services.expectations import _fetch_context, _format_conversation


async def debug():
    await db.connect()
    
    # Проблемные чаты
    test_chats = [
        ("Вашукевич", "КА-00003974"),
        ("Кохановская", "КА-00000573"),
    ]
    
    for name, sync_id in test_chats:
        row = await db.fetchrow(
            "SELECT c.id FROM chats c JOIN customers cu ON c.customer_id = cu.id WHERE cu.sync_id = $1",
            sync_id
        )
        if not row:
            print(f"=== {name}: НЕ НАЙДЕН ===")
            continue
            
        chat_id = row["id"]
        since = datetime.utcnow() - timedelta(days=3)
        msgs = await _fetch_context(chat_id, since, 50)
        
        print(f"=== {name} ({sync_id}) ===")
        print(f"Chat ID: {chat_id}")
        print(f"Сообщений: {len(msgs)}")
        if msgs:
            last = msgs[-1]
            print(f"Последнее от: {last.get('role')}")
            print(f"Последний текст: {last.get('text', '')[:50]}...")
        print()
        print("--- ЧТО УХОДИТ В DEEPSEEK ---")
        print(_format_conversation(msgs))
        print()
        print("=" * 60)
        print()


if __name__ == "__main__":
    asyncio.run(debug())
