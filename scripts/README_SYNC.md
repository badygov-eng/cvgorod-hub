# Telegram Sync Scripts

Скрипты для синхронизации истории сообщений из Telegram в cvgorod-hub через Telegram MCP.

## Файлы

| Файл | Описание |
|------|----------|
| `sync_telegram_history.py` | **Основной скрипт** синхронизации сообщений |
| `test_telegram_mcp.py` | Тестовый скрипт для проверки Telegram MCP |
| `migrate_add_unique_message_index.sql` | SQL миграция (уже применена) |

## Быстрый старт

### 1. Подготовка

```bash
cd /Users/danielbadygov/cvgorod-hub

# Бэкап БД (ОБЯЗАТЕЛЬНО!)
./scripts/backup_db.sh

# Проверить что PostgreSQL запущен
docker ps | grep cvgorod-hub-postgres
```

### 2. Тестовый запуск (dry-run)

```bash
DATABASE_URL="postgresql://cvgorod:cvgorod_secret_2024@localhost:5433/cvgorod_hub" \
python3 scripts/sync_telegram_history.py --dry-run --limit=5
```

### 3. Полная синхронизация (требует Telegram MCP)

**⚠️ Telegram MCP должен быть запущен в Cursor!**

Для полной синхронизации с загрузкой сообщений из Telegram:

1. Откройте Cursor
2. Убедитесь что Telegram MCP активен (Settings → MCP)
3. Попросите AI выполнить следующее:

```
Используй Telegram MCP для синхронизации сообщений:

1. Найди все группы с "cvgorod" в названии:
   mcp_mcp-telegram_search_dialogs(query="cvgorod", limit=50)

2. Для каждой группы получи последние сообщения:
   mcp_mcp-telegram_get_messages(entity="<chat_id>", limit=1000)

3. Сохрани сообщения в PostgreSQL используя скрипт sync_telegram_history.py
```

## Что делает скрипт

1. **Подключается к PostgreSQL** и получает список всех активных чатов
2. **Для каждого чата**:
   - Находит последнее сохраненное сообщение
   - Загружает новые сообщения из Telegram (через MCP)
   - Сохраняет недостающие сообщения в БД
3. **Предотвращает дубликаты** через уникальный индекс на (chat_id, telegram_message_id)

## Опции командной строки

| Опция | Описание |
|-------|----------|
| `--dry-run` | Тестовый режим (не сохраняет в БД) |
| `--limit=N` | Лимит сообщений на чат (для тестирования) |

## Примеры использования

### Тест на 1 сообщение на чат

```bash
DATABASE_URL="postgresql://cvgorod:cvgorod_secret_2024@localhost:5433/cvgorod_hub" \
python3 scripts/sync_telegram_history.py --dry-run --limit=1
```

### Синхронизация с ограничением

```bash
DATABASE_URL="postgresql://cvgorod:cvgorod_secret_2024@localhost:5433/cvgorod_hub" \
python3 scripts/sync_telegram_history.py --limit=100
```

### Полная синхронизация

```bash
DATABASE_URL="postgresql://cvgorod:cvgorod_secret_2024@localhost:5433/cvgorod_hub" \
python3 scripts/sync_telegram_history.py
```

## Интеграция с Telegram MCP

### Что такое Telegram MCP?

Telegram MCP — это MCP сервер который работает через личный аккаунт Telegram (@badygovd) и позволяет:
- Искать диалоги
- Получать историю сообщений
- Отправлять/редактировать/удалять сообщения
- Скачивать медиа

### Как использовать в скрипте?

В скрипте `sync_telegram_history.py` есть два метода которые нужно доработать для интеграции с Telegram MCP:

#### 1. `find_groups_with_bot()` — поиск групп

Замените заглушку на:

```python
# Поиск через Telegram MCP
search_queries = ["cvgorod", "букет", "Chat Cvgorod"]
for query in search_queries:
    dialogs = mcp_mcp-telegram_search_dialogs(query=query, limit=50)
    for dialog in dialogs:
        if dialog['type'] in ['group', 'supergroup']:
            groups.append({
                'id': dialog['id'],
                'name': dialog['title'],
                'chat_type': dialog['type']
            })
```

