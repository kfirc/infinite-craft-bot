"""Interface for browser automation service."""

from abc import ABC, abstractmethod
from typing import Any, Dict, List

try:
    from selenium.webdriver.remote.webelement import WebElement
except ImportError:
    # Fallback for testing without selenium
    WebElement = object


class IBrowserService(ABC):
    """Interface for browser automation operations."""

    @abstractmethod
    def setup_driver(self) -> None:
        """Initialize the browser driver."""

    @abstractmethod
    def connect_to_existing_browser(self, port: int = 9222) -> bool:
        """Connect to existing browser instance."""

    @abstractmethod
    def load_game(self) -> bool:
        """Load the Infinite Craft game."""

    @abstractmethod
    def close(self) -> None:
        """Close browser and cleanup."""

    @abstractmethod
    def find_elements_by_css(self, selector: str) -> List[WebElement]:
        """Find elements using CSS selector."""

    @abstractmethod
    def execute_script(self, script: str, *args) -> Any:
        """Execute JavaScript in browser."""

    @abstractmethod
    def get_viewport_size(self) -> Dict[str, int]:
        """Get browser viewport dimensions."""
