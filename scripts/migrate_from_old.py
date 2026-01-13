"""
Migration script from old project to cvgorod-hub.
Copy messages, chats, users from old database to new structure.
"""

import asyncio
import asyncpg
import os


async def migrate():
    """
    Миграция данных из старого проекта.
    
    Sources:
    - Old DATABASE_URL from environment
    - Default: postgresql://localhost/cvgorod_messages
    
    Target:
    - New DATABASE_URL for cvgorod-hub
    - Default: postgresql://localhost/cvgorod_hub
    """
    old_db_url = os.getenv("OLD_DATABASE_URL", "postgresql://localhost/cvgorod_messages")
    new_db_url = os.getenv("DATABASE_URL", "postgresql://localhost/cvgorod_hub")
    
    print(f"Old DB: {old_db_url}")
    print(f"New DB: {new_db_url}")
    
    old_conn = await asyncpg.connect(old_db_url)
    new_conn = await asyncpg.connect(new_db_url)
    
    try:
        # Миграция чатов
        print("Migrating chats...")
        chats = await old_conn.fetch("SELECT * FROM chats")
        for chat in chats:
            try:
                await new_conn.execute(
                    """
                    INSERT INTO chats (id, name, chat_type, folder, members_count, is_active, created_at, updated_at)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                    ON CONFLICT (id) DO NOTHING
                    """,
                    chat["id"], chat["name"], chat["chat_type"], chat["folder"],
                    chat.get("members_count", 0), chat.get("is_active", True),
                    chat.get("created_at"), chat.get("updated_at"),
                )
            except Exception as e:
                print(f"Error inserting chat {chat['id']}: {e}")
        print(f"Migrated {len(chats)} chats")
        
        # Миграция пользователей
        print("Migrating users...")
        users = await old_conn.fetch("SELECT * FROM users")
        for user in users:
            try:
                await new_conn.execute(
                    """
                    INSERT INTO users (id, username, first_name, last_name, is_manager, first_seen, last_seen)
                    VALUES ($1, $2, $3, $4, $5, $6, $7)
                    ON CONFLICT (id) DO NOTHING
                    """,
                    user["id"], user.get("username"), user.get("first_name"),
                    user.get("last_name"), user.get("is_manager", False),
                    user.get("first_seen"), user.get("last_seen"),
                )
            except Exception as e:
                print(f"Error inserting user {user['id']}: {e}")
        print(f"Migrated {len(users)} users")
        
        # Миграция сообщений
        print("Migrating messages...")
        messages = await old_conn.fetch("SELECT * FROM messages ORDER BY timestamp DESC LIMIT 100000")
        for msg in messages:
            try:
                await new_conn.execute(
                    """
                    INSERT INTO messages (id, telegram_message_id, chat_id, user_id, text, message_type, reply_to_message_id, timestamp, created_at)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                    ON CONFLICT (id) DO NOTHING
                    """,
                    msg["id"], msg["telegram_message_id"], msg["chat_id"], msg["user_id"],
                    msg.get("text"), msg.get("message_type", "text"),
                    msg.get("reply_to_message_id"), msg.get("timestamp"), msg.get("created_at"),
                )
            except Exception as e:
                print(f"Error inserting message {msg['id']}: {e}")
        print(f"Migrated {len(messages)} messages")
        
        # Миграция сессий агента (опционально)
        print("Migrating agent sessions...")
        try:
            sessions = await old_conn.fetch("SELECT * FROM agent_sessions ORDER BY started_at DESC LIMIT 10000")
            for session in sessions:
                try:
                    await new_conn.execute(
                        """
                        INSERT INTO agent_sessions (
                            id, session_id, question, context, started_at, finished_at,
                            duration_seconds, tools_used, api_calls_count, tokens_used,
                            cost_usd, success, final_answer, answer_preview,
                            entities_found_count, critical_issues_count, clients_involved,
                            model_used, provider, session_data, created_at
                        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18, $19, $20, $21)
                        ON CONFLICT (session_id) DO NOTHING
                        """,
                        session["id"], session["session_id"], session["question"],
                        session.get("context"), session.get("started_at"), session.get("finished_at"),
                        session.get("duration_seconds", 0), session.get("tools_used", []),
                        session.get("api_calls_count", 0), session.get("tokens_used", 0),
                        session.get("cost_usd", 0), session.get("success", True),
                        session.get("final_answer"), session.get("answer_preview"),
                        session.get("entities_found_count", 0), session.get("critical_issues_count", 0),
                        session.get("clients_involved", []), session.get("model_used"),
                        session.get("provider"), session.get("session_data", {}),
                        session.get("created_at"),
                    )
                except Exception as e:
                    print(f"Error inserting session {session['session_id'][:8]}: {e}")
            print(f"Migrated {len(sessions)} agent sessions")
        except Exception as e:
            print(f"Agent sessions table not found in old DB: {e}")
        
        print("\nMigration completed successfully!")
        
    finally:
        await old_conn.close()
        await new_conn.close()


if __name__ == "__main__":
    asyncio.run(migrate())
