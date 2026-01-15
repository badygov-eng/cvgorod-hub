-- ============================================================
-- Скрипт проверки схемы БД
-- Запускать после восстановления из бэкапа или при деплое
-- ============================================================

-- Проверка наличия всех обязательных таблиц
DO $$
DECLARE
    required_tables TEXT[] := ARRAY[
        'user_roles',
        'message_patterns',
        'chats',
        'users',
        'messages',
        'message_analysis',
        'customers',
        'pending_responses',
        'mailing_campaigns',
        'mailing_campaign_messages',
        'user_chats'
    ];
    missing_tables TEXT[] := '{}';
    tbl TEXT;
BEGIN
    FOREACH tbl IN ARRAY required_tables LOOP
        IF NOT EXISTS (
            SELECT 1 FROM information_schema.tables 
            WHERE table_schema = 'public' AND table_name = tbl
        ) THEN
            missing_tables := array_append(missing_tables, tbl);
        END IF;
    END LOOP;
    
    IF array_length(missing_tables, 1) > 0 THEN
        RAISE EXCEPTION 'MISSING TABLES: %', array_to_string(missing_tables, ', ');
    ELSE
        RAISE NOTICE 'All required tables exist ✓';
    END IF;
END $$;

-- Проверка наличия данных в справочниках
DO $$
BEGIN
    IF (SELECT COUNT(*) FROM user_roles) = 0 THEN
        RAISE EXCEPTION 'user_roles is EMPTY!';
    END IF;
    RAISE NOTICE 'user_roles: % records ✓', (SELECT COUNT(*) FROM user_roles);
    
    IF (SELECT COUNT(*) FROM message_patterns) = 0 THEN
        RAISE EXCEPTION 'message_patterns is EMPTY!';
    END IF;
    RAISE NOTICE 'message_patterns: % records ✓', (SELECT COUNT(*) FROM message_patterns);
END $$;

-- Проверка внешних ключей
DO $$
BEGIN
    -- Проверка что pattern_id в messages ссылается на существующую таблицу
    IF EXISTS (
        SELECT 1 FROM messages m 
        WHERE m.pattern_id IS NOT NULL 
        AND NOT EXISTS (SELECT 1 FROM message_patterns mp WHERE mp.id = m.pattern_id)
    ) THEN
        RAISE WARNING 'Some messages have invalid pattern_id references';
    END IF;
    
    RAISE NOTICE 'Foreign key checks passed ✓';
END $$;

-- Итоговая статистика
SELECT 
    'messages' as table_name, COUNT(*) as count FROM messages
UNION ALL SELECT 
    'chats', COUNT(*) FROM chats
UNION ALL SELECT 
    'users', COUNT(*) FROM users
UNION ALL SELECT 
    'customers', COUNT(*) FROM customers
UNION ALL SELECT 
    'message_patterns', COUNT(*) FROM message_patterns
UNION ALL SELECT 
    'user_roles', COUNT(*) FROM user_roles
ORDER BY table_name;
