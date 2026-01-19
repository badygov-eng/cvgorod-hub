-- ============================================================
-- Миграция: Добавление маппинга customer_uuid из УЗ API
-- Дата: 2026-01-19
-- Причина: Поддержка отправки по UUID клиента из заказов УЗ
-- ============================================================

-- Таблица маппинга UUID клиентов из УЗ API
CREATE TABLE IF NOT EXISTS customer_uuid_mapping (
    customer_uuid UUID PRIMARY KEY,          -- UUID из УЗ API (customerID)
    cvgorod_chat_id INTEGER,                 -- ID чата в CVGorod API
    chat_id BIGINT,                          -- telegram_chat_id
    customer_name TEXT,                      -- Название чата/клиента
    sync_id VARCHAR(50),                     -- 1С ID "КА-..."
    source TEXT DEFAULT 'uz_api',            -- Источник данных
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Индексы для быстрого поиска
CREATE INDEX IF NOT EXISTS idx_uuid_mapping_cvgorod ON customer_uuid_mapping(cvgorod_chat_id);
CREATE INDEX IF NOT EXISTS idx_uuid_mapping_chat ON customer_uuid_mapping(chat_id);
CREATE INDEX IF NOT EXISTS idx_uuid_mapping_sync ON customer_uuid_mapping(sync_id);

-- Комментарии
COMMENT ON TABLE customer_uuid_mapping IS 'Маппинг UUID клиентов из УЗ API на telegram chat_id';
COMMENT ON COLUMN customer_uuid_mapping.customer_uuid IS 'UUID клиента из УЗ API /Messages/ChatBots (customerID)';
COMMENT ON COLUMN customer_uuid_mapping.cvgorod_chat_id IS 'ID чата в CVGorod API (id из /Messages/ChatBots)';
COMMENT ON COLUMN customer_uuid_mapping.chat_id IS 'Telegram chat_id для отправки сообщений';
COMMENT ON COLUMN customer_uuid_mapping.sync_id IS '1С ID клиента (КА-00001234)';

-- Проверка
DO $$
BEGIN
    RAISE NOTICE 'customer_uuid_mapping: % записей', (SELECT COUNT(*) FROM customer_uuid_mapping);
END $$;
