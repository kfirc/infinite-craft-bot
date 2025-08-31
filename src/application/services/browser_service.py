"""Browser service implementation using Selenium."""

from typing import Dict, List, Optional

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from application.interfaces import IBrowserService, ILoggingService
from config import config


class BrowserService(IBrowserService):
    """
    Browser service implementation using Selenium WebDriver.

    Extracted from utils.py browser setup and management logic.
    Provides abstraction over Selenium for easier testing and potential driver switching.
    """

    def __init__(self, headless: bool = False, logging_service: ILoggingService = None):
        """
        Initialize browser service.

        Args:
            headless: Run browser in headless mode
            logging_service: Service for logging operations
        """
        self.headless = headless
        self.logger = logging_service
        self.driver = None

        # Browser configuration
        self._implicit_wait = config.IMPLICIT_WAIT_TIME
        self._explicit_wait = config.EXPLICIT_WAIT_TIME

    def setup_driver(self) -> None:
        """Initialize the browser driver."""
        try:
            self.logger.info("🚀 Setting up Chrome WebDriver...")

            # Setup Chrome options
            chrome_options = Options()
            chrome_options.add_argument("--no-first-run")
            chrome_options.add_argument("--no-default-browser-check")
            chrome_options.add_argument("--disable-extensions")
            chrome_options.add_argument("--disable-default-apps")

            if self.headless:
                chrome_options.add_argument("--headless")
                chrome_options.add_argument("--no-sandbox")
                chrome_options.add_argument("--disable-dev-shm-usage")

            # Initialize driver
            self.driver = webdriver.Chrome(options=chrome_options)
            self.driver.implicitly_wait(self._implicit_wait)

            self.logger.info("✅ Chrome WebDriver initialized")

        except Exception as e:
            self.logger.error(f"❌ Failed to setup Chrome WebDriver: {e}")
            raise

    def connect_to_existing_browser(self, port: int = None) -> bool:
        """
        Connect to existing browser instance with remote debugging.

        Args:
            port: Debug port (uses config default if None)

        Returns:
            True if connection successful, False otherwise
        """
        if port is None:
            port = config.CHROME_DEBUG_PORT

        try:
            self.logger.info(f"🔗 Connecting to existing Chrome on port {port}...")

            chrome_options = Options()
            chrome_options.add_experimental_option("debuggerAddress", f"localhost:{port}")

            self.driver = webdriver.Chrome(options=chrome_options)
            self.driver.implicitly_wait(self._implicit_wait)

            # Verify connection by checking current URL
            current_url = self.driver.current_url
            self.logger.info(f"✅ Connected to Chrome - Current URL: {current_url}")

            return True

        except Exception as e:
            self.logger.error(f"❌ Failed to connect to existing Chrome: {e}")
            return False

    def load_game(self) -> bool:
        """
        Load the Infinite Craft game.

        Returns:
            True if game loaded successfully, False otherwise
        """
        try:
            game_url = "https://neal.fun/infinite-craft/"
            self.logger.info(f"🎮 Loading game from {game_url}")

            self.driver.get(game_url)

            # Wait for game elements to load
            wait = WebDriverWait(self.driver, self._explicit_wait)

            # Wait for sidebar to be present
            wait.until(EC.presence_of_element_located((By.ID, "sidebar")))

            # Wait for initial elements to load
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "#sidebar .item")))

            self.logger.info("✅ Game loaded successfully")
            return True

        except Exception as e:
            self.logger.error(f"❌ Failed to load game: {e}")
            return False

    def close(self) -> None:
        """Close browser and cleanup."""
        if self.driver:
            try:
                self.logger.info("🔚 Closing browser...")
                self.driver.quit()
                self.driver = None
                self.logger.info("✅ Browser closed")
            except Exception as e:
                self.logger.error(f"❌ Error closing browser: {e}")

    def find_elements_by_css(self, selector: str) -> List[WebElement]:
        """
        Find elements using CSS selector.

        Args:
            selector: CSS selector string

        Returns:
            List of WebElements
        """
        if not self.driver:
            raise RuntimeError("Browser driver not initialized")

        return self.driver.find_elements(By.CSS_SELECTOR, selector)

    def execute_script(self, script: str, *args) -> any:
        """
        Execute JavaScript in browser.

        Args:
            script: JavaScript code to execute
            *args: Arguments to pass to script

        Returns:
            Result of script execution
        """
        if not self.driver:
            raise RuntimeError("Browser driver not initialized")

        return self.driver.execute_script(script, *args)

    def get_viewport_size(self) -> Dict[str, int]:
        """
        Get browser viewport dimensions.

        Returns:
            Dictionary with 'width' and 'height' keys
        """
        if not self.driver:
            raise RuntimeError("Browser driver not initialized")

        return self.driver.execute_script(
            """
            return {
                width: window.innerWidth,
                height: window.innerHeight
            };
        """
        )

    def wait_for_element(self, selector: str, timeout: float = None) -> Optional[WebElement]:
        """
        Wait for element to be present and return it.

        Args:
            selector: CSS selector
            timeout: Wait timeout (uses default if None)

        Returns:
            WebElement if found, None if timeout
        """
        if timeout is None:
            timeout = self._explicit_wait

        try:
            wait = WebDriverWait(self.driver, timeout)
            return wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, selector)))
        except Exception:
            return None

    def is_element_visible(self, element: WebElement) -> bool:
        """Check if element is visible on page."""
        try:
            return element.is_displayed()
        except Exception:
            return False

    def scroll_to_element(self, element: WebElement) -> None:
        """Scroll element into view."""
        if not self.driver:
            raise RuntimeError("Browser driver not initialized")

        self.driver.execute_script(
            """
            arguments[0].scrollIntoView({
                behavior: 'instant',
                block: 'center',
                inline: 'center'
            });
        """,
            element,
        )

    # Property to maintain compatibility with existing code
    @property
    def current_url(self) -> str:
        """Get current browser URL."""
        if not self.driver:
            return ""
        return self.driver.current_url
