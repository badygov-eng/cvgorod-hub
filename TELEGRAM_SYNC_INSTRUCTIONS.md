# Инструкция по синхронизации сообщений из Telegram

## Предварительные требования

1. **Telegram MCP должен быть запущен** в Cursor
   - Проверьте в `~/.cursor/mcp.json` что `mcp-telegram` настроен
   - MCP работает через личный аккаунт @badygovd

2. **База данных должна быть доступна**
   - Локально: `postgresql://cvgorod:cvgorod_secret_2024@localhost:5433/cvgorod_hub`
   - Docker контейнер должен быть запущен: `docker compose up -d postgres`

## Подготовка к синхронизации

### 1. Сделать бэкап базы данных (ОБЯЗАТЕЛЬНО!)

```bash
cd /Users/danielbadygov/cvgorod-hub
./scripts/backup_db.sh
```

Проверьте что бэкап создан:
```bash
ls -lh backups/
```

### 2. Проверить текущее состояние БД

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

Ожидаемый результат (до синхронизации):
- chats: ~277
- users: ~244  
- messages: ~40579

## Запуск синхронизации

### Режим 1: Dry-run (тестирование, без сохранения)

```bash
cd /Users/danielbadygov/cvgorod-hub

# С ограничением на 5 сообщений на чат
DATABASE_URL="postgresql://cvgorod:cvgorod_secret_2024@localhost:5433/cvgorod_hub" \
python3 scripts/sync_telegram_history.py --dry-run --limit=5
```

### Режим 2: Тестовая синхронизация (1 чат, с сохранением)

Для тестирования можно временно изменить SQL запрос в скрипте:
```python
# В функции find_groups_with_bot():
query = "SELECT id, name, chat_type FROM chats WHERE is_active = TRUE LIMIT 1"
```

Затем запустить:
```bash
DATABASE_URL="postgresql://cvgorod:cvgorod_secret_2024@localhost:5433/cvgorod_hub" \
python3 scripts/sync_telegram_history.py --limit=100
```

### Режим 3: Полная синхронизация

**⚠️ ПЕРЕД ЗАПУСКОМ УБЕДИТЕСЬ ЧТО СДЕЛАН БЭКАП!**

```bash
cd /Users/danielbadygov/cvgorod-hub

# Полная синхронизация ВСЕХ чатов
DATABASE_URL="postgresql://cvgorod:cvgorod_secret_2024@localhost:5433/cvgorod_hub" \
python3 scripts/sync_telegram_history.py
```

Процесс может занять несколько часов в зависимости от объёма данных.

## Интеграция с Telegram MCP

Скрипт использует следующие функции Telegram MCP:

### 1. Поиск групп с ботом

```python
# Поиск через search_dialogs
# Telegram MCP: mcp_mcp-telegram_search_dialogs(query="cvgorod", limit=50)
```

### 2. Получение сообщений

```python
# Получение истории
# Telegram MCP: mcp_mcp-telegram_get_messages(
#     entity=str(chat_id),
#     limit=100,
#     min_id=last_message_id  # Загружать после последнего
# )
```

### 3. Структура возвращаемых сообщений

Telegram MCP возвращает сообщения в формате:
```json
{
    "message_id": 123,
    "user_id": 456789,
    "username": "client_user",
    "first_name": "Иван",
    "last_name": "Иванов",
    "text": "Текст сообщения",
    "timestamp": "2026-01-14T10:30:00",
    "message_type": "text",
    "reply_to_message_id": null
}
```

## Мониторинг процесса

Скрипт выводит детальную статистику:
- Количество найденных чатов
- Обработанные чаты
- Загруженные сообщения
- Сохранённые сообщения
- Ошибки

Пример вывода:
```
================================================================================
СИНХРОНИЗАЦИЯ TELEGRAM → cvgorod-hub
================================================================================

Найдено 277 активных чатов в базе

[1/277] Обработка...
============================================================
Чат: Абрамов Игорь CHAT CVGOROD (ID: -4701259304)
============================================================
  Последнее сообщение в БД: ID=42, время=2025-12-20 15:30:00
  Загрузка сообщений из Telegram (chat_id=-4701259304, min_id=42)...
  Загружено 15 сообщений из Telegram
  Обработка 15 сообщений...
  ✓ Чат обработан: сохранено 15 новых сообщений
...
```

## Проверка после синхронизации

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

### 3. Проверить на дубликаты (не должно быть)

```bash
docker exec cvgorod-hub-postgres psql -U cvgorod -d cvgorod_hub -c "
SELECT chat_id, telegram_message_id, COUNT(*) 
FROM messages 
GROUP BY chat_id, telegram_message_id 
HAVING COUNT(*) > 1;
"
```

Результат должен быть пустым благодаря уникальному индексу.

## Устранение проблем

### Telegram MCP не доступен

Проверьте:
1. MCP сервер запущен в Cursor (Settings → MCP)
2. Есть активная сессия Telegram (файл `.session` существует)
3. Telegram MCP настроен в `~/.cursor/mcp.json`

### Rate Limits от Telegram

Если получаете ошибки rate limit:
- Увеличьте паузу между запросами в скрипте (sleep от 0.5 до 2 секунд)
- Используйте `--limit=N` для ограничения количества сообщений

### База данных недоступна

```bash
# Проверить статус контейнера
docker ps | grep cvgorod-hub-postgres

# Если не запущен - запустить
cd /Users/danielbadygov/cvgorod-hub
docker compose up -d postgres

# Проверить логи
docker logs cvgorod-hub-postgres
```

## Восстановление из бэкапа (если что-то пошло не так)

```bash
cd /Users/danielbadygov/cvgorod-hub

# Остановить контейнеры
docker compose down

# Восстановить из последнего бэкапа
./scripts/restore_db.sh backups/backup_YYYYMMDD_HHMMSS.sql.gz

# Запустить контейнеры обратно
docker compose up -d
```

## Автоматизация (опционально)

Можно добавить в cron для регулярной синхронизации:

```bash
# crontab -e
# Каждый день в 04:00
0 4 * * * cd /Users/danielbadygov/cvgorod-hub && DATABASE_URL="postgresql://cvgorod:cvgorod_secret_2024@localhost:5433/cvgorod_hub" python3 scripts/sync_telegram_history.py >> logs/sync_$(date +\%Y\%m\%d).log 2>&1
```

## Контакты

При проблемах:
- Проверьте логи: `logs/sync_*.log`
- Проверьте статус БД: `docker logs cvgorod-hub-postgres`
- Проверьте MCP: Settings → MCP в Cursor

---

**Важно**: Всегда делайте бэкап перед синхронизацией!
