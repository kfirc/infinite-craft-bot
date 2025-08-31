"""Interface for logging service."""

from abc import ABC, abstractmethod


class ILoggingService(ABC):
    """Interface for logging operations."""

    @abstractmethod
    def log(self, level: str, message: str) -> None:
        """Log a message at the specified level."""

    @abstractmethod
    def debug(self, message: str) -> None:
        """Log debug message."""

    @abstractmethod
    def info(self, message: str) -> None:
        """Log info message."""

    @abstractmethod
    def warning(self, message: str) -> None:
        """Log warning message."""

    @abstractmethod
    def error(self, message: str) -> None:
        """Log error message."""

    @abstractmethod
    def time_operation(self, operation_name: str):
        """Context manager for timing operations."""
