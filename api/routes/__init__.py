"""
Routes __init__ for cvgorod-hub API.
"""

from .messages import router as messages
from .clients import router as clients
from .intents import router as intents
from .send import router as send

__all__ = ["messages", "clients", "intents", "send"]
