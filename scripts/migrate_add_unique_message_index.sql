-- Migration: Add unique constraint on (chat_id, telegram_message_id)
-- Date: 2026-01-14
-- Purpose: Prevent duplicate messages during Telegram sync

-- Add unique index to prevent duplicate messages
CREATE UNIQUE INDEX IF NOT EXISTS idx_messages_chat_telegram_id 
ON messages(chat_id, telegram_message_id);

-- Verify index was created
SELECT 
    schemaname,
    tablename,
    indexname,
    indexdef
FROM pg_indexes
WHERE tablename = 'messages' 
    AND indexname = 'idx_messages_chat_telegram_id';
