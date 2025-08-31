"""Service for detecting and tracking elements in the game UI."""

from typing import Dict, List, Optional

from selenium.webdriver.remote.webelement import WebElement

from application.interfaces import IBrowserService, ILoggingService
from domain.models import Element, ElementSource


class ElementDetectionService:
    """
    Service for detecting elements in sidebar and managing element cache.

    Extracted from utils.py sidebar tracking logic:
    - get_sidebar_elements()
    - update_sidebar_cache()
    - _initialize_sidebar_tracking()
    - _find_element_by_name()
    - _ensure_element_visible()
    """

    def __init__(self, browser_service: IBrowserService, logging_service: ILoggingService):
        """
        Initialize element detection service.

        Args:
            browser_service: Service for browser operations
            logging_service: Service for logging
        """
        self.browser = browser_service
        self.logger = logging_service

        # Element tracking (migrated from utils.py)
        self.sidebar_elements: List[Element] = []
        self.sidebar_cache: Dict[str, Element] = {}  # Cache by element name (lowercase)

        # Tracking metadata
        self.last_update_count = 0

    def initialize_sidebar_tracking(self) -> bool:
        """Initialize sidebar element tracking and caching."""
        try:
            self.logger.info("🎯 Initializing sidebar element tracking...")

            # Get initial elements
            elements = self.get_sidebar_elements()

            if not elements:
                self.logger.warning("⚠️ No sidebar elements found during initialization")
                return False

            self.logger.info(f"✅ Sidebar tracking initialized - {len(elements)} elements found")
            return True

        except Exception as e:
            self.logger.error(f"❌ Failed to initialize sidebar tracking: {e}")
            return False

    def get_sidebar_elements(self) -> List[Element]:
        """
        Get all elements from sidebar with their details.

        Returns:
            List of Element domain models
        """
        try:
            element_web_objects = self.browser.find_elements_by_css("#sidebar .item")
            elements = []

            for index, elem_web in enumerate(element_web_objects):
                try:
                    # Extract element data using JavaScript (matches original utils.py approach)
                    element_data = self.browser.execute_script(
                        """
                        var elem = arguments[0];
                        return {
                            name: elem.textContent || elem.innerText || '',
                            emoji: elem.getAttribute('data-emoji') || '',
                            id: elem.getAttribute('data-item-id') || '',
                            dataItemText: elem.getAttribute('data-item-text') || '',
                            index: arguments[1],
                            discovered: elem.getAttribute('data-discovered') || null
                        };
                    """,
                        elem_web,
                        index,
                    )

                    # Create domain model with proper text cleaning
                    raw_name = element_data["name"] or ""
                    # Clean element name: remove newlines, extra spaces
                    clean_name = raw_name.replace("\n", " ").strip()

                    # Remove emoji and extra spaces more robustly
                    # Split by spaces and take only alphabetic words
                    words = []
                    for word in clean_name.split():
                        # Keep words that have alphabetic characters
                        if any(c.isalpha() for c in word):
                            # Remove leading/trailing non-alphabetic chars but keep internal ones
                            cleaned_word = word.strip(
                                "✈️🔥💧🌬️🌍🌱💨☁️🌧️⚡️🐊🪲🕯️🌫️☀️💩⛈️🌋🦟🦎🔪🦖🥘🌪️🌿🌈🦄🌊🪨🎭🎨🎪🎺🎻🎸🎤🎧🎮🎯🎲"
                                "🎳🎰🃏🎴🀄🎊🎉🎈🎁🎀🎗️🎟️🎫🎪⭐✨💫⚡🔥❄️☀️🌟💥💢💦💧🌊🌈☁️⛅⛈️🌤️🌦️🌧️⚆⚇⚈⚉" + " \t\n\r"
                            )
                            if cleaned_word and any(c.isalpha() for c in cleaned_word):
                                words.append(cleaned_word)

                    clean_name = " ".join(words) if words else clean_name

                    element = Element(
                        name=clean_name,
                        emoji=element_data["emoji"],
                        element_id=element_data["id"] or f"elem_{index}",
                        source=ElementSource.DISCOVERED,  # Default, could be enhanced
                        sidebar_index=index,
                    )

                    if element.name:  # Only add if has valid name
                        elements.append(element)

                except Exception as elem_error:
                    self.logger.debug(f"❌ Failed to process sidebar element {index}: {elem_error}")
                    continue

            # Update internal tracking
            self.sidebar_elements = elements
            self._update_sidebar_cache()

            self.logger.debug(f"📊 Detected {len(elements)} sidebar elements")
            return elements

        except Exception as e:
            self.logger.error(f"❌ Failed to get sidebar elements: {e}")
            return []

    def _update_sidebar_cache(self) -> None:
        """Update the sidebar cache with current elements."""
        self.sidebar_cache.clear()

        for element in self.sidebar_elements:
            self.sidebar_cache[element.cache_key] = element

        self.last_update_count = len(self.sidebar_elements)

    def update_sidebar_cache(self) -> bool:
        """
        Update sidebar cache by re-scanning elements.

        Returns:
            True if cache was updated, False if error occurred
        """
        try:
            old_count = len(self.sidebar_elements)

            # Re-scan sidebar
            current_elements = self.get_sidebar_elements()

            # Check for changes
            new_count = len(current_elements)
            if new_count != old_count:
                self.logger.debug(f"📊 Sidebar updated: {old_count} → {new_count} elements")
                return True
            else:
                self.logger.debug("📊 Sidebar unchanged")
                return True

        except Exception as e:
            self.logger.error(f"❌ Failed to update sidebar cache: {e}")
            return False

    def find_element_by_name(self, element_name: str) -> Optional[WebElement]:
        """
        Find a fresh WebElement by name from current sidebar DOM.

        Args:
            element_name: Name of element to find

        Returns:
            Fresh WebElement if found, None otherwise
        """
        try:
            # First check cache for quick lookup
            element = self.sidebar_cache.get(element_name.lower().strip())
            if not element:
                # Element not in cache, try updating cache first
                self.update_sidebar_cache()
                element = self.sidebar_cache.get(element_name.lower().strip())

            if not element:
                self.logger.debug(f"❌ Element '{element_name}' not found in sidebar cache")
                return None

            # Find fresh WebElement by text content (avoids stale element issues)
            sidebar_elements = self.browser.find_elements_by_css("#sidebar .item")

            for web_elem in sidebar_elements:
                try:
                    raw_text = web_elem.text.strip()
                    # Clean element text same way as in get_sidebar_elements
                    clean_text = raw_text.replace("\n", " ").strip()

                    # Remove emoji and extra spaces robustly - same logic as above
                    words = []
                    for word in clean_text.split():
                        if any(c.isalpha() for c in word):
                            cleaned_word = word.strip(
                                "✈️🔥💧🌬️🌍🌱💨☁️🌧️⚡️🐊🪲🕯️🌫️☀️💩⛈️🌋🦟🦎🔪🦖🥘🌪️🌿🌈🦄🌊🪨🎭🎨🎪🎺🎻🎸🎤🎧🎮🎯🎲"
                                "🎳🎰🃏🎴🀄🎊🎉🎈🎁🎀🎗️🎟️🎫🎪⭐✨💫⚡🔥❄️☀️🌟💥💢💦💧🌊🌈☁️⛅⛈️🌤️🌦️🌧️⚆⚇⚈⚉" + " \t\n\r"
                            )
                            if cleaned_word and any(c.isalpha() for c in cleaned_word):
                                words.append(cleaned_word)

                    clean_text = " ".join(words) if words else clean_text

                    if clean_text.lower() == element_name.lower():
                        return web_elem

                    # Try partial match if exact match fails
                    if element_name.lower() in clean_text.lower():
                        return web_elem

                except Exception:
                    continue

            self.logger.debug(f"❌ WebElement for '{element_name}' not found in DOM")
            return None

        except Exception as e:
            self.logger.error(f"❌ Failed to find element '{element_name}': {e}")
            return None

    def ensure_element_visible(self, element: WebElement) -> bool:
        """
        Ensure element is scrolled into view and clickable.

        Args:
            element: WebElement to make visible

        Returns:
            True if element is visible, False otherwise
        """
        try:
            # Get viewport info for bounds checking
            viewport = self.browser.get_viewport_size()

            # Scroll element into view
            self.browser.execute_script(
                """
                arguments[0].scrollIntoView({
                    behavior: 'instant',
                    block: 'center',
                    inline: 'center'
                });
            """,
                element,
            )

            # Check if element is within viewport bounds
            element_rect = self.browser.execute_script(
                """
                const rect = arguments[0].getBoundingClientRect();
                return {
                    x: rect.left,
                    y: rect.top,
                    width: rect.width,
                    height: rect.height,
                    right: rect.right,
                    bottom: rect.bottom
                };
            """,
                element,
            )

            # Validate bounds (matches original logic from utils.py)
            if (
                element_rect["x"] < 0
                or element_rect["y"] < 0
                or element_rect["right"] > viewport["width"]
                or element_rect["bottom"] > viewport["height"]
            ):

                self.logger.debug(f"⚠️ Element outside viewport: {element_rect}")
                return False

            self.logger.debug(f"✅ Element visible at ({element_rect['x']:.0f}, {element_rect['y']:.0f})")
            return True

        except Exception as e:
            self.logger.error(f"❌ Failed to ensure element visibility: {e}")
            return False

    def get_element_count(self) -> int:
        """Get current count of sidebar elements."""
        return len(self.sidebar_elements)

    def get_element_by_name(self, name: str) -> Optional[Element]:
        """Get domain model element by name from cache."""
        return self.sidebar_cache.get(name.lower().strip())

    def has_element(self, name: str) -> bool:
        """Check if element exists in sidebar."""
        return name.lower().strip() in self.sidebar_cache

    def get_all_element_names(self) -> List[str]:
        """Get list of all element names in sidebar."""
        return [elem.name for elem in self.sidebar_elements]

    def detect_new_elements(self, previous_elements: List[Element]) -> List[Element]:
        """
        Detect new elements by comparing with previous state.

        Args:
            previous_elements: Previous list of elements

        Returns:
            List of newly discovered elements
        """
        previous_names = {elem.cache_key for elem in previous_elements}
        current_elements = self.get_sidebar_elements()

        new_elements = []
        for element in current_elements:
            if element.cache_key not in previous_names:
                new_elements.append(element)

        if new_elements:
            self.logger.info(f"🆕 Discovered {len(new_elements)} new elements!")
            for elem in new_elements:
                self.logger.info(f"   🎉 {elem.display_name}")

        return new_elements
