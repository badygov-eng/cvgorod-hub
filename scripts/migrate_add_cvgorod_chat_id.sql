-- ============================================================
-- Миграция: Добавление cvgorod_chat_id в таблицу chats
-- Дата: 2026-01-18
-- Назначение: Связь telegram чатов с ID из CVGorod API
-- ============================================================

-- Добавляем колонку если её нет
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'chats' AND column_name = 'cvgorod_chat_id'
    ) THEN
        ALTER TABLE chats ADD COLUMN cvgorod_chat_id INTEGER;
        CREATE INDEX idx_chats_cvgorod_id ON chats(cvgorod_chat_id);
        RAISE NOTICE 'Добавлена колонка cvgorod_chat_id в таблицу chats';
    ELSE
        RAISE NOTICE 'Колонка cvgorod_chat_id уже существует';
    END IF;
END $$;

-- Проверка
DO $$
BEGIN
    RAISE NOTICE 'chats.cvgorod_chat_id: % непустых из %', 
        (SELECT COUNT(cvgorod_chat_id) FROM chats),
        (SELECT COUNT(*) FROM chats);
END $$;
