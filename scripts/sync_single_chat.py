#!/usr/bin/env python3
"""
Синхронизация сообщений для ОДНОГО чата.
Использование: python scripts/sync_single_chat.py <chat_id>
"""

import asyncio
import os
import sys
from datetime import datetime
from telethon import TelegramClient
import asyncpg

API_ID = 25379848
API_HASH = "5e8dc471c1cf3da3cf532276e38ccc98"
SESSION_PATH = os.path.expanduser("~/.local/state/mcp-telegram/session")
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://cvgorod:cvgorod_secret_2024@localhost:5433/cvgorod_hub")

def log(msg):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)

def to_timestamp(dt):
    if dt and isinstance(dt, datetime) and dt.tzinfo:
        dt = dt.replace(tzinfo=None)
    return dt

async def sync_chat(chat_id: int):
    log(f"Синхронизация чата ID: {chat_id}")
    
    # Подключаемся к Telegram
    log("🔌 Подключение к Telegram...")
    client = TelegramClient(SESSION_PATH, API_ID, API_HASH)
    await client.connect()
    
    if not await client.is_user_authorized():
        log("❌ Telegram не авторизован!")
        return
    
    me = await client.get_me()
    log(f"✅ Telegram: {me.first_name}")
    
    # Подключаемся к PostgreSQL
    log("🔌 Подключение к PostgreSQL...")
    conn = await asyncpg.connect(DATABASE_URL)
    log("✅ PostgreSQL подключён")
    
    # Получаем информацию о чате
    chat_info = await conn.fetchrow("SELECT id, name FROM chats WHERE id = $1", chat_id)
    if not chat_info:
        log(f"❌ Чат с ID {chat_id} не найден в базе!")
        return
    
    log(f"📂 Чат: {chat_info['name']}")
    
    # Ищем диалог в Telegram
    log("🔍 Поиск диалога в Telegram...")
    dialogs = await client.get_dialogs(limit=None)
    
    # Telegram использует positive ID для supergroup как -(100 + id)
    # Поэтому ищем по разным вариантам
    target_dialog = None
    search_ids = [
        chat_id,
        abs(chat_id),
        int(str(abs(chat_id))[3:]) if str(abs(chat_id)).startswith('100') else abs(chat_id),
    ]
    
    for d in dialogs:
        if hasattr(d.entity, 'id'):
            if d.entity.id in search_ids or -d.entity.id in search_ids:
                target_dialog = d
                log(f"✅ Найден диалог: {d.name}")
                break
    
    if not target_dialog:
        log(f"❌ Диалог не найден в Telegram для ID: {chat_id}")
        log(f"   Искал ID: {search_ids}")
        await conn.close()
        await client.disconnect()
        return
    
    # Получаем последние сообщения из Telegram
    log("📥 Загрузка сообщений из Telegram (лимит 100)...")
    messages = await client.get_messages(target_dialog.entity, limit=100)
    log(f"✅ Загружено {len(messages)} сообщений")
    
    saved = 0
    skipped = 0
    
    for msg in messages:
        if not msg.from_id:
            continue
        user_id = getattr(msg.from_id, 'user_id', None)
        if not user_id:
            continue
        
        username = getattr(msg.sender, 'username', None) if msg.sender else None
        first_name = getattr(msg.sender, 'first_name', None) if msg.sender else None
        last_name = getattr(msg.sender, 'last_name', None) if msg.sender else None
        msg_date = to_timestamp(msg.date)
        
        # Определяем тип сообщения и текст
        msg_type = 'text'
        msg_text = msg.text
        
        if msg.voice:
            msg_type = 'voice'
            msg_text = '[Голосовое сообщение]'
        elif msg.video_note:
            msg_type = 'video_note'
            msg_text = '[Видеосообщение]'
        elif msg.sticker:
            msg_type = 'sticker'
            msg_text = f'[Стикер: {msg.sticker.emoji or ""}]'
        elif msg.photo:
            msg_type = 'photo'
            msg_text = msg.message or '[Фото]'
        elif msg.video:
            msg_type = 'video'
            msg_text = msg.message or '[Видео]'
        elif msg.document:
            msg_type = 'document'
            doc_name = getattr(msg.document, 'file_name', '') or ''
            msg_text = msg.message or f'[Документ: {doc_name}]'
        elif msg.audio:
            msg_type = 'audio'
            msg_text = msg.message or '[Аудио]'
        elif not msg_text:
            continue
        
        # Сохраняем пользователя
        await conn.execute("""
            INSERT INTO users (id, username, first_name, last_name)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (id) DO UPDATE SET
                username = COALESCE(EXCLUDED.username, users.username),
                first_name = COALESCE(EXCLUDED.first_name, users.first_name)
        """, user_id, username, first_name, last_name)
        
        # Сохраняем сообщение
        result = await conn.fetchval("""
            INSERT INTO messages (telegram_message_id, chat_id, user_id, text, message_type, timestamp)
            VALUES ($1, $2, $3, $4, $5, $6)
            ON CONFLICT (chat_id, telegram_message_id) DO NOTHING
            RETURNING id
        """, msg.id, chat_id, user_id, msg_text, msg_type, msg_date)
        
        if result:
            saved += 1
            log(f"  + [{msg_type}] {first_name}: {msg_text[:40]}...")
        else:
            skipped += 1
    
    log(f"\n📊 Итого: сохранено {saved}, пропущено (уже есть) {skipped}")
    
    await conn.close()
    await client.disconnect()
    log("✅ Готово!")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Использование: python scripts/sync_single_chat.py <chat_id>")
        print("Пример: python scripts/sync_single_chat.py -4882715175")
        sys.exit(1)
    
    chat_id = int(sys.argv[1])
    asyncio.run(sync_chat(chat_id))
