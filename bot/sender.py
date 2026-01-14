"""
Message Sender — отправка сообщений клиентам в группы.
"""

import logging
from typing import Optional

from telegram import Bot
from telegram.error import TelegramError


logger = logging.getLogger(__name__)


class MessageSender:
    """Отправка сообщений в Telegram группы."""
    
    def __init__(self, bot: Optional[Bot] = None):
        self.bot = bot
    
    async def send_to_chat(
        self,
        chat_id: int,
        text: str,
        parse_mode: str = None,
    ) -> bool:
        """
        Отправка сообщения в чат.
        
        Args:
            chat_id: ID чата
            text: Текст сообщения
            parse_mode: Формат (HTML, Markdown)
        
        Returns:
            True если отправлено успешно
        """
        if not self.bot:
            logger.warning("Bot not initialized, cannot send message")
            return False
        
        try:
            await self.bot.send_message(
                chat_id=chat_id,
                text=text,
                parse_mode=parse_mode,
            )
            logger.info(f"Sent message to chat {chat_id}")
            return True
        except TelegramError as e:
            logger.error(f"Failed to send message to {chat_id}: {e}")
            return False
    
    async def send_with_keyboard(
        self,
        chat_id: int,
        text: str,
        keyboard: list,
        parse_mode: str = None,
    ) -> bool:
        """Отправка сообщения с inline keyboard."""
        if not self.bot:
            return False
        
        from telegram import InlineKeyboardMarkup
        
        try:
            await self.bot.send_message(
                chat_id=chat_id,
                text=text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode=parse_mode,
            )
            return True
        except TelegramError as e:
            logger.error(f"Failed to send keyboard message to {chat_id}: {e}")
            return False


# Глобальный экземпляр
sender = MessageSender()
