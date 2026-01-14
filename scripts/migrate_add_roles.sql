-- Миграция: Добавление поддержки ролевой модели в cvgorod-hub
-- База данных: cvgorod_hub
-- Автор: System
-- Дата: 2026-01-14
-- Описание: Добавление таблиц для рассылок, новых колонок в messages,
--            индексов для оптимизации запросов и эвристики определения ролей

-- ============================================================
-- ШАГ 1: Добавление новых колонок в таблицу messages
-- ============================================================

-- Добавление колонки role (роль отправителя)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'messages' AND column_name = 'role'
    ) THEN
        ALTER TABLE messages ADD COLUMN role VARCHAR(50);
        COMMENT ON COLUMN messages.role IS 'Роль отправителя: CLIENT, MANAGER, DIRECTOR, BOT';
    END IF;
END $$;

-- Добавление колонки is_automatic (автоматическое сообщение)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'messages' AND column_name = 'is_automatic'
    ) THEN
        ALTER TABLE messages ADD COLUMN is_automatic BOOLEAN DEFAULT FALSE;
        COMMENT ON COLUMN messages.is_automatic IS 'True если сообщение отправлено автоматически (ботом)';
    END IF;
END $$;

-- Добавление колонки intent (классификация интента)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'messages' AND column_name = 'intent'
    ) THEN
        ALTER TABLE messages ADD COLUMN intent VARCHAR(100);
        COMMENT ON COLUMN messages.intent IS 'Классификация интента сообщения';
    END IF;
END $$;

-- Добавление колонки intent_confidence (уверенность классификации)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'messages' AND column_name = 'intent_confidence'
    ) THEN
        ALTER TABLE messages ADD COLUMN intent_confidence DECIMAL(5, 4);
        COMMENT ON COLUMN messages.intent_confidence IS 'Уверенность классификации интента (0-1)';
    END IF;
END $$;

-- Добавление колонки is_reply (является ли ответом)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'messages' AND column_name = 'is_reply'
    ) THEN
        ALTER TABLE messages ADD COLUMN is_reply BOOLEAN DEFAULT FALSE;
        COMMENT ON COLUMN messages.is_reply IS 'True если сообщение является ответом на другое';
    END IF;
END $$;

-- Добавление колонки reply_to_message_id (ссылка на сообщение-родитель)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'messages' AND column_name = 'reply_to_message_id'
    ) THEN
        ALTER TABLE messages ADD COLUMN reply_to_message_id BIGINT;
        COMMENT ON COLUMN messages.reply_to_message_id IS 'ID сообщения на которое дан ответ';
        COMMENT ON CONSTRAINT IF EXISTS fk_reply_to_message_id
            ON messages IS 'Внешний ключ на сообщение';
    END IF;
END $$;

-- ============================================================
-- ШАГ 2: Добавление внешнего ключа для reply_to_message_id
-- ============================================================

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'messages' AND column_name = 'reply_to_message_id'
    ) AND NOT EXISTS (
        SELECT 1 FROM information_schema.table_constraints tc
        JOIN information_schema.constraint_column_usage ccu
            ON tc.constraint_name = ccu.constraint_name
        WHERE tc.table_name = 'messages'
            AND tc.constraint_type = 'FOREIGN KEY'
            AND ccu.column_name = 'reply_to_message_id'
    ) THEN
        ALTER TABLE messages
            ADD CONSTRAINT fk_messages_reply_to_message_id
            FOREIGN KEY (reply_to_message_id)
            REFERENCES messages(id) ON DELETE SET NULL;
    END IF;
END $$;

-- ============================================================
-- ШАГ 3: Создание таблицы рассылок (mailing_campaigns)
-- ============================================================

