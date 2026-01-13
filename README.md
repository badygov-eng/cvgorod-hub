# cvgorod-hub

CRM Message Hub — сбор сообщений из Telegram, LLM-обработка, REST API.

## 📊 Архитектура

```
cvgorod-hub/
├── api/                    # FastAPI REST API
│   ├── main.py             # Главный файл приложения
│   ├── auth.py             # API Key авторизация
│   └── routes/
│       ├── messages.py     # /api/v1/messages
│       ├── clients.py      # /api/v1/clients
│       ├── intents.py      # /api/v1/intents
│       └── send.py         # /api/v1/send + песочница
├── bot/
│   ├── collector.py        # Сбор сообщений из Telegram
│   ├── sandbox_manager.py  # Управление песочницей
│   └── sender.py           # Отправка одобренных сообщений
├── services/
│   ├── database.py         # PostgreSQL async клиент
│   ├── intent_classifier.py # LLM классификация (DeepSeek)
│   ├── role_repository.py  # Работа с ролями
│   └── yandex_stt.py       # Yandex Speech-to-Text
├── config/
│   ├── settings.py         # Конфигурация
│   └── roles.py            # Роли пользователей
└── docker-compose.yml      # Оркестрация контейнеров
```

## 🔌 API Endpoints

### Messages
| Method | Endpoint | Описание |
|--------|----------|----------|
| GET | `/api/v1/messages` | Список сообщений с фильтрами |
| GET | `/api/v1/messages/{id}` | Конкретное сообщение |
| GET | `/api/v1/messages/stats/total` | Статистика сообщений |

### Clients
| Method | Endpoint | Описание |
|--------|----------|----------|
| GET | `/api/v1/clients` | Список клиентов |
| GET | `/api/v1/clients/{id}/messages` | Сообщения клиента |
| GET | `/api/v1/clients/stats/active` | Активные клиенты |

### Intents (LLM анализ)
| Method | Endpoint | Описание |
|--------|----------|----------|
| GET | `/api/v1/intents` | Статистика по интентам |
| GET | `/api/v1/intents/daily` | Ежедневная статистика |
| GET | `/api/v1/intents/urgent` | Срочные сообщения |

### Send (Песочница)
| Method | Endpoint | Описание |
|--------|----------|----------|
| POST | `/api/v1/send` | Создать запрос на отправку |
| GET | `/api/v1/sandbox/pending` | Ожидающие сообщения |
| POST | `/api/v1/sandbox/{id}/approve` | Одобрить отправку |
| POST | `/api/v1/sandbox/{id}/reject` | Отклонить отправку |

## 🚀 Запуск

### Среды выполнения

Проект поддерживает три среды: development, staging, production.

| Среда | Порт | Назначение | .env файл |
|-------|------|------------|-----------|
| Development | 8308 | Локальная разработка | .env.dev |
| Staging | 8309 | Тестирование | .env.staging |
| Production | 8300 | Продакшн | .env.prod |

### Локально (Development)

```bash
# 1. Установить зависимости
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 2. Скопировать .env файл для разработки
cp .env.example .env.dev
# Или для быстрого старта:
cp .env.dev .env

# 3. Запустить PostgreSQL и Redis
docker compose up -d postgres redis

# 4. Инициализировать БД
psql $DATABASE_URL -f scripts/init_db.sql

# 5. Запустить API в режиме разработки
ENVIRONMENT=development python main.py
# API будет доступен на http://localhost:8308
```

### Staging

```bash
# Использует .env.staging
ENVIRONMENT=staging python main.py
# API будет доступен на http://localhost:8309
```

### Docker

```bash
# Полный стек
docker compose up -d

# Только API
docker compose up -d api

# С указанием environment
ENVIRONMENT=production docker compose up -d
```

## 🧪 Тестирование

### Запуск тестов

```bash
# Все тесты
pytest tests/ -v

# Только unit-тесты
pytest tests/unit/ -v

# Только интеграционные тесты
pytest tests/integration/ -v -m integration

# E2E тесты
pytest tests/e2e/ -v -m e2e

# С покрытием
pytest tests/ --cov=api --cov=services --cov=config

# Пропустить медленные тесты
pytest tests/ -m "not slow"
```

### Тестовые маркеры

- `integration` — тесты, требующие внешние сервисы (БД, API)
- `e2e` — полные сценарии (end-to-end)
- `slow` — медленные тесты (пропускаются с `-m "not slow"`)

## 📦 Порты

| Сервис | Dev | Staging | Production | Docker |
|--------|-----|---------|------------|--------|
| API | 8308 | 8309 | 8300 | 8000 |
| PostgreSQL | 5433 | 5433 | — | 5432 |
| Redis | 6380 | 6380 | — | 6379 |

## 🐳 Docker Compose

Сеть: `cvgorod-net` (общая с cvgorod-agent)

```yaml
services:
  api:          # FastAPI
  bot:          # Telegram bot collector
  redis:        # Кэш и очереди
  postgres:     # Основная БД
```

## 🚀 Деплой в Production

### Предварительные требования

