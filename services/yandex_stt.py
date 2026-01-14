"""
Yandex SpeechKit STT service.
Stub module for cvgorod-hub.
"""

class STTService:
    """Stub STT service."""

    def __init__(self):
        self.is_configured = False

    async def recognize(self, audio_bytes: bytes) -> str:
        """Recognize speech from audio."""
        return ""


def get_stt() -> STTService:
    """Get STT service instance."""
    return STTService()
