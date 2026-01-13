"""
Message Collector Service для CVGorod.

Собирает сообщения из Telegram групп и сохраняет в PostgreSQL.
Подключается как listener к python-telegram-bot Application.

Поддерживает:
- Текстовые сообщения
- Голосовые сообщения (с расшифровкой через Yandex SpeechKit)
- Определение ролей (директор, менеджер, бот, клиент)
- Интеграция с Yandex Tracker для логирования событий
"""

import logging
import re
from datetime import datetime
from typing import Optional, Dict, Any, Set

from telegram import Update
from telegram.ext import Application, ContextTypes

from services.database import db
from services.role_repository import role_repository, get_user_role, is_staff
from services.yandex_stt import get_stt
from services.tracker import tracker, log_telegram_message, log_database_operation
from config.roles import (
    MANAGER_IDS, BOT_IDS, MANAGER_NAMES,
    UserRole
)

logger = logging.getLogger(__name__)

# Обратная совместимость
MANAGER_KEYWORDS = MANAGER_NAMES


class MessageCollector:
    """
    Коллектор сообщений из Telegram групп.

    Функции:
    - Обработка входящих сообщений
    - Парсинг и валидация данных
    - Сохранение в PostgreSQL
    - Определение типа пользователя (клиент/менеджер)
    """

    def __init__(self):
        self._known_managers: Set[int] = set()
        self._processed_message_ids: Set[int] = set()
        self._message_buffer: Dict[int, datetime] = {}

    async def initialize(self) -> None:
        """Инициализация коллектора."""
        # Загружаем список менеджеров из базы
        managers = await db.get_all_managers()
        self._known_managers = {m["id"] for m in managers}
        logger.info(f"MessageCollector initialized with {len(self._known_managers)} known managers")

    async def handle_update(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """
        Обработка входящего обновления от Telegram.

        Этот метод вызывается для каждого сообщения в группах,
        где бот имеет доступ (Group Privacy = OFF).
        """
        try:
            # Игнорируем сообщения от ботов
            if update.message and update.message.from_user and update.message.from_user.is_bot:
                return

            # Пропускаем системные сообщения
            if not update.message or not update.message.text:
                return

            message_id = update.message.message_id
            chat_id = update.message.chat_id
            user_id = update.message.from_user.id

            # Проверка на дубликаты (защита от повторной обработки)
            if message_id in self._processed_message_ids:
                return

            self._processed_message_ids.add(message_id)

            # Проверка chat_id (должен быть отрицательным для групп)
            if chat_id > 0:
                return  # Это личный чат, не группа

            # Парсинг данных сообщения
            message_data = await self._parse_message(update, context, message_id)
            if message_data is None:
                return

            # Сохранение в базу
            await self._save_to_database(message_data)

            # Логируем сообщение в Tracker
            await log_telegram_message(
                chat_id=chat_id,
                message_type=message_data["message_type"],
                has_intent=bool(message_data.get("pattern_id")),
            )

            logger.debug(
                f"Message saved: chat={chat_id}, user={user_id}, "
                f"text={message_data['text'][:50]}..."
            )

        except Exception as e:
            logger.error(f"Error processing message: {e}", exc_info=True)
            # Логируем ошибку в Yandex Tracker
            await tracker.error(
                summary=f"Error processing Telegram message",
                data={
                    "error": str(e),
                    "chat_id": chat_id if 'chat_id' in locals() else None,
                    "user_id": user_id if 'user_id' in locals() else None,
                },
            )

    async def _parse_message(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        message_id: int,
    ) -> Optional[Dict[str, Any]]:
        """Парсит данные сообщения из Update."""
        if not update.message:
            return None

        msg = update.message

        # Основные данные
        chat = msg.chat
        user = msg.from_user

        if not chat or not user:
            return None

        # Извлекаем текст (включая расшифровку голосовых)
        text = await self._extract_text(msg, context)
        if not text or len(text.strip()) < 2:
            return None  # Пропускаем пустые/слишком короткие сообщения

        # Определяем роль пользователя
        user_role = await role_repository.get_user_role(user.id)

        return {
            "telegram_message_id": message_id,
            "chat_id": chat.id,
            "chat_name": chat.title or str(chat.id),
            "chat_type": "supergroup" if chat.type in ["supergroup", "group"] else chat.type,
            "user_id": user.id,
            "username": user.username,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "text": text,
            "message_type": self._get_message_type(msg),
            "reply_to_message_id": msg.reply_to_message.message_id if msg.reply_to_message else None,
            "timestamp": msg.date,
            "role_id": user_role.id,
            "is_staff": user_role.is_staff,
            "is_bot": user_role.is_bot,
        }

    async def _extract_text(self, message, context) -> Optional[str]:
        """Извлекает текст из сообщения (включая расшифровку голосовых)."""
        if message.text:
            return message.text
        if message.caption:
            return message.caption
        
        # Расшифровка голосовых сообщений
        if message.voice:
            return await self._transcribe_voice(message, context)
        
        return None
    
    async def _transcribe_voice(self, message, context) -> Optional[str]:
        """Расшифровывает голосовое сообщение через Yandex SpeechKit."""
        stt = get_stt()
        if not stt.is_configured:
            logger.debug("Yandex STT not configured, skipping voice transcription")
            return "[Голосовое сообщение]"
        
        try:
            # Скачиваем аудио файл
            voice = message.voice
            file = await context.bot.get_file(voice.file_id)
            audio_bytes = await file.download_as_bytearray()
            
            # Расшифровываем
            text = await stt.recognize(bytes(audio_bytes))
            
            if text:
                logger.info(f"Voice transcribed: {text[:50]}...")
                return f"[Голосовое] {text}"
            else:
                return "[Голосовое сообщение - не удалось расшифровать]"
                
        except Exception as e:
            logger.error(f"Voice transcription failed: {e}")
            return "[Голосовое сообщение]"

    def _get_message_type(self, message) -> str:
        """Определяет тип сообщения."""
        if message.text:
            return "text"
        if message.photo:
            return "photo"
        if message.document:
            return "document"
        if message.sticker:
            return "sticker"
        if message.voice:
            return "voice"
        if message.video:
            return "video"
        if message.animation:
            return "animation"
        return "other"

    def _detect_manager(self, user, text: str) -> bool:
        """
        Определяет является ли пользователь менеджером или директором.

        Проверяет:
        - ID пользователя в конфиге ролей (config/roles.py)
        - ID пользователя в списке известных менеджеров из БД
        - Username/name содержит ключевые слова менеджера
        """
        # 1. Проверяем по конфигу ролей (приоритет)
        if is_staff(user.id):
            return True
        
        # 2. Проверяем по ID из базы данных
        if user.id in self._known_managers:
            return True
        
        # 3. Проверяем по ID из конфига (статический список)
        if user.id in MANAGER_IDS:
            return True

        # 4. Проверяем по username
        if user.username:
            username_lower = user.username.lower()
            for keyword in MANAGER_KEYWORDS:
                if keyword in username_lower:
                    return True

        # 5. Проверяем по имени
        if user.first_name:
            first_lower = user.first_name.lower()
            for keyword in MANAGER_KEYWORDS:
                if keyword in first_lower:
                    return True

        return False

    async def _save_to_database(self, data: Dict[str, Any]) -> None:
        """Сохраняет данные сообщения в базу."""
        start_time = datetime.utcnow()
        try:
            # Сохраняем или обновляем чат
            await db.get_or_create_chat(
                chat_id=data["chat_id"],
                chat_name=data["chat_name"],
                chat_type=data["chat_type"],
            )

            # Сохраняем или обновляем пользователя с role_id
            await db.get_or_create_user(
                user_id=data["user_id"],
                username=data["username"],
                first_name=data["first_name"],
                last_name=data["last_name"],
                is_manager=data.get("is_staff", False),  # Обратная совместимость
            )

            # Обновляем role_id если он известен
            if data.get("role_id"):
                await db.execute(
                    "UPDATE users SET role_id = $1 WHERE id = $2",
                    data["role_id"], data["user_id"]
                )

            # Обновляем время last_seen
            await db.update_user_seen(data["user_id"])

            # Классифицируем сообщение
            pattern_id = None
            if data.get("text") and not data.get("is_bot"):
                pattern_id = await db.classify_message(data["text"], data["user_id"])

            # Сохраняем сообщение
            await db.execute(
                """
                INSERT INTO messages (
                    telegram_message_id, chat_id, user_id, text,
                    message_type, reply_to_message_id, timestamp, pattern_id
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                RETURNING id
                """,
                data["telegram_message_id"],
                data["chat_id"],
                data["user_id"],
                data["text"],
                data["message_type"],
                data.get("reply_to_message_id"),
                data["timestamp"],
                pattern_id,
            )

            # Логируем успешную операцию в Tracker
            duration_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
            await log_database_operation(
                operation="save_message",
                table="messages",
                success=True,
                duration_ms=duration_ms,
            )

        except Exception as e:
            # Логируем ошибку в Tracker
            duration_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
            await log_database_operation(
                operation="save_message",
                table="messages",
                success=False,
                duration_ms=duration_ms,
                error=str(e),
            )
            logger.error(f"Error saving to database: {e}", exc_info=True)
            raise

    def register_handlers(self, application: Application) -> None:
        """
        Регистрирует обработчики в Application.

        Использует MessageHandler с фильтром TEXT
        для перехвата всех текстовых сообщений в группах.
        """
        from telegram.ext import MessageHandler, filters

        # Добавляем handler для всех текстовых сообщений
        handler = MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            self.handle_update,
        )
        application.add_handler(handler)

        logger.info("MessageCollector handlers registered")


