"""
Sandbox Manager — управление песочницей ответов.
"""

import logging
from typing import Optional

from telegram import Bot
from telegram.error import TelegramError

from config import settings
from services.database import db
from bot.sender import MessageSender

logger = logging.getLogger(__name__)


class SandboxManager:
    """Менеджер песочницы для ответов бота."""
    
    def __init__(self):
        self.sender = MessageSender()
        self._bot: Optional[Bot] = None
    
    def set_bot(self, bot: Bot) -> None:
        """Установка бота для отправки сообщений."""
        self._bot = bot
        self.sender.bot = bot
    
    async def send_approved_message(
        self,
        chat_id: int,
        text: str,
    ) -> bool:
        """
        Отправка одобренного сообщения в чат.
        
        Args:
            chat_id: ID чата
            text: Текст сообщения
        
        Returns:
            True если отправлено успешно
        """
        return await self.sender.send_to_chat(
            chat_id=chat_id,
            text=text,
            parse_mode="HTML",
        )
    
    async def notify_admin_about_pending(
        self,
        pending_id: int,
        chat_id: int,
        client_name: Optional[str],
        text: str,
        admin_id: int,
    ) -> bool:
        """
        Уведомление администратора о новом ожидающем сообщении.
        
        Args:
            pending_id: ID записи в pending_responses
            chat_id: ID чата
            client_name: Имя клиента
            text: Текст сообщения
            admin_id: ID администратора для уведомления
        """
        if not self._bot:
            logger.warning("Bot not initialized, cannot notify admin")
            return False
        
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup
        
        keyboard = [
            [
                InlineKeyboardButton("Одобрить", callback_data=f"sandbox_approve:{pending_id}"),
                InlineKeyboardButton("Отклонить", callback_data=f"sandbox_reject:{pending_id}"),
            ],
            [
                InlineKeyboardButton("Изменить", callback_data=f"sandbox_edit:{pending_id}"),
            ],
        ]
        
        message = (
            f"📬 <b>Новый ответ для одобрения</b>\n\n"
            f"👤 Клиент: {client_name or 'Неизвестен'}\n"
            f"💬 Текст:\n{text}\n\n"
            f"ID: {pending_id}"
        )
        
        try:
            await self._bot.send_message(
                chat_id=admin_id,
                text=message,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="HTML",
            )
            logger.info(f"Notified admin {admin_id} about pending {pending_id}")
            return True
        except TelegramError as e:
            logger.error(f"Failed to notify admin: {e}")
            return False
    
    async def get_pending_for_approval(
        self,
        limit: int = 10,
    ) -> list[dict]:
        """Получение ожидающих сообщений для отображения администратору."""
        result = await db.fetch(
            """
            SELECT id, chat_id, client_name, response_text, context, created_at
            FROM pending_responses
            WHERE status = 'pending'
            ORDER BY created_at ASC
            LIMIT $1
            """,
            limit
        )
        
        return [
            {
                "id": row["id"],
                "chat_id": row["chat_id"],
                "client_name": row.get("client_name"),
                "text": row["response_text"],
                "context": row.get("context"),
                "created_at": str(row["created_at"]),
            }
            for row in result
        ]


# Глобальный экземпляр
sandbox_manager = SandboxManager()
