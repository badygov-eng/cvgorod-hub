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

### Локально

```bash
# 1. Установить зависимости
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 2. Создать .env файл
cp .env.example .env
# Заполнить переменные

# 3. Запустить PostgreSQL и Redis
docker compose up -d postgres redis

# 4. Инициализировать БД
psql $DATABASE_URL -f scripts/init_db.sql

# 5. Запустить API
python main.py
```

### Docker

```bash
# Полный стек
docker compose up -d

# Только API
docker compose up -d api
```

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
