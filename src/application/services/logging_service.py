"""Logging service implementation."""

import functools
import time
from datetime import datetime

from application.interfaces import ILoggingService


class LoggingService(ILoggingService):
    """
    Logging service implementation extracted from utils.py.

    Provides enhanced logging with timestamps and levels.
    Includes timing functionality for performance monitoring.
    """

    def __init__(self, log_level: str = "INFO"):
        """
        Initialize logging service.

        Args:
            log_level: Minimum log level to output (DEBUG, INFO, WARNING, ERROR)
        """
        self.log_level = log_level.upper()
        self._level_hierarchy = {"DEBUG": 0, "INFO": 1, "WARNING": 2, "ERROR": 3}

    def log(self, level: str, message: str) -> None:
        """Log a message at the specified level."""
        level = level.upper()

        # Check if level should be logged
        if self._level_hierarchy.get(level, 1) < self._level_hierarchy.get(self.log_level, 1):
            return

        # Create timestamp
        timestamp = datetime.now().strftime("%H:%M:%S")

        # Color coding for different levels (if terminal supports it)
        level_colors = {"DEBUG": "🔍", "INFO": "ℹ️", "WARNING": "⚠️", "ERROR": "❌"}

        icon = level_colors.get(level, "📝")

        # Format and print message
        formatted_message = f"[{timestamp}] {icon} {level}: {message}"
        print(formatted_message)

    def debug(self, message: str) -> None:
        """Log debug message."""
        self.log("DEBUG", message)

    def info(self, message: str) -> None:
        """Log info message."""
        self.log("INFO", message)

    def warning(self, message: str) -> None:
        """Log warning message."""
        self.log("WARNING", message)

    def error(self, message: str) -> None:
        """Log error message."""
        self.log("ERROR", message)

    def time_operation(self, operation_name: str):
        """Context manager for timing operations."""
        return TimingContext(self, operation_name)


class TimingContext:
    """Context manager for timing operations."""

    def __init__(self, logging_service: LoggingService, operation_name: str):
        """
        Initialize timing context.

        Args:
            logging_service: Service for logging results
            operation_name: Name of operation being timed
        """
        self.logger = logging_service
        self.operation_name = operation_name
        self.start_time = None

    def __enter__(self):
        """Start timing."""
        self.start_time = time.time()
        self.logger.debug(f"⏱️ Starting {self.operation_name}...")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """End timing and log result."""
        if self.start_time:
            execution_time = time.time() - self.start_time

            if exc_type is None:
                self.logger.debug(f"✅ {self.operation_name} completed in {execution_time:.3f}s")
            else:
                self.logger.error(f"❌ {self.operation_name} failed after {execution_time:.3f}s: {exc_val}")


def timing_decorator(operation_name: str):
    """Decorator to time function execution and log results."""

    def decorator(func):
        @functools.wraps(func)
        def wrapper(self, *args, **kwargs):
            # Assume self has a logger attribute
            logger = getattr(self, "logger", None) or getattr(self, "_logger", None)

            if not logger:
                # Fallback to direct execution if no logger found
                return func(self, *args, **kwargs)

            start_time = time.time()
            try:
                result = func(self, *args, **kwargs)
                execution_time = time.time() - start_time
                logger.debug(f"✅ {operation_name} completed in {execution_time:.3f}s")
                return result
            except Exception as e:
                execution_time = time.time() - start_time
                logger.error(f"❌ {operation_name} failed after {execution_time:.3f}s: {e}")
                raise

        return wrapper

    return decorator
