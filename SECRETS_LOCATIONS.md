# Расположение секретов cvgorod-hub

> **ВАЖНО**: Все секреты хранятся в `~/.secrets/` и НЕ дублируются в других местах!

## DEV (локальная разработка)

| Секрет | Расположение | Описание |
|--------|--------------|----------|
| `TELEGRAM_BOT_TOKEN` | `~/.secrets/telegram/cvgorod_hub.token` | Токен бота @cvgorodassistent_bot |
| `HUB_API_KEY` | `~/.secrets/cvgorod/hub_api.env` | API ключ для авторизации |
| `DEEPSEEK_API_KEY` | `~/.secrets/cloud/deepseek.env` | API ключ DeepSeek |
| `POSTGRES_PASSWORD` | `~/.secrets/databases/cvgorod.env` | Пароль PostgreSQL |
| `TRACKER_TOKEN` | `~/.secrets/yandex/tracker.env` | Токен Yandex Tracker |

### Загрузка секретов на DEV

Секреты автоматически загружаются через `config/settings.py`:
1. Сначала `.env` файл (низкий приоритет)
2. Затем файлы из `~/.secrets/` (высокий приоритет, перезаписывают `.env`)

## PROD (сервер 158.160.153.14)

| Секрет | Расположение | Описание |
|--------|--------------|----------|
| `TELEGRAM_BOT_TOKEN` | `~/.secrets/telegram/cvgorod_hub.token` | Токен бота |
| `HUB_API_KEY` | `~/.secrets/cvgorod/hub_api.env` | API ключ |
| `DEEPSEEK_API_KEY` | `~/.secrets/cloud/deepseek.env` | API ключ DeepSeek |
| `POSTGRES_PASSWORD` | Docker Compose переменная | Пароль PostgreSQL |
| `TRACKER_TOKEN` | `~/.secrets/yandex/tracker.env` | Токен Yandex Tracker |

### Docker Compose на PROD

В `docker-compose.yml` секреты загружаются через:
```yaml
environment:
  - TELEGRAM_BOT_TOKEN  # Берётся из окружения хоста
  - DATABASE_URL=${DATABASE_URL:-postgresql://cvgorod:${POSTGRES_PASSWORD}@postgres:5432/cvgorod_hub}
volumes:
  - ${HOME}/.secrets:/root/.secrets:ro  # Монтируется внутрь контейнера
```

## Структура ~/.secrets/

```
~/.secrets/
├── telegram/
│   ├── cvgorod_hub.token    # TELEGRAM_BOT_TOKEN для cvgorod-hub
│   ├── cvgorod_agent.env    # TELEGRAM_BOT_TOKEN для cvgorod-agent  
│   └── cvgorod.env          # Старый файл (НЕ ИСПОЛЬЗОВАТЬ для hub!)
├── cvgorod/
│   ├── hub_api.env          # HUB_API_KEY
│   └── agent.env            # Настройки агента
├── cloud/
│   └── deepseek.env         # DEEPSEEK_API_KEY
├── databases/
│   └── cvgorod.env          # POSTGRES_PASSWORD (опционально)
└── yandex/
    └── tracker.env          # TRACKER_TOKEN, TRACKER_ORG_ID
```

## Формат файлов секретов

### cvgorod_hub.token
```env
TELEGRAM_BOT_TOKEN=8524184664:AAFWgTANskxKN4CErS5TAShmyaQSCKsp6kQ
```

### hub_api.env
```env
HUB_API_KEY=your-secure-api-key-here
HUB_API_URL=http://cvgorod-hub-api:8000  # Для Docker network
```

### deepseek.env
```env
DEEPSEEK_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

## ПРАВИЛА (обязательны к выполнению)

### ✅ ПРАВИЛЬНО
- Секреты хранятся ТОЛЬКО в `~/.secrets/`
- В `.env` только переменные без чувствительных данных
- `docker-compose.yml` использует `${VARIABLE}` подстановку

### ❌ ЗАПРЕЩЕНО
- Хардкодить пароли/токены в коде
- Дублировать токены в нескольких файлах
- Коммитить `.env` файлы с секретами
- Использовать разные токены для одного бота

## Проверка секретов

### DEV
```bash
# Проверить загруженные секреты
python -c "from config import settings; print(settings.TELEGRAM_BOT_TOKEN[:20])"
```

### PROD
```bash
ssh badygovdaniil@158.160.153.14
cat ~/.secrets/telegram/cvgorod_hub.token
docker exec cvgorod-hub-bot env | grep TELEGRAM
```

## Миграция на новую структуру

Если секреты раньше были в `.env`:

1. Создайте файлы в `~/.secrets/`
2. Удалите секреты из `.env`
3. Перезапустите сервисы
4. Проверьте работу

---

*Создано: 14 января 2026*
*После инцидента с дублированием токенов*
