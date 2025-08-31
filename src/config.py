#!/usr/bin/env python3
"""
Configuration Management for Infinite Craft Bot.

This module provides a comprehensive configuration system with default
settings and environment variable overrides via .env file support.

Usage:
    from config import Config
    config = Config()

    # Use configuration values
    if not config.SKIP_ENTER_PROMPT:
        input("Press Enter to continue...")
"""

import os
from pathlib import Path
from typing import Any, Dict

from dotenv import load_dotenv


class Config:
    """
    Base configuration class with default settings for automation.

    All configuration values can be overridden via environment variables
    or .env file.
    """

    def __init__(self):
        """Initialize configuration, loading .env file if it exists."""
        # Load .env file from project root (parent of src directory)
        env_path = Path(__file__).parent.parent / ".env"
        if env_path.exists():
            load_dotenv(env_path)

        # Initialize all config values
        self._load_config()

    def _load_config(self):
        """Load all configuration values with environment overrides."""
        # ================================
        # USER INTERACTION SETTINGS
        # ================================
        self.SKIP_ENTER_PROMPT = self._get_bool_env("SKIP_ENTER_PROMPT", False)
        self.AUTO_ASSUME_WEBSITE_READY = self._get_bool_env("AUTO_ASSUME_WEBSITE_READY", False)

        # ================================
        # BROWSER SETTINGS
        # ================================
        self.CHROME_DEBUG_PORT = self._get_int_env("CHROME_DEBUG_PORT", 9222)
        self.CHROME_CONNECTION_TIMEOUT = self._get_int_env("CHROME_CONNECTION_TIMEOUT", 5)
        self.GAME_LOAD_TIMEOUT = self._get_int_env("GAME_LOAD_TIMEOUT", 10)

        # ================================
        # GAME TIMING SETTINGS (from utils.py)
        # ================================
        # Core game timing (based on game rules from memory bank)
        self.MERGE_MAX_WAIT_TIME = self._get_float_env("MERGE_MAX_WAIT_TIME", 2.0)
        self.ELEMENT_APPEARANCE_MAX_WAIT = self._get_float_env("ELEMENT_APPEARANCE_MAX_WAIT", 2.0)
        self.POLL_INTERVAL = self._get_float_env("POLL_INTERVAL", 0.1)
        self.STABLE_CHECKS_REQUIRED = self._get_int_env("STABLE_CHECKS_REQUIRED", 3)

        # Actual delays used in the code (from time.sleep calls)
        self.COMBINATION_PROCESSING_DELAY = self._get_float_env("COMBINATION_PROCESSING_DELAY", 0.8)
        self.SCROLL_COMPLETION_DELAY = self._get_float_env("SCROLL_COMPLETION_DELAY", 0.3)
        self.COMBINATION_RESULT_DELAY = self._get_float_env("COMBINATION_RESULT_DELAY", 4.0)
        self.CHROME_TAB_SWITCH_DELAY = self._get_float_env("CHROME_TAB_SWITCH_DELAY", 3.0)
        self.DIALOG_CLOSE_DELAY = self._get_float_env("DIALOG_CLOSE_DELAY", 0.5)
        self.MENU_OPERATION_DELAY = self._get_float_env("MENU_OPERATION_DELAY", 1.0)
        self.SAVE_OPERATION_DELAY = self._get_float_env("SAVE_OPERATION_DELAY", 2.0)

        # ================================
        # AUTOMATION STRATEGY SETTINGS
        # ================================
        # Attempt limits (from actual code usage)
        self.DEFAULT_MAX_ATTEMPTS = self._get_int_env("DEFAULT_MAX_ATTEMPTS", 50)
        self.MAX_ATTEMPTS_BETWEEN_SUCCESS = self._get_int_env("MAX_ATTEMPTS_BETWEEN_SUCCESS", 50)
        self.MAX_ATTEMPTS_BEFORE_CLEAR = self._get_int_env("MAX_ATTEMPTS_BEFORE_CLEAR", 5)
        self.DRAG_MAX_RETRIES = self._get_int_env("DRAG_MAX_RETRIES", 3)

        # Target word automation
        self.TARGET_WORD_MAX_ATTEMPTS = self._get_int_env("TARGET_WORD_MAX_ATTEMPTS", 50)
        self.TOP_COMBINATIONS_PER_ITERATION = self._get_int_env("TOP_COMBINATIONS_PER_ITERATION", 5)

        # ================================
        # GAME MECHANICS SETTINGS (from utils.py)
        # ================================
        # Workspace management
        self.WORKSPACE_LOCATIONS_COUNT = self._get_int_env("WORKSPACE_LOCATIONS_COUNT", 5)

        # Distance tolerances (from hardcoded values)
        self.MERGE_DISTANCE_TOLERANCE = self._get_int_env("MERGE_DISTANCE_TOLERANCE", 50)
        self.ELEMENT_POSITION_TOLERANCE = self._get_int_env("ELEMENT_POSITION_TOLERANCE", 60)

        # Drag mechanics (actual values from utils.py)
        self.DRAG_PIXEL_STEPS = self._get_int_env("DRAG_PIXEL_STEPS", 300)
        self.DRAG_MAX_STEPS = self._get_int_env("DRAG_MAX_STEPS", 3)
        self.DRAG_HOLD_DURATION = self._get_float_env("DRAG_HOLD_DURATION", 0.05)
        self.SCROLL_ATTEMPTS_MAX = self._get_int_env("SCROLL_ATTEMPTS_MAX", 3)

        # ================================
        # LOGGING AND DEBUG SETTINGS
        # ================================
        self.LOG_LEVEL = self._get_env("LOG_LEVEL", "INFO")
        self.ENABLE_TIMING_LOGS = self._get_bool_env("ENABLE_TIMING_LOGS", True)
        self.ENABLE_DEBUG_LOGS = self._get_bool_env("ENABLE_DEBUG_LOGS", False)

        # ================================
        # FILE PATHS AND CACHING
        # ================================
        self.AUTOMATION_CACHE_FILE = self._get_env("AUTOMATION_CACHE_FILE", "automation.cache.json")
        self.EMBEDDINGS_CACHE_FILE = self._get_env("EMBEDDINGS_CACHE_FILE", "embeddings.cache.json")

        # ================================
        # TESTING AND DEVELOPMENT
        # ================================
        self.TEST_MODE = self._get_bool_env("TEST_MODE", False)
        self.DRY_RUN = self._get_bool_env("DRY_RUN", False)
        self.ENABLE_PERFORMANCE_TIMING = self._get_bool_env("ENABLE_PERFORMANCE_TIMING", True)
        self.KEEP_BROWSER_OPEN_DELAY = self._get_float_env("KEEP_BROWSER_OPEN_DELAY", 10.0)

    def _get_env(self, key: str, default: str) -> str:
        """Get string environment variable with default."""
        return os.getenv(key, default)

    def _get_int_env(self, key: str, default: int) -> int:
        """Get integer environment variable with default."""
        try:
            return int(os.getenv(key, str(default)))
        except (ValueError, TypeError):
            return default

    def _get_float_env(self, key: str, default: float) -> float:
        """Get float environment variable with default."""
        try:
            return float(os.getenv(key, str(default)))
        except (ValueError, TypeError):
            return default

    def _get_bool_env(self, key: str, default: bool) -> bool:
        """Get boolean environment variable with default."""
        value = os.getenv(key, str(default)).lower()
        return value in ("true", "1", "yes", "on", "enabled")

    def get_strategy_config(self, strategy_type: str = "default") -> Dict[str, Any]:
        """Get configuration dict for specific automation strategy.

        Args:
            strategy_type: Type of strategy ('target_word', 'exploration',
                          'default')

        Returns:
            Configuration dictionary for the strategy
        """
        base_config = {
            "max_attempts": self.DEFAULT_MAX_ATTEMPTS,
            "max_attempts_between_success": self.MAX_ATTEMPTS_BETWEEN_SUCCESS,
        }

        if strategy_type == "target_word":
            return {
                **base_config,
                "type": "target_word_hunter",
                "max_attempts": self.TARGET_WORD_MAX_ATTEMPTS,
                "top_combinations_per_iteration": self.TOP_COMBINATIONS_PER_ITERATION,
                "test_alpha_weights": False,
            }
        elif strategy_type == "exploration":
            return {**base_config, "type": "exploration", "max_attempts": 100, "target_new_elements": 20}
        else:
            return base_config

    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dict for logging/debugging."""
        return {key: value for key, value in self.__dict__.items() if not key.startswith("_")}


class DevelopmentConfig(Config):
    """Development environment configuration with debug settings."""

    def _load_config(self):
        """Load base config then apply development overrides."""
        super()._load_config()

        # Development-specific overrides
        self.LOG_LEVEL = self._get_env("LOG_LEVEL", "DEBUG")
        self.ENABLE_DEBUG_LOGS = self._get_bool_env("ENABLE_DEBUG_LOGS", True)
        self.SKIP_ENTER_PROMPT = self._get_bool_env("SKIP_ENTER_PROMPT", True)
        self.AUTO_ASSUME_WEBSITE_READY = self._get_bool_env("AUTO_ASSUME_WEBSITE_READY", True)
        # Faster iteration in development
        self.KEEP_BROWSER_OPEN_DELAY = self._get_float_env("KEEP_BROWSER_OPEN_DELAY", 2.0)


class ProductionConfig(Config):
    """Production environment configuration with optimized settings."""

    def _load_config(self):
        """Load base config then apply production overrides."""
        super()._load_config()

        # Production-specific overrides
        self.LOG_LEVEL = self._get_env("LOG_LEVEL", "INFO")
        self.ENABLE_DEBUG_LOGS = self._get_bool_env("ENABLE_DEBUG_LOGS", False)
        self.AUTO_ASSUME_WEBSITE_READY = self._get_bool_env("AUTO_ASSUME_WEBSITE_READY", True)
        self.SKIP_ENTER_PROMPT = self._get_bool_env("SKIP_ENTER_PROMPT", True)


# ================================
# CONFIGURATION FACTORY
# ================================


def get_config() -> Config:
    """Get appropriate configuration based on environment.

    Returns:
        Configuration instance based on INFINITE_CRAFT_ENV environment
        variable
    """
    env = os.getenv("INFINITE_CRAFT_ENV", "default")

    if env == "development":
        return DevelopmentConfig()
    elif env == "production":
        return ProductionConfig()
    else:
        return Config()


# Global configuration instance
config = get_config()
