"""
Routes __init__ for cvgorod-hub API.
"""

from .clients import router as clients
from .expectations import router as expectations
from .intents import router as intents
from .messages import router as messages
from .reports import router as reports
from .send import router as send

__all__ = ["messages", "clients", "intents", "send", "reports", "expectations"]
