-- Migration: Add customers table and link to chats
-- Date: 2026-01-15

-- 1. Таблица клиентов из 1С
CREATE TABLE IF NOT EXISTS customers (
    id SERIAL PRIMARY KEY,
    sync_id VARCHAR(20) UNIQUE NOT NULL,      -- КА-00003484
    name VARCHAR(255) NOT NULL,
    email VARCHAR(255),
    phone VARCHAR(50),
    cvgorod_chat_id INT,                       -- ID из cvgorod API
    created_at TIMESTAMP DEFAULT NOW()
);

-- 2. Добавляем customer_id в chats
ALTER TABLE chats ADD COLUMN IF NOT EXISTS customer_id INT REFERENCES customers(id);

-- 3. Индекс для быстрого поиска
CREATE INDEX IF NOT EXISTS idx_chats_customer ON chats(customer_id);
CREATE INDEX IF NOT EXISTS idx_customers_sync_id ON customers(sync_id);
CREATE INDEX IF NOT EXISTS idx_customers_name ON customers(name);

-- 4. Комментарии
COMMENT ON TABLE customers IS 'Клиенты из 1С (sync_id = КА-XXXXXXXX)';
COMMENT ON COLUMN customers.sync_id IS 'ID клиента в 1С';
COMMENT ON COLUMN customers.cvgorod_chat_id IS 'ID чата в cvgorod API';
COMMENT ON COLUMN chats.customer_id IS 'Ссылка на клиента из 1С';