CREATE TABLE IF NOT EXISTS mailing_campaigns (
    id BIGSERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    description TEXT DEFAULT NULL,
    message_template TEXT NOT NULL,
    sent_by_user_id BIGINT REFERENCES users(id) ON DELETE SET NULL,
    sent_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    status VARCHAR(50) DEFAULT 'DRAFT',
    scheduled_at TIMESTAMP WITH TIME ZONE DEFAULT NULL,
    completed_at TIMESTAMP WITH TIME ZONE DEFAULT NULL,
    total_recipients INTEGER DEFAULT 0,
    successful_deliveries INTEGER DEFAULT 0,
    failed_deliveries INTEGER DEFAULT 0,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

COMMENT ON TABLE mailing_campaigns IS 'Таблица кампаний массовых рассылок';
COMMENT ON COLUMN mailing_campaigns.status IS 'Статус: DRAFT, SCHEDULED, SENDING, COMPLETED, CANCELLED';
COMMENT ON COLUMN mailing_campaigns.metadata IS 'Дополнительные метаданные (JSON)';

-- Индексы для mailing_campaigns
CREATE INDEX IF NOT EXISTS idx_mailing_campaigns_status
    ON mailing_campaigns(status);
CREATE INDEX IF NOT EXISTS idx_mailing_campaigns_scheduled
    ON mailing_campaigns(scheduled_at) WHERE scheduled_at IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_mailing_campaigns_sent_by
    ON mailing_campaigns(sent_by_user_id);

-- ============================================================
-- ШАГ 4: Создание таблицы сообщений рассылок (mailing_campaign_messages)
-- ============================================================

CREATE TABLE IF NOT EXISTS mailing_campaign_messages (
    id BIGSERIAL PRIMARY KEY,
    campaign_id BIGINT NOT NULL REFERENCES mailing_campaigns(id) ON DELETE CASCADE,
    message_id BIGINT REFERENCES messages(id) ON DELETE SET NULL,
    chat_id BIGINT NOT NULL,
    recipient_user_id BIGINT REFERENCES users(id) ON DELETE SET NULL,
    status VARCHAR(50) DEFAULT 'PENDING',
    sent_at TIMESTAMP WITH TIME ZONE DEFAULT NULL,
    delivered_at TIMESTAMP WITH TIME ZONE DEFAULT NULL,
    read_at TIMESTAMP WITH TIME ZONE DEFAULT NULL,
    error_message TEXT DEFAULT NULL,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

COMMENT ON TABLE mailing_campaign_messages IS 'Таблица отслеживания отправленных сообщений рассылок';
COMMENT ON COLUMN mailing_campaign_messages.status IS 'Статус доставки: PENDING, SENT, DELIVERED, READ, FAILED';

-- Индексы для mailing_campaign_messages
CREATE INDEX IF NOT EXISTS idx_mailing_campaign_messages_campaign
    ON mailing_campaign_messages(campaign_id);
CREATE INDEX IF NOT EXISTS idx_mailing_campaign_messages_chat
    ON mailing_campaign_messages(chat_id);
CREATE INDEX IF NOT EXISTS idx_mailing_campaign_messages_status
    ON mailing_campaign_messages(status);
CREATE INDEX IF NOT EXISTS idx_mailing_campaign_messages_sent
    ON mailing_campaign_messages(sent_at) WHERE sent_at IS NOT NULL;

-- ============================================================
-- ШАГ 5: Создание таблицы связи пользователей с чатами (user_chats)
-- ============================================================

CREATE TABLE IF NOT EXISTS user_chats (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    chat_id BIGINT NOT NULL,
    chat_name VARCHAR(500) DEFAULT NULL,
    role VARCHAR(50) NOT NULL DEFAULT 'CLIENT',
    is_primary BOOLEAN DEFAULT FALSE,
    joined_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_activity TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    message_count INTEGER DEFAULT 0,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(user_id, chat_id, role)
);

COMMENT ON TABLE user_chats IS 'Таблица связи пользователей с чатами с указанием роли';
COMMENT ON COLUMN user_chats.role IS 'Роль пользователя в чате: CLIENT, MANAGER, BOT';
COMMENT ON COLUMN user_chats.is_primary IS 'True если это основной чат пользователя';

-- Индексы для user_chats
CREATE INDEX IF NOT EXISTS idx_user_chats_user_id
    ON user_chats(user_id);
CREATE INDEX IF NOT EXISTS idx_user_chats_chat_id
    ON user_chats(chat_id);
CREATE INDEX IF NOT EXISTS idx_user_chats_role
    ON user_chats(role);
CREATE INDEX IF NOT EXISTS idx_user_chats_last_activity
    ON user_chats(last_activity DESC);

-- ============================================================
-- ШАГ 6: Добавление недостающих ролей в user_roles
-- ============================================================

INSERT INTO user_roles (role_name, display_name, description, is_staff, is_bot, exclude_from_analytics) VALUES
    ('director', 'Директор', 'Руководитель, имеющий доступ к аналитике и отчётам', TRUE, FALSE, TRUE)
ON CONFLICT (role_name) DO UPDATE SET
    display_name = EXCLUDED.display_name,
    description = EXCLUDED.description;

-- ============================================================
-- ШАГ 7: Добавление колонки role в таблицу users (если нет)
-- ============================================================

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'users' AND column_name = 'role'
    ) THEN
        ALTER TABLE users ADD COLUMN role VARCHAR(50) DEFAULT 'CLIENT';
        COMMENT ON COLUMN users.role IS 'Текущая роль пользователя в системе';
    END IF;
END $$;

-- ============================================================
-- ШАГ 8: Добавление колонки is_active в таблицу users (если нет)
-- ============================================================

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'users' AND column_name = 'is_active'
    ) THEN
        ALTER TABLE users ADD COLUMN is_active BOOLEAN DEFAULT TRUE;
        COMMENT ON COLUMN users.is_active IS 'Активен ли пользователь в системе';
    END IF;
