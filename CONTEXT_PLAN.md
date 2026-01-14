# Контекст и план работы - cvgorod-hub

## Текущая проблема

**Симптом:** Бот добавлен в группу, видит сообщения (Group Privacy = OFF), но сообщения не сохраняются в базу данных.

**Факты:**
- Бот `cvgorodassistent_bot` добавлен в группу
- Group Privacy отключен (бот видит все сообщения)
- Сообщение от Шамхала было отправлено, но не найдено в БД
- В старом проекте "Цветущий город бот" все работало корректно

## Сравнение старого и нового проекта

### Старый проект (`/Users/danielbadygov/Цветущий городбот/`)

**Структура:**
```python
# bot/admin_bot.py
class AdminBot:
    def __init__(self):
        # ...
        message_collector.register_handlers(self.application)  # В __init__
    
    async def _on_startup(self, app: Application):
        await db.connect()
        await message_collector.initialize()  # В post_init
    
    def run(self):
        self.application.run_polling(
            drop_pending_updates=True,
            stop_signals=(),
            poll_interval=1.0,
            timeout=30,
        )
```

### Новый проект (`/Users/danielbadygov/cvgorod-hub/`)

**Структура:**
```python
# bot/collector.py
async def main():
    await db.connect()
    await init_tracker()
    
    application = Application.builder().token(...).build()
    message_collector.register_handlers(application)  # До start_polling
    await message_collector.initialize()  # До start_polling
    
    await application.initialize()
    await application.start()
    await application.updater.start_polling(...)
    
    await asyncio.Event().wait()  # Бесконечное ожидание
```

## Ключевые отличия для проверки

1. **Порядок инициализации:**
   - Старый: `register_handlers` в `__init__`, `initialize` в `post_init`
   - Новый: оба до `start_polling`

2. **Метод запуска:**
   - Старый: `run_polling()` (синхронный)
   - Новый: `start_polling()` (асинхронный) + `asyncio.Event().wait()`

3. **Обработчики:**
   - Проверить, что `MessageHandler` правильно регистрируется
   - Проверить, что `handle_update` вызывается для всех сообщений

## План отладки

### Шаг 1: Проверить логи бота
```bash
docker logs --tail 100 cvgorod-hub-bot 2>&1 | grep -E 'Message|handle_update|register'
```

### Шаг 2: Добавить детальное логирование
- Добавить логи в `handle_update` (начало/конец)
- Добавить логи в `register_handlers`
- Добавить логи в `_save_to_database`

### Шаг 3: Проверить фильтры MessageHandler
- Убедиться, что `filters.TEXT & ~filters.COMMAND` не блокирует сообщения
- Проверить, что сообщения не игнорируются из-за `is_bot` или других условий

### Шаг 4: Сравнить MessageCollector
- Проверить, что `services/message_collector.py` идентичен старому
- Убедиться, что `register_handlers` вызывается правильно

### Шаг 5: Проверить базу данных
- Убедиться, что `db.connect()` успешно выполняется
- Проверить, что нет ошибок при INSERT

## Текущее состояние проекта

- ✅ Бот запущен и работает
- ✅ База данных подключена
- ✅ Миграция данных выполнена (40,579 сообщений)
- ✅ Токен обновлен (`cvgorodassistent_bot`)
- ❌ Новые сообщения не сохраняются

## Файлы для проверки

1. `/Users/danielbadygov/cvgorod-hub/bot/collector.py` - главный файл бота
2. `/Users/danielbadygov/cvgorod-hub/services/message_collector.py` - логика сбора сообщений
3. `/Users/danielbadygov/Цветущий городбот/bot/admin_bot.py` - рабочий пример

## Команды для проверки

```bash
# Проверить логи
docker logs --tail 200 cvgorod-hub-bot 2>&1

# Проверить последние сообщения в БД
docker compose exec postgres psql -U cvgorod_user -d cvgorod_hub -c "SELECT id, chat_id, user_id, text, timestamp FROM messages ORDER BY timestamp DESC LIMIT 10;"

# Проверить статус бота
docker ps | grep cvgorod-hub-bot
```

## Следующие шаги

1. Добавить детальное логирование в `handle_update`
2. Проверить, вызывается ли `handle_update` вообще
3. Сравнить точную логику обработки сообщений со старым проектом
4. Проверить фильтры и условия в `handle_update`
