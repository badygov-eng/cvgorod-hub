-- ============================================================
-- Миграция: Добавление поддержки batch отправки сообщений
-- Дата: 2026-01-19
-- Причина: Массовая отправка сообщений с планированием
-- ============================================================

DO $$
BEGIN
    -- Добавляем batch_id для группировки сообщений
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name = 'pending_responses' AND column_name = 'batch_id') THEN
        ALTER TABLE pending_responses ADD COLUMN batch_id UUID;
        CREATE INDEX idx_pending_batch_id ON pending_responses(batch_id);
        RAISE NOTICE 'Column batch_id added to pending_responses.';
    ELSE
        RAISE NOTICE 'Column batch_id already exists.';
    END IF;

    -- Добавляем scheduled_at для планирования отправки
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name = 'pending_responses' AND column_name = 'scheduled_at') THEN
        ALTER TABLE pending_responses ADD COLUMN scheduled_at TIMESTAMP WITH TIME ZONE;
        CREATE INDEX idx_pending_scheduled ON pending_responses(scheduled_at);
        RAISE NOTICE 'Column scheduled_at added to pending_responses.';
    ELSE
        RAISE NOTICE 'Column scheduled_at already exists.';
    END IF;

    -- Добавляем send_order для порядка отправки в batch
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name = 'pending_responses' AND column_name = 'send_order') THEN
        ALTER TABLE pending_responses ADD COLUMN send_order INTEGER DEFAULT 0;
        RAISE NOTICE 'Column send_order added to pending_responses.';
    ELSE
        RAISE NOTICE 'Column send_order already exists.';
    END IF;

    -- Добавляем batch_name для названия пакета
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name = 'pending_responses' AND column_name = 'batch_name') THEN
        ALTER TABLE pending_responses ADD COLUMN batch_name VARCHAR(255);
        RAISE NOTICE 'Column batch_name added to pending_responses.';
    ELSE
        RAISE NOTICE 'Column batch_name already exists.';
    END IF;

END $$;

-- Проверка
SELECT column_name, data_type 
FROM information_schema.columns 
WHERE table_name = 'pending_responses'
ORDER BY ordinal_position;