END $$;

-- ============================================================
-- ШАГ 9: Создание индексов для таблицы messages
-- ============================================================

-- Индекс для фильтрации по роли
CREATE INDEX IF NOT EXISTS idx_messages_role
    ON messages(role) WHERE role IS NOT NULL;

-- Индекс для фильтрации по интенту
CREATE INDEX IF NOT EXISTS idx_messages_intent
    ON messages(intent) WHERE intent IS NOT NULL;

-- Индекс для фильтрации автоматических сообщений
CREATE INDEX IF NOT EXISTS idx_messages_automatic
    ON messages(is_automatic) WHERE is_automatic = TRUE;

-- Индекс для фильтрации ответов
CREATE INDEX IF NOT EXISTS idx_messages_is_reply
    ON messages(is_reply) WHERE is_reply = TRUE;

-- Композитный индекс для типичных запросов аналитики
CREATE INDEX IF NOT EXISTS idx_messages_chat_role_time
    ON messages(chat_id, role, timestamp DESC)
    WHERE role IS NOT NULL;

-- Индекс для поиска сообщений клиентов за период
CREATE INDEX IF NOT EXISTS idx_messages_client_time
    ON messages(timestamp DESC)
    WHERE role = 'CLIENT';

-- ============================================================
-- ШАГ 10: Заполнение данных на основе существующих данных
-- ============================================================

-- Обновление поля role в messages на основе существующих данных
-- CLIENTS: пользователи с role_id = 6 (клиенты)
UPDATE messages m
SET role = 'CLIENT'
FROM users u
WHERE m.user_id = u.id
    AND u.role_id = 6
    AND m.role IS NULL;

-- MANAGERS: пользователи с is_manager = TRUE
UPDATE messages m
SET role = 'MANAGER'
FROM users u
WHERE m.user_id = u.id
    AND (u.is_manager = TRUE OR u.role_id IN (
        SELECT id FROM user_roles WHERE role_name = 'manager'
    ))
    AND m.role IS NULL;

-- DIRECTORS: пользователи с role_id директора
UPDATE messages m
SET role = 'DIRECTOR'
FROM users u
WHERE m.user_id = u.id
    AND u.role_id IN (
        SELECT id FROM user_roles WHERE role_name = 'director'
    )
    AND m.role IS NULL;

-- BOTS: пользователи с role_id ботов
UPDATE messages m
SET role = 'BOT'
FROM users u
WHERE m.user_id = u.id
    AND u.role_id IN (
        SELECT id FROM user_roles WHERE is_bot = TRUE
    )
    AND m.role IS NULL;

-- Для сообщений без определённой роли - определяем эвристически
-- MANAGER: пользователь пишет в 2 и более разных чатов
UPDATE messages m
SET role = 'MANAGER'
FROM (
    SELECT DISTINCT user_id
    FROM messages
    GROUP BY user_id
    HAVING COUNT(DISTINCT chat_id) >= 2
) AS potential_managers
WHERE m.user_id = potential_managers.user_id
    AND m.role IS NULL;

-- Оставшиеся неопределённые - CLIENTS
UPDATE messages m
SET role = 'CLIENT'
WHERE m.role IS NULL;

-- ============================================================
-- ШАГ 11: Обновление поля role в таблице users
-- ============================================================

-- MANAGERS
UPDATE users u
SET role = 'MANAGER'
WHERE (u.is_manager = TRUE OR u.role_id IN (
    SELECT id FROM user_roles WHERE role_name = 'manager'
))
    AND u.role IS NULL;

-- DIRECTORS
UPDATE users u
SET role = 'DIRECTOR'
WHERE u.role_id IN (
    SELECT id FROM user_roles WHERE role_name = 'director'
)
    AND u.role IS NULL;

-- BOTS
UPDATE users u
SET role = 'BOT'
WHERE u.role_id IN (
    SELECT id FROM user_roles WHERE is_bot = TRUE
)
    AND u.role IS NULL;

