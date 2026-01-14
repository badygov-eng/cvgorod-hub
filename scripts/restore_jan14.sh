#!/bin/bash
# =============================================================================
# Restore messages from Jan 14, 2026
# Recovers messages that were lost during migration from cvgorod-agent to cvgorod-hub
# =============================================================================

set -e

echo "========================================"
echo "  Restore Jan 14 Messages"
echo "========================================"
echo ""

# Check connection to agent database
echo "[1/4] Checking agent database..."
AGENT_MSGS=$(ssh badygovdaniil@158.160.153.14 -i ~/.ssh/yandex_vm_key "
    docker exec cvgorod-agent-postgres psql -U cvgorod -d cvgorod_agent -t -c \"SELECT COUNT(*) FROM messages WHERE created_at >= '2026-01-14' AND created_at < '2026-01-15';\"
" 2>/dev/null | tr -d '[:space:]')

if [ -z "$AGENT_MSGS" ] || [ "$AGENT_MSGS" = "0" ]; then
    echo "  ⚠️  No messages found in agent database for Jan 14"
    echo "  Checking if agent database is accessible..."
    ssh badygovdaniil@158.160.153.14 -i ~/.ssh/yandex_vm_key "docker exec cvgorod-agent-postgres psql -U cvgorod -d cvgorod_agent -c \"SELECT 'Agent DB accessible' as status;\" 2>/dev/null || echo '  ❌ Agent database not accessible'"
    exit 0
fi

echo "  ✅ Found $AGENT_MSGS messages in agent database for Jan 14"

# Get messages from agent database and insert into hub
echo ""
echo "[2/4] Restoring messages to cvgorod-hub..."

ssh badygovdaniil@158.160.153.14 -i ~/.ssh/yandex_vm_key "
    docker exec cvgorod-agent-postgres psql -U cvgorod -d cvgorod_agent -c \"
        INSERT INTO messages (
            telegram_message_id, chat_id, user_id, text,
            message_type, reply_to_message_id, timestamp, pattern_id, created_at
        )
        SELECT 
            m.telegram_message_id, m.chat_id, m.user_id, m.text,
            m.message_type, m.reply_to_message_id, m.timestamp, m.pattern_id, m.created_at
        FROM messages m
        WHERE m.created_at >= '2026-01-14' AND m.created_at < '2026-01-15'
        ON CONFLICT (telegram_message_id, chat_id) DO NOTHING;
    \"
"

RESTORED=$(ssh badygovdaniil@158.160.153.14 -i ~/.ssh/yandex_vm_key "
    docker exec cvgorod-hub-postgres psql -U cvgorod -d cvgorod_hub -t -c \"
        SELECT COUNT(*) FROM messages WHERE created_at >= '2026-01-14' AND created_at < '2026-01-15';
    \"
" 2>/dev/null | tr -d '[:space:]')

echo "  ✅ Restored messages for Jan 14: $RESTORED records"

# Also restore chats and users that might be missing
echo ""
echo "[3/4] Restoring missing chats and users..."

ssh badygovdaniil@158.160.153.14 -i ~/.ssh/yandex_vm_key "
    # Restore chats
    docker exec cvgorod-agent-postgres psql -U cvgorod -d cvgorod_agent -c \"
        INSERT INTO chats (id, name, chat_type, folder, members_count, is_active, created_at, updated_at)
        SELECT id, name, chat_type, folder, members_count, is_active, created_at, updated_at
        FROM chats
        WHERE created_at >= '2026-01-14'
        ON CONFLICT (id) DO NOTHING;
    \"
    
    # Restore users  
    docker exec cvgorod-agent-postgres psql -U cvgorod -d cvgorod_agent -c \"
        INSERT INTO users (id, username, first_name, last_name, is_manager, role_id, first_seen, last_seen)
        SELECT id, username, first_name, last_name, is_manager, role_id, first_seen, last_seen
        FROM users
        WHERE first_seen >= '2026-01-14'
        ON CONFLICT (id) DO NOTHING;
    \"
"

echo "  ✅ Chats and users restored"

# Final verification
echo ""
echo "[4/4] Verification..."

TOTAL_MSGS=$(ssh badygovdaniil@158.160.153.14 -i ~/.ssh/yandex_vm_key "
    docker exec cvgorod-hub-postgres psql -U cvgorod -d cvgorod_hub -t -c \"SELECT COUNT(*) FROM messages;\"
" 2>/dev/null | tr -d '[:space:]')

LAST_MSG=$(ssh badygovdaniil@158.160.153.14 -i ~/.ssh/yandex_vm_key "
    docker exec cvgorod-hub-postgres psql -U cvgorod -d cvgorod_hub -t -c \"SELECT MAX(created_at) FROM messages;\"
" 2>/dev/null | tr -d '[:space:]')

echo ""
echo "========================================"
echo "  Results"
echo "========================================"
echo "  📊 Total messages in DB: $TOTAL_MSGS"
echo "  🕐 Last message: $LAST_MSG"
echo ""
