"""Application service interfaces for dependency injection."""

from .browser_interface import IBrowserService
from .cache_interface import ICacheService
from .logging_interface import ILoggingService

__all__ = [
    "IBrowserService",
    "ICacheService",
    "ILoggingService",
]
