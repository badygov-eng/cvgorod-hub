"""
Yandex SpeechKit STT service.
Распознавание голосовых сообщений через Yandex SpeechKit API.
"""

import logging
import os
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)

# URL для Yandex SpeechKit STT
YANDEX_STT_URL = "https://stt.api.cloud.yandex.net/speech/v1/stt:recognize"


class STTService:
    """Yandex SpeechKit STT service."""

    def __init__(self):
        self.api_key: str | None = None
        self.folder_id: str | None = None
        self.is_configured = False
        self._load_config()

    def _load_config(self) -> None:
        """Загружает конфигурацию из переменных окружения или секретов."""
        # Пробуем из env
        self.api_key = os.getenv("YANDEX_CLOUD_API_KEY")
        self.folder_id = os.getenv("YANDEX_FOLDER_ID")

        # Если нет в env — пробуем из файла секретов
        if not self.api_key:
            secrets_path = Path.home() / ".secrets" / "cloud" / "yandex.env"
            if secrets_path.exists():
                try:
                    with open(secrets_path) as f:
                        for line in f:
                            line = line.strip()
                            if line.startswith("#") or "=" not in line:
                                continue
                            key, value = line.split("=", 1)
                            if key == "YANDEX_CLOUD_API_KEY":
                                self.api_key = value
                            elif key == "YANDEX_FOLDER_ID":
                                self.folder_id = value
                except Exception as e:
                    logger.warning(f"Failed to load Yandex secrets: {e}")

        self.is_configured = bool(self.api_key and self.folder_id)
        
        if self.is_configured:
            logger.info("Yandex STT configured successfully")
        else:
            logger.warning("Yandex STT not configured (missing API key or folder ID)")

    async def recognize(self, audio_bytes: bytes) -> str:
        """
        Распознаёт речь из аудио через Yandex SpeechKit.

        Args:
            audio_bytes: Аудио данные (OGG/Opus от Telegram)

        Returns:
            Распознанный текст или пустая строка при ошибке
        """
        if not self.is_configured:
            logger.debug("Yandex STT not configured, skipping recognition")
            return ""

        if not audio_bytes:
            return ""

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    YANDEX_STT_URL,
                    params={
                        "lang": "ru-RU",
                        "folderId": self.folder_id,
                        "format": "oggopus",  # Telegram использует OGG/Opus
                    },
                    headers={
                        "Authorization": f"Api-Key {self.api_key}",
                        "Content-Type": "application/octet-stream",
                    },
                    content=audio_bytes,
                )

                if response.status_code == 200:
                    data = response.json()
                    text = data.get("result", "")
                    if text:
                        logger.info(f"STT success: {text[:50]}...")
                    return text
                else:
                    logger.error(
                        f"Yandex STT error: {response.status_code} - {response.text}"
                    )
                    return ""

        except httpx.TimeoutException:
            logger.error("Yandex STT timeout")
            return ""
        except Exception as e:
            logger.error(f"Yandex STT error: {e}")
            return ""


# Singleton instance
_stt_instance: STTService | None = None


def get_stt() -> STTService:
    """Get STT service singleton instance."""
    global _stt_instance
    if _stt_instance is None:
        _stt_instance = STTService()
    return _stt_instance
