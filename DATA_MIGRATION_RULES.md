# Правила миграции данных и предотвращения потерь

## Проблемы, обнаруженные 14 января 2026

### 1. Данные не были перенесены при создании cvgorod-hub
- **Причина**: При создании нового проекта `cvgorod-hub` данные из старого `cvgorod-bot` (`cvgorod_messages`) не были скопированы
- **Последствие**: База данных `cvgorod_hub` была пустой (0 чатов, 0 пользователей, 0 сообщений)
- **Источник данных**: Volume `cvgorod_postgres_data` с базой `cvgorod_messages`

### 2. Миграции не были применены
- **Причина**: Скрипты миграции (`migrate_add_roles.sql`, `migrate_add_sentiment.sql`) существовали, но не применялись автоматически
- **Последствие**: Отсутствовали колонки `role`, `sentiment`, `is_automatic`, `intent` в таблице `messages`

### 3. Отсутствовали бэкапы
- **Причина**: Директория `backups/` была пустой, автоматический бэкап не был настроен
- **Последствие**: Риск полной потери данных

---

## ПРАВИЛА (ОБЯЗАТЕЛЬНЫ К ВЫПОЛНЕНИЮ)

### Правило 1: Бэкап ПЕРЕД любыми изменениями БД

```bash
# ВСЕГДА выполнять перед:
# - Миграциями
# - Обновлением docker-compose
# - Изменением схемы БД
# - Деплоем новой версии

./scripts/backup_db.sh
```

### Правило 2: Проверка данных ПОСЛЕ миграции

```bash
# После ЛЮБОЙ миграции выполнить:
docker exec cvgorod-hub-postgres psql -U cvgorod -d cvgorod_hub -c "
SELECT 'chats' as tbl, COUNT(*) FROM chats
UNION ALL SELECT 'users', COUNT(*) FROM users  
UNION ALL SELECT 'messages', COUNT(*) FROM messages;
"
```

**Ожидаемый минимум**: >200 чатов, >200 пользователей, >40000 сообщений

### Правило 3: Никогда не удалять Docker Volumes без бэкапа

```bash
# ЗАПРЕЩЕНО без бэкапа:
docker volume rm cvgorod-hub_postgres_data  # НЕТ!
docker-compose down -v                       # НЕТ!

# ПРАВИЛЬНО:
./scripts/backup_db.sh
docker-compose down  # Без -v!
```

### Правило 4: При создании нового проекта - скрипт миграции данных

При создании нового проекта из существующего ОБЯЗАТЕЛЬНО:

1. Создать бэкап старого проекта
2. Написать скрипт миграции данных
3. Выполнить миграцию
4. Проверить количество записей
5. Создать бэкап нового проекта

### Правило 5: Автоматический ежедневный бэкап

Настроен cron job:
```
0 3 * * * /home/badygovdaniil/cvgorod-hub/scripts/auto_backup.sh
```

Проверять наличие бэкапов еженедельно:
```bash
ls -la /home/badygovdaniil/cvgorod-hub/backups/
```

### Правило 6: Проверка схемы после деплоя

После каждого деплоя проверять наличие всех колонок:

```sql
SELECT column_name FROM information_schema.columns 
WHERE table_name = 'messages' 
ORDER BY ordinal_position;
```

**Обязательные колонки**:
- id, telegram_message_id, chat_id, user_id, text
- message_type, reply_to_message_id, pattern_id, timestamp, created_at
- role, sentiment, is_automatic, intent, intent_confidence, is_reply

---

## Чек-лист при деплое

- [ ] Создан бэкап: `./scripts/backup_db.sh`
- [ ] Проверено количество записей (chats > 200, messages > 40000)
- [ ] Применены все миграции
- [ ] Проверены все колонки в таблицах
- [ ] Автобэкап в cron работает

---

## Восстановление из бэкапа

```bash
# 1. Найти последний бэкап
ls -la /home/badygovdaniil/cvgorod-hub/backups/

# 2. Остановить сервисы (кроме postgres)
docker-compose stop api bot

# 3. Восстановить
zcat backups/backup_XXXXXXXX_XXXXXX.sql.gz | docker exec -i cvgorod-hub-postgres psql -U cvgorod -d cvgorod_hub

# 4. Запустить сервисы
docker-compose up -d
```

---

## Контакты источников данных

| Проект | Volume | База | Порт |
|--------|--------|------|------|
| cvgorod-hub | cvgorod-hub_postgres_data | cvgorod_hub | 5433 |
| cvgorod-bot (старый) | cvgorod_postgres_data | cvgorod_messages | - |
| cvgorod-agent | cvgorod-agent_postgres_data | cvgorod_agent | - |

---

*Создано: 14 января 2026*
*После инцидента с потерей данных*