-- Остальные - CLIENTS
UPDATE users u
SET role = 'CLIENT'
WHERE u.role IS NULL;

-- ============================================================
-- ШАГ 12: Создание представлений для аналитики
-- ============================================================

-- Представление: статистика сообщений по ролям
CREATE OR REPLACE VIEW messages_by_role AS
SELECT
    DATE(m.timestamp) as date,
    m.role,
    COUNT(*) as message_count,
    COUNT(DISTINCT m.chat_id) as active_chats,
    COUNT(DISTINCT m.user_id) as active_users
FROM messages m
WHERE m.role IS NOT NULL
GROUP BY DATE(m.timestamp), m.role
ORDER BY date DESC, role;

COMMENT ON VIEW messages_by_role IS 'Статистика сообщений по ролям за каждый день';

-- Представление: производительность менеджеров
CREATE OR REPLACE VIEW manager_performance AS
SELECT
    u.id as user_id,
    u.username,
    u.first_name,
    u.last_name,
    COUNT(DISTINCT m.chat_id) as chats_count,
    COUNT(m.id) as total_messages,
    COUNT(CASE WHEN m.role = 'MANAGER' THEN 1 END) as manager_messages,
    COUNT(CASE WHEN m.role = 'CLIENT' THEN 1 END) as client_messages,
    MIN(m.timestamp) as first_message,
    MAX(m.timestamp) as last_message
FROM users u
LEFT JOIN messages m ON u.id = m.user_id
WHERE u.role = 'MANAGER' OR u.is_manager = TRUE
GROUP BY u.id, u.username, u.first_name, u.last_name
ORDER BY total_messages DESC;

COMMENT ON VIEW manager_performance IS 'Производительность менеджеров';

-- Представление: неотвеченные вопросы клиентов
CREATE OR REPLACE VIEW unanswered_client_questions AS
WITH client_messages AS (
    SELECT
        m.id as message_id,
        m.chat_id,
        m.user_id,
        m.text,
        m.timestamp,
        c.name as chat_name,
        u.username,
        u.first_name
    FROM messages m
    LEFT JOIN chats c ON m.chat_id = c.id
    LEFT JOIN users u ON m.user_id = u.id
    WHERE m.role = 'CLIENT'
        AND (m.text LIKE '%?%' OR LOWER(m.text) LIKE '%есть ли%'
            OR LOWER(m.text) LIKE '%сколько%' OR LOWER(m.text) LIKE '%когда%'
            OR LOWER(m.text) LIKE '%можно ли%' OR LOWER(m.text) LIKE '%подскажите%'
            OR LOWER(m.text) LIKE '%узнать%')
),
replied_messages AS (
    SELECT DISTINCT
        m.chat_id,
        m.user_id,
        first_message.timestamp as question_time
    FROM messages m
    JOIN client_messages first_message
        ON m.chat_id = first_message.chat_id
        AND m.timestamp > first_message.timestamp
        AND m.timestamp < first_message.timestamp + INTERVAL '24 hours'
    WHERE m.role = 'MANAGER'
)
SELECT
    cm.message_id,
    cm.chat_id,
    cm.chat_name,
    cm.user_id,
    cm.username,
    cm.first_name,
    cm.text as question_text,
    cm.timestamp as question_time
FROM client_messages cm
LEFT JOIN replied_messages rm
    ON cm.chat_id = rm.chat_id
    AND cm.user_id = rm.user_id
    AND rm.question_time = cm.timestamp
WHERE rm.chat_id IS NULL
ORDER BY cm.timestamp DESC;

COMMENT ON VIEW unanswered_client_questions IS 'Вопросы клиентов без ответов от менеджеров';

-- ============================================================
-- ШАГ 13: Функции для работы с ролевой моделью
-- ============================================================

-- Функция определения роли пользователя по его активности
CREATE OR REPLACE FUNCTION determine_user_role(p_user_id BIGINT)
RETURNS VARCHAR(50) AS $$
DECLARE
    v_chat_count INTEGER;
    v_role VARCHAR(50);
BEGIN
    -- Подсчёт уникальных чатов пользователя
    SELECT COUNT(DISTINCT chat_id) INTO v_chat_count
    FROM messages
    WHERE user_id = p_user_id;
    
    -- Эвристика определения роли
    IF v_chat_count >= 2 THEN
        v_role := 'MANAGER';
    ELSE
        v_role := 'CLIENT';
    END IF;
    
    RETURN v_role;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION determine_user_role IS 'Определяет роль пользователя по количеству чатов';

