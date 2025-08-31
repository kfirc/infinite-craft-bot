"""Service for workspace management and element positioning."""

from typing import Dict, List

from application.interfaces import IBrowserService, ILoggingService
from domain.models import Element, ElementPosition, PositionedElement, Workspace
from domain.services import GameMechanics


class WorkspaceService:
    """
    Service for managing workspace elements and locations.

    Extracted from utils.py workspace management logic:
    - _get_workspace_elements()
    - find_workspace_elements()
    - _get_next_workspace_location()
    - _should_clear_workspace()
    - clear_workspace_tracking()
    - workspace_elements tracking
    """

    def __init__(self, browser_service: IBrowserService, logging_service: ILoggingService):
        """
        Initialize workspace service.

        Args:
            browser_service: Service for browser operations
            logging_service: Service for logging
        """
        self.browser = browser_service
        self.logger = logging_service

        # Initialize workspace domain model
        self.workspace = Workspace()

        # Statistics tracking (matches original utils.py)
        self.attempts_since_last_clear = 0

    def get_workspace_elements(self) -> List[PositionedElement]:
        """
        Get all current elements in the workspace that are visible to the user.

        Returns:
            List of PositionedElement domain models
        """
        try:
            # Use JavaScript to query workspace elements (matches original approach)
            workspace_data = self.browser.execute_script(
                """
                // Look for workspace container
                var workspace = document.querySelector('#instances, .instances, [class*="instances"]');
                if (!workspace) {
                    // Fallback: look for any container with elements
                    workspace = document.querySelector('#app, .app, main');
                }

                if (!workspace) return [];

                // Look for instance elements in workspace
                var items = workspace.querySelectorAll('.instance, .item[data-item-id]');
                var elements = [];

                items.forEach(function(item, index) {
                    var rect = item.getBoundingClientRect();
                    var text = item.textContent || item.innerText || '';
                    var emoji = item.getAttribute('data-emoji') || '';
                    var id = item.getAttribute('data-item-id') || 'workspace_' + index;

                    // Only include elements in reasonable workspace area
                    if (rect.left >= 200 && rect.left <= 1000 &&
                        rect.top >= 200 && rect.top <= 400 && text.trim()) {
                        elements.push({
                            name: text.trim(),
                            emoji: emoji,
                            id: id,
                            x: Math.round(rect.left + rect.width / 2),
                            y: Math.round(rect.top + rect.height / 2),
                            width: rect.width,
                            height: rect.height
                        });
                    }
                });

                return elements;
            """
            )

            # Convert to domain models
            positioned_elements = []
            for elem_data in workspace_data:
                try:
                    element = Element(name=elem_data["name"], emoji=elem_data["emoji"], element_id=elem_data["id"])

                    position = ElementPosition(elem_data["x"], elem_data["y"])
                    positioned_element = element.with_position(position)
                    positioned_elements.append(positioned_element)

                except Exception as e:
                    self.logger.debug(f"❌ Failed to create element from data {elem_data}: {e}")
                    continue

            # Update internal workspace
            self.workspace.elements = positioned_elements

            self.logger.debug(f"📊 Found {len(positioned_elements)} elements in workspace")
            return positioned_elements

        except Exception as e:
            self.logger.error(f"❌ Failed to get workspace elements: {e}")
            return []

    def get_next_workspace_location(self) -> ElementPosition:
        """
        Get the next workspace location using round-robin through predefined positions.

        Returns:
            ElementPosition for next location
        """
        location = self.workspace.get_next_location()

        self.logger.debug(
            f"📍 Next workspace location: {location.name} at ({location.position.x}, {location.position.y})"
        )
        return location.position

    def is_location_empty(self, position: ElementPosition) -> bool:
        """
        Check if a workspace location is empty (no elements at that position).

        Args:
            position: Position to check

        Returns:
            True if location is empty, False if occupied
        """
        from config import config

        tolerance = config.ELEMENT_POSITION_TOLERANCE

        for positioned_element in self.workspace.elements:
            # Check if any existing element is too close to this position
            distance = abs(positioned_element.position.x - position.x) + abs(positioned_element.position.y - position.y)
            if distance < tolerance:
                self.logger.debug(
                    f"🚫 Location ({position.x}, {position.y}) occupied by {positioned_element.element.display_name}"
                )
                return False

        self.logger.debug(f"✅ Location ({position.x}, {position.y}) is empty")
        return True

    def should_clear_workspace(self) -> bool:
        """
        Determine if workspace should be cleared based on element count and attempts.

        Returns:
            True if workspace should be cleared
        """
        current_count = len(self.workspace.elements)
        max_elements = GameMechanics.MAX_ELEMENTS_BEFORE_CLEAR

        should_clear = GameMechanics.should_clear_workspace(current_count)

        if should_clear:
            self.logger.debug(f"🧹 Workspace should be cleared: {current_count}/{max_elements} elements")

        return should_clear

    def clear_workspace_tracking(self) -> int:
        """
        Clear tracked workspace elements and reset location index.

        Returns:
            Number of elements that were cleared
        """
        cleared_count = self.workspace.clear()
        self.attempts_since_last_clear = 0

        self.logger.info(f"🧹 Cleared workspace element tracking - {cleared_count} elements removed")
        return cleared_count

    def clear_workspace(self) -> bool:
        """
        Clear all elements from the actual browser workspace using the clear tool-icon button.
        This is the REAL workspace clearing that removes elements from the browser.

        Returns:
            bool: True if workspace was cleared successfully
        """
        try:
            import time

            from selenium.webdriver.common.action_chains import ActionChains
            from selenium.webdriver.common.by import By

            from config import config

            self.logger.debug("🧹 Clearing browser workspace...")

            # Method 1: Use the clear tool-icon (PROVEN WORKING in original utils.py!)
            try:
                clear_icon = self.browser.driver.find_element(By.CSS_SELECTOR, ".clear.tool-icon")
                clear_icon.click()

                # Wait briefly for confirmation dialog
                time.sleep(config.DIALOG_CLOSE_DELAY)

                # Find and click Yes button
                yes_buttons = self.browser.driver.find_elements(By.XPATH, '//*[contains(text(), "Yes")]')
                for btn in yes_buttons:
                    if btn.is_displayed():
                        btn.click()
                        self.logger.debug("✅ Browser workspace cleared successfully")

                        # Also clear our tracking after successful browser clear
                        tracking_cleared = self.clear_workspace_tracking()
                        self.logger.info(
                            f"🧹 REAL CLEAR: Browser workspace + {tracking_cleared} tracked elements cleared"
                        )
                        return True

                self.logger.warning("⚠️ Clear button clicked but no Yes confirmation found")
                # Still clear tracking even if confirmation not found
                self.clear_workspace_tracking()
                return True

            except Exception as clear_error:
                self.logger.warning(f"⚠️ Clear tool-icon method failed: {clear_error}")

            # Method 2: Fallback - try trash icon with ActionChains
            try:
                trash_icon = self.browser.driver.find_element(By.CSS_SELECTOR, ".trash-icon")

                # Use ActionChains to avoid click interception
                actions = ActionChains(self.browser.driver)
                actions.move_to_element(trash_icon).click().perform()

                time.sleep(config.DIALOG_CLOSE_DELAY)

                yes_buttons = self.browser.driver.find_elements(By.XPATH, '//*[contains(text(), "Yes")]')
                for btn in yes_buttons:
                    if btn.is_displayed():
                        btn.click()
                        self.logger.debug("✅ Browser workspace cleared via trash icon")

                        # Also clear our tracking after successful browser clear
                        tracking_cleared = self.clear_workspace_tracking()
                        self.logger.info(
                            f"🧹 REAL CLEAR: Browser workspace + {tracking_cleared} tracked elements cleared"
                        )
                        return True

                self.logger.warning("⚠️ Trash icon clicked but no Yes confirmation found")
                # Still clear tracking even if confirmation not found
                self.clear_workspace_tracking()
                return True

            except Exception as trash_error:
                self.logger.warning(f"⚠️ Trash icon method failed: {trash_error}")

            # If both methods failed, still clear tracking
            tracking_cleared = self.clear_workspace_tracking()
            self.logger.warning(f"⚠️ Browser clear failed, but cleared {tracking_cleared} tracked elements")
            return False

        except Exception as e:
            self.logger.error(f"❌ Workspace clear failed completely: {e}")
            return False

    def add_element_to_workspace(self, element: Element, position: ElementPosition) -> PositionedElement:
        """
        Add an element to workspace tracking at specific position.

        Args:
            element: Element to add
            position: Position where element was placed

        Returns:
            PositionedElement that was added
        """
        positioned_element = self.workspace.add_element(element, position)

        self.logger.debug(f"📍 Added {element.display_name} to workspace at ({position.x}, {position.y})")
        return positioned_element

    def remove_element_from_workspace(self, element: Element) -> bool:
        """
        Remove an element from workspace tracking.

        Args:
            element: Element to remove

        Returns:
            True if element was removed, False if not found
        """
        removed = self.workspace.remove_element(element)

        if removed:
            self.logger.debug(f"📍 Removed {element.display_name} from workspace")
        else:
            self.logger.debug(f"❌ Element {element.display_name} not found in workspace")

        return removed

    def find_elements_near_position(
        self, target_position: ElementPosition, tolerance: int = None
    ) -> List[PositionedElement]:
        """
        Find elements within tolerance distance of target location.

        Args:
            target_position: Position to search around
            tolerance: Distance tolerance (uses game mechanics default if None)

        Returns:
            List of elements within tolerance
        """
        if tolerance is None:
            tolerance = GameMechanics.ELEMENT_POSITION_TOLERANCE

        near_elements = self.workspace.find_elements_near_position(target_position, tolerance)

        self.logger.debug(
            f"🔍 Found {len(near_elements)} elements within {tolerance}px of "
            f"({target_position.x}, {target_position.y})"
        )

        return near_elements

    def get_workspace_summary(self) -> Dict:
        """
        Get summary of workspace state for logging/debugging.

        Returns:
            Dictionary with workspace statistics and element info
        """
        summary = self.workspace.get_workspace_summary()
        summary["attempts_since_last_clear"] = self.attempts_since_last_clear

        return summary

    def increment_attempt_counter(self) -> None:
        """Increment the attempt counter (for clear timing)."""
        self.attempts_since_last_clear += 1

    def wait_for_element_to_appear(
        self, initial_workspace: List[PositionedElement], element_name: str, max_wait: float = None
    ) -> List[PositionedElement]:
        """
        Wait for a specific element to appear in workspace after drag.

        Args:
            initial_workspace: Workspace state before drag
            element_name: Name of element expected to appear
            max_wait: Maximum wait time (uses game mechanics default if None)

        Returns:
            Updated workspace elements list
        """
        if max_wait is None:
            max_wait = GameMechanics.get_element_appearance_timeout()

        import time

        start_time = time.time()
        poll_interval = GameMechanics.POLL_INTERVAL

        self.logger.debug(f"⏰ Waiting up to {max_wait}s for '{element_name}' to appear in workspace")

        while (time.time() - start_time) < max_wait:
            current_workspace = self.get_workspace_elements()

            # Check if workspace changed (element appeared)
            if len(current_workspace) != len(initial_workspace):
                self.logger.debug(f"✅ Workspace changed: {len(initial_workspace)} → {len(current_workspace)} elements")
                return current_workspace

            # Check if specific element appeared
            for elem in current_workspace:
                if element_name.lower() in elem.element.name.lower():
                    self.logger.debug(f"✅ Target element '{element_name}' appeared in workspace")
                    return current_workspace

            time.sleep(poll_interval)

        # Timeout - return current state anyway
        final_workspace = self.get_workspace_elements()
        elapsed = time.time() - start_time
        self.logger.debug(f"⏰ Element wait timeout after {elapsed:.3f}s - returning current workspace")

        return final_workspace

    def has_element_in_workspace(self, element_name: str) -> bool:
        """Check if workspace contains an element with given name."""
        return self.workspace.has_element_named(element_name)

    def get_workspace_element_names(self) -> List[str]:
        """Get list of all element names currently in workspace."""
        return self.workspace.get_elements_by_name()
