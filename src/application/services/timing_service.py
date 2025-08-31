"""
Timing Service for Infinite Craft Automation.

Centralizes all timing-related operations and delays based on global configuration.
All timing values come from config.py to ensure consistency and configurability.
"""

import time
from typing import Optional

from application.interfaces import ILoggingService
from config import config


class TimingService:
    """
    Service that handles all timing and delay operations.

    Extracted from hardcoded time.sleep() calls throughout the codebase.
    All timing values now come from global configuration.
    """

    def __init__(self, logging_service: ILoggingService):
        """
        Initialize timing service.

        Args:
            logging_service: Service for logging timing operations
        """
        self.logger = logging_service

    def wait_for_combination_processing(self) -> None:
        """Wait for combination processing to complete."""
        self.logger.debug(f"⏱️ Waiting {config.COMBINATION_PROCESSING_DELAY}s for combination processing")
        time.sleep(config.COMBINATION_PROCESSING_DELAY)

    def wait_for_scroll_completion(self) -> None:
        """Wait for scroll operation to complete."""
        self.logger.debug(f"⏱️ Waiting {config.SCROLL_COMPLETION_DELAY}s for scroll completion")
        time.sleep(config.SCROLL_COMPLETION_DELAY)

    def wait_for_combination_result(self) -> None:
        """Wait for combination result to appear."""
        self.logger.debug(f"⏱️ Waiting {config.COMBINATION_RESULT_DELAY}s for combination result")
        time.sleep(config.COMBINATION_RESULT_DELAY)

    def wait_for_chrome_tab_switch(self) -> None:
        """Wait for Chrome tab switch to complete."""
        self.logger.debug(f"⏱️ Waiting {config.CHROME_TAB_SWITCH_DELAY}s for Chrome tab switch")
        time.sleep(config.CHROME_TAB_SWITCH_DELAY)

    def wait_for_dialog_close(self) -> None:
        """Wait for dialog to close."""
        self.logger.debug(f"⏱️ Waiting {config.DIALOG_CLOSE_DELAY}s for dialog close")
        time.sleep(config.DIALOG_CLOSE_DELAY)

    def wait_for_menu_operation(self) -> None:
        """Wait for menu operation to complete."""
        self.logger.debug(f"⏱️ Waiting {config.MENU_OPERATION_DELAY}s for menu operation")
        time.sleep(config.MENU_OPERATION_DELAY)

    def wait_for_save_operation(self) -> None:
        """Wait for save operation to complete."""
        self.logger.debug(f"⏱️ Waiting {config.SAVE_OPERATION_DELAY}s for save operation")
        time.sleep(config.SAVE_OPERATION_DELAY)

    def wait_for_merge(self, max_wait_time: Optional[float] = None) -> None:
        """
        Wait for element merge to complete.

        Args:
            max_wait_time: Maximum time to wait (uses config default if None)
        """
        wait_time = max_wait_time or config.MERGE_MAX_WAIT_TIME
        self.logger.debug(f"⏱️ Waiting {wait_time}s for merge completion")
        time.sleep(wait_time)

    def wait_for_element_appearance(self, max_wait_time: Optional[float] = None) -> None:
        """
        Wait for element to appear.

        Args:
            max_wait_time: Maximum time to wait (uses config default if None)
        """
        wait_time = max_wait_time or config.ELEMENT_APPEARANCE_MAX_WAIT
        self.logger.debug(f"⏱️ Waiting {wait_time}s for element appearance")
        time.sleep(wait_time)

    def poll_interval(self) -> None:
        """Wait for one polling interval."""
        time.sleep(config.POLL_INTERVAL)

    def drag_hold_pause(self) -> None:
        """Pause during drag operations for realism."""
        time.sleep(config.DRAG_HOLD_DURATION)

    def custom_delay(self, seconds: float, description: str = "") -> None:
        """
        Custom delay with optional description.

        Args:
            seconds: Number of seconds to wait
            description: Optional description for logging
        """
        if description:
            self.logger.debug(f"⏱️ Custom delay: {description} ({seconds}s)")
        time.sleep(seconds)