# Глобальный экземпляр
message_collector = MessageCollector()


async def main() -> None:
    """
    Запуск бота-коллектора сообщений.
    
    Инициализирует Telegram Application, регистрирует обработчики
    и начинает приём сообщений из групп.
    """
    import logging
    from telegram.ext import Application
    
    from config import settings
    from services.database import db
    
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    logger = logging.getLogger(__name__)
    
    if not settings.TELEGRAM_BOT_TOKEN:
        raise ValueError("TELEGRAM_BOT_TOKEN не задан")
    
    logger.info("Starting Message Collector Bot...")
    
    # Подключаемся к базе данных
    logger.info("Connecting to database...")
    await db.connect()
    logger.info("Database connected")

    # Инициализируем Tracker
    from services.tracker import init_tracker, shutdown_tracker
    await init_tracker()

    # Создаём Application
    application = (
        Application.builder()
        .token(settings.TELEGRAM_BOT_TOKEN)
        .post_init(lambda app: logger.info("Bot initialized"))
        .build()
    )
    
    # Регистрируем обработчики
    message_collector.register_handlers(application)
    
    # Инициализируем коллектор (загружает менеджеров из БД)
    await message_collector.initialize()
    
    # Запускаем бота
    logger.info("Starting polling...")
    await application.initialize()
    await application.start()
    await application.updater.start_polling(
        drop_pending_updates=True,
        timeout=30,
    )
    
    # Ожидаем завершения
    try:
        await application.updater.stop()
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        await shutdown_tracker()
        await application.stop()
        await application.shutdown()


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())