-- Функция определения рассылки (одинаковые сообщения в нескольких чатах)
CREATE OR REPLACE FUNCTION detect_mailing(p_message_id BIGINT)
RETURNS BOOLEAN AS $$
DECLARE
    v_text TEXT;
    v_similar_count INTEGER;
BEGIN
    -- Получаем текст сообщения
    SELECT text INTO v_text
    FROM messages
    WHERE id = p_message_id;
    
    IF v_text IS NULL THEN
        RETURN FALSE;
    END IF;
    
    -- Ищем похожие сообщения от того же пользователя
    SELECT COUNT(*) INTO v_similar_count
    FROM messages
    WHERE user_id = (SELECT user_id FROM messages WHERE id = p_message_id)
        AND id != p_message_id
        AND text = v_text
        AND timestamp > NOW() - INTERVAL '24 hours';
    
    RETURN v_similar_count >= 2;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION detect_mailing IS 'Определяет является ли сообщение частью рассылки';

-- ============================================================
-- ШАГ 14: Обновление представления daily_message_stats
-- ============================================================

CREATE OR REPLACE VIEW daily_message_stats AS
SELECT
    DATE(m.timestamp) as date,
    COUNT(*) as message_count,
    COUNT(DISTINCT m.chat_id) as active_chats,
    COUNT(DISTINCT m.user_id) as active_users,
    COUNT(CASE WHEN m.role = 'CLIENT' THEN 1 END) as client_messages,
    COUNT(CASE WHEN m.role = 'MANAGER' THEN 1 END) as manager_messages,
    COUNT(CASE WHEN m.role = 'BOT' THEN 1 END) as bot_messages,
    COUNT(DISTINCT CASE WHEN m.role = 'MANAGER' THEN m.chat_id END) as manager_chats
FROM messages m
GROUP BY DATE(m.timestamp)
ORDER BY date DESC;

-- ============================================================
-- ШАГ 15: Триггеры для автоматического обновления
-- ============================================================

-- Триггер для обновления updated_at в mailing_campaigns
CREATE OR REPLACE FUNCTION update_mailing_campaigns_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_mailing_campaigns_updated ON mailing_campaigns;
CREATE TRIGGER trg_mailing_campaigns_updated
    BEFORE UPDATE ON mailing_campaigns
    FOR EACH ROW
    EXECUTE FUNCTION update_mailing_campaigns_timestamp();

-- Триггер для обновления updated_at в user_chats
CREATE OR REPLACE FUNCTION update_user_chats_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_user_chats_updated ON user_chats;
CREATE TRIGGER trg_user_chats_updated
    BEFORE UPDATE ON user_chats
    FOR EACH ROW
    EXECUTE FUNCTION update_user_chats_timestamp();

-- ============================================================
-- ПРОВЕРКА МИГРАЦИИ
-- ============================================================

DO $$
DECLARE
    v_errors INTEGER := 0;
    v_check TEXT;
BEGIN
    -- Проверка колонок messages
    PERFORM 1 FROM information_schema.columns
        WHERE table_name = 'messages' AND column_name = 'role';
    IF NOT FOUND THEN
        RAISE WARNING 'Колонка role не найдена в messages';
        v_errors := v_errors + 1;
    END IF;

    -- Проверка таблицы mailing_campaigns
    PERFORM 1 FROM information_schema.tables
        WHERE table_name = 'mailing_campaigns';
    IF NOT FOUND THEN
        RAISE WARNING 'Таблица mailing_campaigns не найдена';
        v_errors := v_errors + 1;
    END IF;

    -- Проверка таблицы user_chats
    PERFORM 1 FROM information_schema.tables
        WHERE table_name = 'user_chats';
    IF NOT FOUND THEN
        RAISE WARNING 'Таблица user_chats не найдена';
        v_errors := v_errors + 1;
    END IF;

    -- Проверка представления messages_by_role
    PERFORM 1 FROM information_schema.views
        WHERE table_name = 'messages_by_role';
    IF NOT FOUND THEN
        RAISE WARNING 'Представление messages_by_role не найдено';
        v_errors := v_errors + 1;
    END IF;

    -- Проверка данных в messages.role
    SELECT INTO v_check COUNT(*) FROM messages WHERE role IS NULL;
    RAISE NOTICE 'Сообщений с NULL ролью: %', v_check;

    IF v_errors > 0 THEN
        RAISE WARNING 'Миграция завершена с % предупреждениями', v_errors;
    ELSE
        RAISE NOTICE 'Миграция успешно завершена';
    END IF;
END $$;

-- Конец миграции
