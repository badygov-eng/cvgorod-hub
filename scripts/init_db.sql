-- Schema for cvgorod-hub
-- Database: cvgorod_hub

-- ============================================================
-- СПРАВОЧНИКИ РОЛЕЙ И ПАТТЕРНОВ
-- ============================================================

-- Таблица ролей пользователей
CREATE TABLE IF NOT EXISTS user_roles (
    id SERIAL PRIMARY KEY,
    role_name VARCHAR(50) UNIQUE NOT NULL,
    display_name VARCHAR(100),
    description TEXT,
    is_staff BOOLEAN DEFAULT FALSE,
    is_bot BOOLEAN DEFAULT FALSE,
    exclude_from_analytics BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Заполнение ролей
INSERT INTO user_roles (role_name, display_name, is_staff, is_bot, exclude_from_analytics) VALUES
    ('admin', 'Администратор', TRUE, FALSE, TRUE),
    ('director', 'Директор', TRUE, FALSE, TRUE),
    ('manager', 'Менеджер', TRUE, FALSE, TRUE),
    ('broadcast_bot', 'Бот рассылки', FALSE, TRUE, TRUE),
    ('assistant_bot', 'AI Ассистент', FALSE, TRUE, TRUE),
    ('client', 'Клиент', FALSE, FALSE, FALSE)
ON CONFLICT (role_name) DO NOTHING;

-- Таблица паттернов сообщений
CREATE TABLE IF NOT EXISTS message_patterns (
    id SERIAL PRIMARY KEY,
    pattern_name VARCHAR(100) NOT NULL,
    pattern_type VARCHAR(50) NOT NULL,
    keyword_patterns TEXT[] DEFAULT '{}',
    regex_pattern TEXT,
    sender_role_id INTEGER REFERENCES user_roles(id),
    min_text_length INTEGER DEFAULT 0,
    auto_classify BOOLEAN DEFAULT TRUE,
    priority INTEGER DEFAULT 100,
    description TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_message_patterns_type ON message_patterns(pattern_type);

-- Заполнение паттернов
INSERT INTO message_patterns (pattern_name, pattern_type, keyword_patterns, priority, description) VALUES
    ('broadcast_reminder', 'broadcast', ARRAY['напоминаю', 'свободные к продаже', 'акция', 'скидка'], 10, 'Рассылки бота'),
    ('question_price', 'question', ARRAY['сколько', 'цена', 'стоит', 'почём'], 20, 'Вопросы о цене'),
    ('question_stock', 'question', ARRAY['есть', 'наличии', 'остались', 'когда будет'], 20, 'Вопросы о наличии'),
    ('order_intent', 'order', ARRAY['беру', 'заказываю', 'оформляю', 'хочу заказать'], 15, 'Намерение заказать'),
    ('complaint', 'complaint', ARRAY['брак', 'плохо', 'испорчен', 'жалоба', 'претензия', 'ужасно'], 5, 'Жалобы'),
    ('confirmation', 'confirmation', ARRAY['да', 'подтверждаю', 'согласен', 'ок', 'хорошо'], 30, 'Подтверждения')
ON CONFLICT DO NOTHING;

-- ============================================================
-- ОСНОВНЫЕ ТАБЛИЦЫ
-- ============================================================

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
    role_id INTEGER REFERENCES user_roles(id) DEFAULT 6,  -- 6 = client
    first_seen TIMESTAMP DEFAULT NOW(),
    last_seen TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
CREATE INDEX IF NOT EXISTS idx_users_manager ON users(is_manager);
CREATE INDEX IF NOT EXISTS idx_users_role ON users(role_id);

-- Таблица сообщений
CREATE TABLE IF NOT EXISTS messages (
    id SERIAL PRIMARY KEY,
    telegram_message_id BIGINT NOT NULL,
    chat_id BIGINT NOT NULL REFERENCES chats(id) ON DELETE CASCADE,
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    text TEXT DEFAULT NULL,
    message_type VARCHAR(50) DEFAULT 'text',
    reply_to_message_id BIGINT DEFAULT NULL,
    pattern_id INTEGER REFERENCES message_patterns(id),  -- Классификация сообщения
    timestamp TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_messages_chat ON messages(chat_id);
CREATE INDEX IF NOT EXISTS idx_messages_timestamp ON messages(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_messages_user ON messages(user_id);
CREATE INDEX IF NOT EXISTS idx_messages_chat_time ON messages(chat_id, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_messages_pattern ON messages(pattern_id);

-- Full-text search для русского языка
CREATE INDEX IF NOT EXISTS idx_messages_text_gin ON messages USING gin(to_tsvector('russian', COALESCE(text, '')));

-- ============================================================
-- ФУНКЦИЯ КЛАССИФИКАЦИИ СООБЩЕНИЙ
-- ============================================================

-- Функция для автоматической классификации сообщений по паттернам
CREATE OR REPLACE FUNCTION classify_message(p_text TEXT, p_user_id BIGINT)
RETURNS INTEGER AS $$
DECLARE
    v_pattern_id INTEGER;
    v_pattern RECORD;
    v_text_lower TEXT;
BEGIN
    v_text_lower := LOWER(COALESCE(p_text, ''));
    
    -- Проверяем паттерны по приоритету (меньше = выше приоритет)
    FOR v_pattern IN 
        SELECT id, keyword_patterns, regex_pattern, min_text_length
        FROM message_patterns
        WHERE auto_classify = TRUE
        ORDER BY priority ASC
    LOOP
        -- Проверка минимальной длины
        IF LENGTH(v_text_lower) < v_pattern.min_text_length THEN
            CONTINUE;
        END IF;
        
        -- Проверка ключевых слов
        IF v_pattern.keyword_patterns IS NOT NULL AND array_length(v_pattern.keyword_patterns, 1) > 0 THEN
            IF EXISTS (
                SELECT 1 FROM unnest(v_pattern.keyword_patterns) AS kw
                WHERE v_text_lower LIKE '%' || LOWER(kw) || '%'
            ) THEN
                RETURN v_pattern.id;
            END IF;
        END IF;
        
        -- Проверка regex (если задан)
        IF v_pattern.regex_pattern IS NOT NULL THEN
            IF v_text_lower ~ v_pattern.regex_pattern THEN
                RETURN v_pattern.id;
            END IF;
        END IF;
    END LOOP;
    
    RETURN NULL;  -- Не классифицировано
END;
$$ LANGUAGE plpgsql;

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
