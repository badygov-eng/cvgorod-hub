-- =============================================================================
-- Миграция: добавление поля sentiment для анализа настроений клиентов
-- =============================================================================

-- Добавляем поле sentiment в таблицу messages
ALTER TABLE messages ADD COLUMN IF NOT EXISTS sentiment VARCHAR(20) DEFAULT NULL;

-- Индекс для быстрого поиска по настроению
CREATE INDEX IF NOT EXISTS idx_messages_sentiment ON messages(sentiment);

-- Комментарий для документации
COMMENT ON COLUMN messages.sentiment IS 'Настроение клиента: positive, neutral, negative, unknown';

-- Обновляем существующие записи (если нужно)
-- UPDATE messages SET sentiment = 'unknown' WHERE sentiment IS NULL;

DO $$
BEGIN
    -- Проверяем, существует ли представление
    IF EXISTS (SELECT 1 FROM information_schema.views WHERE table_name = 'daily_message_stats') THEN
        -- Обновляем представление для включения статистики по sentiment
        DROP VIEW IF EXISTS daily_message_stats;
    END IF;
END $$;

-- Обновленное представление для аналитики с учётом sentiment
CREATE OR REPLACE VIEW daily_message_stats AS
SELECT
    DATE(timestamp) as date,
    COUNT(*) as message_count,
    COUNT(DISTINCT chat_id) as active_chats,
    COUNT(DISTINCT user_id) as active_users,
    COUNT(CASE WHEN sentiment = 'positive' THEN 1 END) as positive_count,
    COUNT(CASE WHEN sentiment = 'negative' THEN 1 END) as negative_count,
    COUNT(CASE WHEN sentiment = 'neutral' THEN 1 END) as neutral_count,
    COUNT(CASE WHEN sentiment IS NULL THEN 1 END) as unknown_count
FROM messages
GROUP BY DATE(timestamp)
ORDER BY date DESC;

-- Представление для анализа настроений по пользователям
CREATE OR REPLACE VIEW user_sentiment_stats AS
SELECT
    u.id,
    u.username,
    u.first_name,
    COUNT(m.id) as total_messages,
    COUNT(CASE WHEN m.sentiment = 'positive' THEN 1 END) as positive_count,
    COUNT(CASE WHEN m.sentiment = 'negative' THEN 1 END) as negative_count,
    COUNT(CASE WHEN m.sentiment = 'neutral' THEN 1 END) as neutral_count,
    CASE
        WHEN COUNT(m.id) > 0 THEN
            ROUND(
                (COUNT(CASE WHEN m.sentiment = 'positive' THEN 1 END)::NUMERIC /
                COUNT(m.id)::NUMERIC) * 100, 1
            )
        ELSE 0
    END as positive_percent,
    CASE
        WHEN COUNT(m.id) > 0 THEN
            ROUND(
                (COUNT(CASE WHEN m.sentiment = 'negative' THEN 1 END)::NUMERIC /
                COUNT(m.id)::NUMERIC) * 100, 1
            )
        ELSE 0
    END as negative_percent
FROM users u
LEFT JOIN messages m ON u.id = m.user_id
GROUP BY u.id, u.username, u.first_name
ORDER BY negative_percent DESC, total_messages DESC
LIMIT 100;

SELECT 'Миграция добавления sentiment выполнена успешно!' as status;
