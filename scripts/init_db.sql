-- Schema for cvgorod-hub
-- Database: cvgorod_hub

-- Таблица чатов (групп)
CREATE TABLE IF NOT EXISTS chats (
    id BIGINT PRIMARY KEY,
    name VARCHAR(500) DEFAULT NULL,
    chat_type VARCHAR(50) DEFAULT 'group',
    folder VARCHAR(100) DEFAULT NULL,
    members_count INT DEFAULT 0,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_chats_folder ON chats(folder);
CREATE INDEX IF NOT EXISTS idx_chats_active ON chats(is_active);

-- Таблица пользователей
CREATE TABLE IF NOT EXISTS users (
    id BIGINT PRIMARY KEY,
    username VARCHAR(255) DEFAULT NULL,
    first_name VARCHAR(255) DEFAULT NULL,
    last_name VARCHAR(255) DEFAULT NULL,
    is_manager BOOLEAN DEFAULT FALSE,
    first_seen TIMESTAMP DEFAULT NOW(),
    last_seen TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
CREATE INDEX IF NOT EXISTS idx_users_manager ON users(is_manager);

-- Таблица сообщений
CREATE TABLE IF NOT EXISTS messages (
    id SERIAL PRIMARY KEY,
    telegram_message_id BIGINT NOT NULL,
    chat_id BIGINT NOT NULL REFERENCES chats(id) ON DELETE CASCADE,
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    text TEXT DEFAULT NULL,
    message_type VARCHAR(50) DEFAULT 'text',
    reply_to_message_id BIGINT DEFAULT NULL,
    timestamp TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_messages_chat ON messages(chat_id);
CREATE INDEX IF NOT EXISTS idx_messages_timestamp ON messages(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_messages_user ON messages(user_id);
CREATE INDEX IF NOT EXISTS idx_messages_chat_time ON messages(chat_id, timestamp DESC);

-- Full-text search для русского языка
CREATE INDEX IF NOT EXISTS idx_messages_text_gin ON messages USING gin(to_tsvector('russian', COALESCE(text, '')));

-- Таблица анализа сообщений (LLM классификация)
CREATE TABLE IF NOT EXISTS message_analysis (
    id SERIAL PRIMARY KEY,
    message_id INTEGER REFERENCES messages(id) ON DELETE CASCADE,
    intent VARCHAR(50) DEFAULT 'unknown',
    sentiment VARCHAR(20) DEFAULT 'unknown',
    entities JSONB DEFAULT '{}',
    confidence REAL DEFAULT 0.0,
    model_used VARCHAR(50) DEFAULT 'deepseek-chat',
    tokens_used INTEGER DEFAULT 0,
    processing_time_ms INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_message_analysis_intent ON message_analysis(intent);
CREATE INDEX IF NOT EXISTS idx_message_analysis_sentiment ON message_analysis(sentiment);
CREATE INDEX IF NOT EXISTS idx_message_analysis_message ON message_analysis(message_id);

-- Таблица песочницы ответов
CREATE TABLE IF NOT EXISTS pending_responses (
    id SERIAL PRIMARY KEY,
    chat_id BIGINT NOT NULL,
    client_name VARCHAR(500),
    response_text TEXT NOT NULL,
    context TEXT,
    requested_by VARCHAR(100) DEFAULT 'agent',
    status VARCHAR(20) DEFAULT 'pending',
    approved_by BIGINT,
    approved_at TIMESTAMP WITH TIME ZONE,
    sent_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_pending_status ON pending_responses(status);
CREATE INDEX IF NOT EXISTS idx_pending_created ON pending_responses(created_at);

-- Представление для аналитики
CREATE OR REPLACE VIEW daily_message_stats AS
SELECT
    DATE(timestamp) as date,
    COUNT(*) as message_count,
    COUNT(DISTINCT chat_id) as active_chats,
    COUNT(DISTINCT user_id) as active_users
FROM messages
GROUP BY DATE(timestamp)
ORDER BY date DESC;

-- Представление для топ пользователей
CREATE OR REPLACE VIEW top_users AS
SELECT
    u.id,
    u.username,
    u.first_name,
    u.is_manager,
    COUNT(m.id) as message_count
FROM users u
LEFT JOIN messages m ON u.id = m.user_id
GROUP BY u.id, u.username, u.first_name, u.is_manager
ORDER BY message_count DESC
LIMIT 100;
