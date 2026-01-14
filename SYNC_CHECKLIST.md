# ✅ Чеклист: Синхронизация истории Telegram → cvgorod-hub

## Статус инфраструктуры

- ✅ Уникальный индекс создан: `idx_messages_chat_telegram_id`
- ✅ Скрипт синхронизации создан: `scripts/sync_telegram_history.py`
- ✅ Тестовый скрипт создан: `scripts/test_telegram_mcp.py`
- ✅ Документация создана:
  - `TELEGRAM_SYNC_INSTRUCTIONS.md` — полная инструкция
  - `scripts/README_SYNC.md` — краткий справочник
- ✅ Dry-run тест пройден успешно (277 чатов найдено)

## Перед запуском синхронизации

### 1. Проверить текущее состояние БД

```bash
docker exec cvgorod-hub-postgres psql -U cvgorod -d cvgorod_hub -c "
SELECT 
    'chats' as table_name, COUNT(*) as count FROM chats
UNION ALL 
SELECT 'users', COUNT(*) FROM users  
UNION ALL 
SELECT 'messages', COUNT(*) FROM messages;
"
```

**Текущее состояние** (до синхронизации):
- chats: 277
- users: 244
- messages: 40,579

### 2. Сделать бэкап

```bash
cd /Users/danielbadygov/cvgorod-hub
./scripts/backup_db.sh
```

Проверить что бэкап создан:
```bash
ls -lh backups/
```

### 3. Проверить Telegram MCP

В Cursor:
- Settings → MCP → Убедиться что `mcp-telegram` активен
- Попробовать: `mcp_mcp-telegram_search_dialogs(query="cvgorod", limit=5)`

## Запуск синхронизации

### Вариант 1: Через Cursor AI (рекомендуется)

Скопируйте в Cursor:

```
Выполни синхронизацию Telegram сообщений для cvgorod-hub:

1. Используй Telegram MCP для поиска групп:
   mcp_mcp-telegram_search_dialogs(query="cvgorod", limit=50)

2. Для каждой найденной группы загрузи последние 1000 сообщений:
   mcp_mcp-telegram_get_messages(entity="<chat_id>", limit=1000)

3. Сохрани сообщения в PostgreSQL:
   - DATABASE_URL: postgresql://cvgorod:cvgorod_secret_2024@localhost:5433/cvgorod_hub
   - Используй ON CONFLICT DO NOTHING для предотвращения дубликатов
   - Формат: (telegram_message_id, chat_id, user_id, text, timestamp, ...)

4. Выведи статистику:
   - Сколько групп обработано
   - Сколько сообщений загружено
   - Сколько новых сообщений сохранено
```

### Вариант 2: Через Python скрипт (требует доработки)

**⚠️ Требует интеграции Telegram MCP в скрипт!**

См. инструкции в `scripts/README_SYNC.md` как добавить вызовы MCP в:
- `find_groups_with_bot()`
- `fetch_messages_from_telegram()`

```bash
DATABASE_URL="postgresql://cvgorod:cvgorod_secret_2024@localhost:5433/cvgorod_hub" \
python3 scripts/sync_telegram_history.py
```

## После синхронизации

### 1. Проверить количество записей

```bash
docker exec cvgorod-hub-postgres psql -U cvgorod -d cvgorod_hub -c "
SELECT 
    'chats' as table_name, COUNT(*) as count FROM chats
UNION ALL 
SELECT 'users', COUNT(*) FROM users  
UNION ALL 
SELECT 'messages', COUNT(*) FROM messages;
"
```

**Ожидаемый результат**:
- messages: больше 40,579 (новые сообщения добавлены)

### 2. Проверить последние сообщения

```bash
docker exec cvgorod-hub-postgres psql -U cvgorod -d cvgorod_hub -c "
SELECT 
    c.name as chat_name,
    MAX(m.timestamp) as last_message,
    COUNT(m.id) as message_count
FROM messages m
JOIN chats c ON m.chat_id = c.id
GROUP BY c.name
ORDER BY MAX(m.timestamp) DESC
LIMIT 10;
"
```

### 3. Проверить на дубликаты

```bash
docker exec cvgorod-hub-postgres psql -U cvgorod -d cvgorod_hub -c "
SELECT chat_id, telegram_message_id, COUNT(*) 
FROM messages 
GROUP BY chat_id, telegram_message_id 
HAVING COUNT(*) > 1;
"
```

**Ожидаемый результат**: 0 строк (благодаря уникальному индексу)

## Если возникли проблемы

### Восстановление из бэкапа

```bash
cd /Users/danielbadygov/cvgorod-hub
docker compose down
./scripts/restore_db.sh backups/backup_<timestamp>.sql.gz
docker compose up -d
```

### Проверка логов

```bash
# Логи PostgreSQL
docker logs cvgorod-hub-postgres

# Логи синхронизации (если через скрипт)
ls -lh logs/sync_*.log
```

## Следующие шаги

### Регулярная синхронизация

После успешной первой синхронизации можно настроить автоматическую:

```bash
# Добавить в cron
crontab -e

# Каждый день в 4:00
0 4 * * * cd /Users/danielbadygov/cvgorod-hub && DATABASE_URL="..." python3 scripts/sync_telegram_history.py >> logs/sync_$(date +\%Y\%m\%d).log 2>&1
```

### Мониторинг

Создать дашборд в Grafana:
- Количество сообщений по дням
- Количество новых пользователей
- Активность чатов

---

## Контакты и поддержка

При проблемах:
1. Проверьте логи: `docker logs cvgorod-hub-postgres`
2. Проверьте бэкапы: `ls -lh backups/`
3. Проверьте индекс: 
   ```sql
   SELECT indexname, indexdef FROM pg_indexes 
   WHERE tablename = 'messages' 
   AND indexname = 'idx_messages_chat_telegram_id';
   ```

📖 Документация:
- [Полная инструкция](./TELEGRAM_SYNC_INSTRUCTIONS.md)
- [Краткий справочник](./scripts/README_SYNC.md)
- [Cursor Rules](./.cursorrules)

---

**✅ Готово к запуску!**

Следуйте инструкциям выше для синхронизации истории Telegram сообщений.
