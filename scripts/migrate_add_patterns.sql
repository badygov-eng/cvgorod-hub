-- ============================================================
-- Миграция: Создание таблицы message_patterns
-- Дата: 2026-01-15
-- Причина: Таблица отсутствовала после восстановления из бэкапа
-- ============================================================

-- Таблица паттернов для классификации сообщений
CREATE TABLE IF NOT EXISTS message_patterns (
    id SERIAL PRIMARY KEY,
    pattern_name VARCHAR(100) NOT NULL,
    pattern_type VARCHAR(50) NOT NULL,  -- broadcast, question, order, complaint, confirmation
    keyword_patterns TEXT[] DEFAULT '{}',
    regex_pattern TEXT,
    sender_role_id INTEGER REFERENCES user_roles(id),
    min_text_length INTEGER DEFAULT 0,
    auto_classify BOOLEAN DEFAULT TRUE,
    priority INTEGER DEFAULT 100,  -- меньше = выше приоритет
    description TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_message_patterns_type ON message_patterns(pattern_type);

-- Базовые паттерны
INSERT INTO message_patterns (pattern_name, pattern_type, keyword_patterns, priority, description) VALUES
    ('broadcast_reminder', 'broadcast', ARRAY['напоминаю', 'свободные к продаже', 'акция', 'скидка'], 10, 'Рассылки бота'),
    ('question_price', 'question', ARRAY['сколько', 'цена', 'стоит', 'почём'], 20, 'Вопросы о цене'),
    ('question_stock', 'question', ARRAY['есть', 'наличии', 'остались', 'когда будет'], 20, 'Вопросы о наличии'),
    ('order_intent', 'order', ARRAY['беру', 'заказываю', 'оформляю', 'хочу заказать'], 15, 'Намерение заказать'),
    ('complaint', 'complaint', ARRAY['брак', 'плохо', 'испорчен', 'жалоба', 'претензия', 'ужасно'], 5, 'Жалобы'),
    ('confirmation', 'confirmation', ARRAY['да', 'подтверждаю', 'согласен', 'ок', 'хорошо'], 30, 'Подтверждения')
ON CONFLICT DO NOTHING;

-- Проверка
DO $$
BEGIN
    RAISE NOTICE 'message_patterns: % записей', (SELECT COUNT(*) FROM message_patterns);
END $$;
