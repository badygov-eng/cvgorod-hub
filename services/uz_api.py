"""
УЗ API клиент для синхронизации customer_uuid маппинга.

УЗ API предоставляет:
- /Account/SignIn — авторизация (JWT токен)
- /Messages/ChatBots — список чатов с customerID (UUID)
"""

import logging
import os
from dataclasses import dataclass
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)


def _load_uz_credentials() -> tuple[str, str, str]:
    """Загрузка УЗ credentials из секретов или env."""
    # Пробуем из секретов (для Docker)
    secrets_path = os.getenv("SECRETS_PATH", os.path.expanduser("~/.secrets"))
    uz_env_path = Path(secrets_path) / "cvgorod" / "uz.env"
    
    url = os.getenv("UZ_API_URL", "")
    username = os.getenv("UZ_USERNAME", "")
    password = os.getenv("UZ_PASSWORD", "")
    
    if uz_env_path.exists():
        logger.info("Loading UZ credentials from %s", uz_env_path)
        with open(uz_env_path) as f:
            for line in f:
                line = line.strip()
                if line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                if key == "UZ_API_URL":
                    url = value
                elif key == "UZ_USERNAME":
                    username = value
                elif key == "UZ_PASSWORD":
                    password = value
    
    return url, username, password


@dataclass
class UZChatBot:
    """Чат из УЗ API."""
    id: int  # cvgorod_chat_id
    customer_id: str  # UUID клиента
    messenger: str
    name: str


class UZApiClient:
    """Клиент для работы с УЗ API."""

    def __init__(self):
        url, username, password = _load_uz_credentials()
        self.base_url = url or "https://web.cvgorod.ru/api/public/v1"
        self.username = username
        self.password = password
        self._token: str | None = None
        
        if self.username:
            logger.info("UZ API configured: %s, user=%s", self.base_url, self.username)
        else:
            logger.warning("UZ credentials not configured")

    async def _get_token(self) -> str | None:
        """Получить JWT токен для авторизации."""
        if not self.username or not self.password:
            logger.error("UZ credentials not configured (UZ_USERNAME, UZ_PASSWORD)")
            return None

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.base_url}/Account/SignIn",
                    json={
                        "userName": self.username,
                        "password": self.password,
                    },
                )

                if response.status_code == 200:
                    data = response.json()
                    self._token = data.get("token")
                    logger.info("UZ API token obtained successfully")
                    return self._token
                else:
                    logger.error("UZ SignIn failed: %d %s", response.status_code, response.text[:200])
                    return None

        except Exception as e:
            logger.error("Failed to get UZ token: %s", e)
            return None

    async def get_chatbots(self) -> list[UZChatBot]:
        """
        Получить список всех чатов из УЗ API.
        
        Returns:
            Список UZChatBot с customerID (UUID) и cvgorod_chat_id
        """
        token = await self._get_token()
        if not token:
            return []

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.get(
                    f"{self.base_url}/Messages/ChatBots",
                    headers={"Authorization": f"Bearer {token}"},
                )

                if response.status_code != 200:
                    logger.error("UZ ChatBots API error: %d", response.status_code)
                    return []

                chatbots_data = response.json()
                logger.info("Fetched %d chatbots from UZ API", len(chatbots_data))

                result = []
                for chat in chatbots_data:
                    customer_id = chat.get("customerID")
                    if not customer_id:
                        continue
                    
                    result.append(UZChatBot(
                        id=chat.get("id", 0),
                        customer_id=customer_id,
                        messenger=chat.get("messenger", "Telegram"),
                        name=chat.get("name", ""),
                    ))

                return result

        except Exception as e:
            logger.error("Failed to fetch UZ chatbots: %s", e)
            return []


# Singleton
uz_api = UZApiClient()
