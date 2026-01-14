#!/usr/bin/env python3
"""
Полная синхронизация с исправлением ID и загрузкой ВСЕХ сообщений.
"""

import asyncio
import os
import sys
from datetime import datetime, timedelta
from telethon import TelegramClient
from telethon.tl.types import Channel
import asyncpg

sys.stdout.reconfigure(line_buffering=True)

API_ID = 25379848
API_HASH = "5e8dc471c1cf3da3cf532276e38ccc98"
SESSION_PATH = os.path.expanduser("~/.local/state/mcp-telegram/session")
DATABASE_URL = "postgresql://cvgorod:cvgorod_secret_2024@localhost:5433/cvgorod_hub"

MESSAGES_PER_REQUEST = 500
MAX_MESSAGES_PER_CHAT = 10000  # Увеличено до 10000
PAUSE_BETWEEN_CHATS = 2

def log(msg):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)

def to_timestamp(dt):
    if dt and isinstance(dt, datetime) and dt.tzinfo:
        dt = dt.replace(tzinfo=None)
    return dt

def normalize_chat_id(chat_id):
    """Нормализует chat_id — убирает префикс -100 если есть."""
    if chat_id < 0:
        str_id = str(chat_id)
        if str_id.startswith('-100'):
            return int(str_id[4:])  # Убираем -100
    return abs(chat_id)

async def get_all_messages_backwards(client, entity, max_messages=MAX_MESSAGES_PER_CHAT):
    """Получает ВСЕ сообщения (от новых к старым) с пагинацией."""
    all_messages = []
    offset_id = 0
    
    while len(all_messages) < max_messages:
        messages = await client.get_messages(
            entity,
            limit=MESSAGES_PER_REQUEST,
            offset_id=offset_id
        )
        
        if not messages:
            break
        
        all_messages.extend(messages)
        offset_id = messages[-1].id
        
        if len(messages) < MESSAGES_PER_REQUEST:
            break
        
        await asyncio.sleep(0.3)
    
    return all_messages

async def main():
    start_time = datetime.now()
    
    log("=" * 65)
    log("ПОЛНАЯ СИНХРОНИЗАЦИЯ (исправленные ID + все сообщения)")
    log("=" * 65)
    
    log("🔌 Подключение к Telegram...")
    client = TelegramClient(SESSION_PATH, API_ID, API_HASH)
    await client.connect()
    
    if not await client.is_user_authorized():
        log("❌ Telegram не авторизован!")
        return
    
    me = await client.get_me()
    log(f"✅ Telegram: {me.first_name}")
    
    log("🔌 Подключение к PostgreSQL...")
    pool = await asyncpg.create_pool(DATABASE_URL, min_size=2, max_size=5)
    log("✅ PostgreSQL подключён")
    
    log("📂 Загрузка чатов из БД...")
    async with pool.acquire() as conn:
        chats = await conn.fetch("SELECT id, name FROM chats WHERE is_active = TRUE ORDER BY name")
    
    total_chats = len(chats)
    log(f"📋 Чатов в БД: {total_chats}")
    
    log("📥 Загрузка диалогов Telegram...")
    dialogs = await client.get_dialogs(limit=None)
    
    # Создаём map с нормализованными ID
    dialog_map = {}
    for d in dialogs:
        if hasattr(d.entity, 'id'):
            # Сохраняем по нормализованному ID
            norm_id = normalize_chat_id(d.entity.id)
            dialog_map[norm_id] = d
            # Также по оригинальному
            dialog_map[d.entity.id] = d
    
    log(f"✅ Диалогов: {len(dialogs)}, в map: {len(dialog_map)}")
    
    stats = {
        'processed': 0, 'not_found': 0,
        'fetched': 0, 'saved': 0, 'already_exists': 0, 'errors': 0
    }
    
    log("\n🚀 НАЧИНАЮ СИНХРОНИЗАЦИЮ...\n")
    
    for i, chat in enumerate(chats, 1):
        db_chat_id = chat['id']
        chat_name = chat['name'] or str(db_chat_id)
        
        # Нормализуем ID для поиска
        norm_id = normalize_chat_id(db_chat_id)
        
        percent = (i / total_chats) * 100
        elapsed = (datetime.now() - start_time).total_seconds()
        eta = str(timedelta(seconds=int((elapsed / i) * (total_chats - i)))) if i > 0 else "..."
        
        short_name = (chat_name[:30] + "...") if len(chat_name) > 30 else chat_name
        
        # Ищем по нормализованному ID
        dialog = dialog_map.get(norm_id) or dialog_map.get(db_chat_id) or dialog_map.get(abs(db_chat_id))
        
        if not dialog:
            log(f"[{i}/{total_chats}] {percent:.0f}% {short_name} — ⚠️ не найден (ID: {db_chat_id})")
            stats['not_found'] += 1
            continue
        
        log(f"[{i}/{total_chats}] {percent:.0f}% {short_name} | ETA: {eta}")
        
        try:
            # Получаем текущее кол-во сообщений в БД
            async with pool.acquire() as conn:
                existing_count = await conn.fetchval(
                    "SELECT COUNT(*) FROM messages WHERE chat_id = $1", db_chat_id
                )
            
            # Загружаем ВСЕ сообщения
            messages = await get_all_messages_backwards(client, dialog.entity)
            
            if not messages:
                log(f"    → пустой чат")
                stats['processed'] += 1
                continue
            
            stats['fetched'] += len(messages)
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
                
                async with pool.acquire() as conn:
                    await conn.execute("""
                        INSERT INTO users (id, username, first_name, last_name)
                        VALUES ($1, $2, $3, $4)
                        ON CONFLICT (id) DO UPDATE SET
                            username = COALESCE(EXCLUDED.username, users.username)
                    """, user_id, username, first_name, last_name)
                    
                    result = await conn.fetchval("""
                        INSERT INTO messages (telegram_message_id, chat_id, user_id, text, message_type, timestamp)
                        VALUES ($1, $2, $3, $4, 'text', $5)
                        ON CONFLICT (chat_id, telegram_message_id) DO NOTHING
                        RETURNING id
                    """, msg.id, db_chat_id, user_id, msg.text, msg_date)
                    
                    if result:
                        saved += 1
                    else:
                        skipped += 1
            
            stats['saved'] += saved
            stats['already_exists'] += skipped
            stats['processed'] += 1
            
            new_total = existing_count + saved
            log(f"    → загр: {len(messages)}, новых: {saved}, было: {existing_count}, всего: {new_total}")
            
        except Exception as e:
            log(f"    → ❌ {str(e)[:60]}")
            stats['errors'] += 1
        
        await asyncio.sleep(PAUSE_BETWEEN_CHATS)
    
    elapsed_total = str(datetime.now() - start_time).split('.')[0]
    
    log("\n" + "=" * 65)
    log(f"📊 ИТОГО за {elapsed_total}:")
    log(f"   Чатов обработано:    {stats['processed']}")
    log(f"   Чатов не найдено:    {stats['not_found']}")
    log(f"   Сообщений загружено: {stats['fetched']}")
    log(f"   Сообщений сохранено: {stats['saved']}")
    log(f"   Уже было в БД:       {stats['already_exists']}")
    log(f"   Ошибок:              {stats['errors']}")
    
    async with pool.acquire() as conn:
        msg_count = await conn.fetchval("SELECT COUNT(*) FROM messages")
    
    log(f"\n💾 Всего сообщений в БД: {msg_count}")
    log("=" * 65)
    
    await pool.close()
    await client.disconnect()
    log("✅ ГОТОВО!")

if __name__ == "__main__":
    asyncio.run(main())