1. Скопируйте `cp .env.prod .env` и заполните production значения
2. Убедитесь что сервис настроен в systemd

### Деплой

```bash
# С автоматическим бэкапом
./deploy/deploy-prod.sh

# Без бэкапа (быстрее)
./deploy/deploy-prod.sh --no-backup
```

### Systemd сервис

Сервис: `cvgorod-hub.service`

```bash
# Управление
sudo systemctl status cvgorod-hub
sudo systemctl restart cvgorod-hub
sudo systemctl stop cvgorod-hub

# Логи
sudo journalctl -u cvgorod-hub -f
sudo journalctl -u cvgorod-hub -n 100
```

### Синхронизация данных

```bash
# Скачать данные с production
./deploy/pull-data.sh              # всё
./deploy/pull-data.sh --db         # только БД
./deploy/pull-data.sh --redis      # только Redis

# Загрузить данные на production
./deploy/push-data.sh --all        # всё (с подтверждением)
./deploy/push-data.sh --db backup.sql.gz
./deploy/push-data.sh --redis dump.rdb
```

## 📊 MCP Интеграция

Проект интегрирован с MCP (Management Control Platform):

### Shared модули

- `MCP.shared.llm.DeepSeekClient` — LLM для классификации интентов
- `MCP.shared.secrets_loader` — централизованная загрузка секретов
- `MCP.shared.billing` — мониторинг биллинга DeepSeek

### Проверка биллинга

```bash
# Через MCP CLI
mcp billing --project cvgorod-hub
```

## 🔧 Разработка

### Структура тестов

```
tests/
├── __init__.py
├── conftest.py           # Shared fixtures
├── unit/                 # Быстрые тесты без внешних зависимостей
│   ├── test_services.py
│   └── test_intent_classifier.py
├── integration/          # Тесты с БД/API
│   └── test_api.py
└── e2e/                  # Полные сценарии
    └── test_workflow.py
```

### Добавление тестов

1. Создайте файл в соответствующей директории
2. Используйте fixtures из `conftest.py`
3. Добавьте маркеры если нужны (`@pytest.mark.integration`)

## 🔐 Авторизация

Все API endpoints требуют `X-API-Key` header:

```bash
curl -H "X-API-Key: your-secret-key" \
     http://localhost:8300/api/v1/messages
```

## 📦 Порты

| Сервис | Порт (локальный) | Порт (Docker) |
|--------|------------------|---------------|
| API | 8300 | 8000 |
| PostgreSQL | 5433 | 5432 |
| Redis | 6380 | 6379 |

## 🔑 Секреты

Хранятся в `~/.secrets/`:

```
~/.secrets/
├── telegram/cvgorod.env    # TELEGRAM_BOT_TOKEN
├── cvgorod/hub_api.env     # HUB_API_KEY
└── cloud/deepseek.env      # DEEPSEEK_API_KEY
```

## 🗃️ База данных

### Таблицы

- `chats` — Telegram чаты (группы/личные)
- `users` — Пользователи с ролями
- `messages` — Сообщения с FTS по русскому
- `message_analysis` — LLM классификация
- `pending_responses` — Песочница ответов
- `user_roles` — Справочник ролей
- `message_patterns` — Паттерны сообщений

### Роли пользователей

| Роль | is_staff | is_bot | Описание |
|------|----------|--------|----------|
| admin | ✅ | ❌ | Администратор |
| director | ✅ | ❌ | Директор по продажам |
| manager | ✅ | ❌ | Менеджер |
| broadcast_bot | ❌ | ✅ | Бот рассылки |
| assistant_bot | ❌ | ✅ | AI Ассистент |
| client | ❌ | ❌ | Клиент (по умолчанию) |

### Типы интентов

| Интент | Описание |
|--------|----------|
| question | Вопрос клиента |
| order | Заказ |
| complaint | Жалоба |
| interest | Интерес к товару |
| confirmation | Подтверждение |
| broadcast | Рассылка бота |

## 🔗 Связь с cvgorod-agent

Hub предоставляет REST API для CodeAct Agent:

```
cvgorod-agent --> cvgorod-hub (через HUB_API_URL)
    |
    ├── GET /api/v1/messages    # Чтение сообщений
    ├── GET /api/v1/clients     # Список клиентов
    ├── GET /api/v1/intents     # Статистика
    └── POST /api/v1/send       # Отправка через песочницу
```

## 🧪 Тестирование

```bash
# Запуск тестов
pytest tests/ -v

# С покрытием
pytest tests/ --cov=api --cov=services
```

## 📝 Миграции

```bash
# Миграция из старой БД
python scripts/migrate_from_old.py
```

## 🐳 Docker Compose

Сеть: `cvgorod-net` (общая с cvgorod-agent)

```yaml
services:
  api:          # FastAPI на порту 8300
  bot:          # Telegram bot collector
  redis:        # Кэш и очереди
  postgres:     # Основная БД
```

---

**Проект:** Цветущий город (cvgorod)
**Порты:** 8300-8399 (диапазон)
**Связь:** cvgorod-agent подключается к Hub API