#### 2. `fetch_messages_from_telegram()` — загрузка сообщений

Замените заглушку на:

```python
# Загрузка через Telegram MCP
telegram_messages = mcp_mcp-telegram_get_messages(
    entity=str(chat_id),
    limit=limit or 1000,
    offset_id=min_id
)

for msg in telegram_messages:
    messages.append({
        "message_id": msg.id,
        "user_id": msg.from_id.user_id,
        "username": msg.from_user.username,
        "first_name": msg.from_user.first_name,
        "text": msg.text or msg.caption,
        "timestamp": msg.date,
        "message_type": "text",  # или определить по msg.media
        "reply_to_message_id": msg.reply_to_msg_id
    })
```

## Статистика

После выполнения скрипт выводит:

```
================================================================================
СТАТИСТИКА СИНХРОНИЗАЦИИ
================================================================================
Чатов найдено:         277
Чатов обработано:      277
Сообщений загружено:   12450
Сообщений сохранено:   12430
Сообщений пропущено:   20  (дубликаты)
Пользователей создано: 85
Ошибок:                0
================================================================================
```

## Проверка результатов

### Количество записей

```bash
docker exec cvgorod-hub-postgres psql -U cvgorod -d cvgorod_hub -c "
SELECT 'messages' as table, COUNT(*) FROM messages;
"
```

### Последние сообщения по чатам

```bash
docker exec cvgorod-hub-postgres psql -U cvgorod -d cvgorod_hub -c "
SELECT c.name, MAX(m.timestamp) as last_msg 
FROM messages m 
JOIN chats c ON m.chat_id = c.id 
GROUP BY c.name 
ORDER BY last_msg DESC 
LIMIT 10;
"
```

### Проверка на дубликаты (должно быть 0)

```bash
docker exec cvgorod-hub-postgres psql -U cvgorod -d cvgorod_hub -c "
SELECT COUNT(*) FROM (
    SELECT chat_id, telegram_message_id 
    FROM messages 
    GROUP BY chat_id, telegram_message_id 
    HAVING COUNT(*) > 1
) duplicates;
"
```

## Восстановление из бэкапа

Если что-то пошло не так:

```bash
cd /Users/danielbadygov/cvgorod-hub

# Остановить контейнеры
docker compose down

# Восстановить БД
./scripts/restore_db.sh backups/backup_YYYYMMDD_HHMMSS.sql.gz

# Запустить обратно
docker compose up -d
```

## Troubleshooting

### Telegram MCP не доступен

- Проверьте что MCP запущен в Cursor (Settings → MCP)
- Проверьте `~/.cursor/mcp.json` для конфигурации `mcp-telegram`
- Убедитесь что есть активная Telegram сессия

### База данных недоступна

```bash
# Проверить статус
docker ps | grep cvgorod-hub-postgres

# Запустить если не работает
docker compose up -d postgres

# Посмотреть логи
docker logs cvgorod-hub-postgres
```

### Rate Limits от Telegram

- Увеличьте паузу между запросами (sleep в коде)
- Используйте `--limit=N` для ограничения
- Запускайте синхронизацию в нерабочее время

## Автоматизация

Добавьте в cron для регулярной синхронизации:

```bash
crontab -e

# Каждый день в 4:00 утра
0 4 * * * cd /Users/danielbadygov/cvgorod-hub && DATABASE_URL="postgresql://cvgorod:cvgorod_secret_2024@localhost:5433/cvgorod_hub" python3 scripts/sync_telegram_history.py >> logs/sync_$(date +\%Y\%m\%d).log 2>&1
```

## Связанные документы

- [Полная инструкция](../TELEGRAM_SYNC_INSTRUCTIONS.md)
- [Cursor Rules](./../.cursorrules) — секция "Telegram MCP"
- [MCP Services Registry](/Users/danielbadygov/MCP/MCP_SERVICES_REGISTRY.md)

---

**Важно**: Всегда делайте бэкап перед синхронизацией!
