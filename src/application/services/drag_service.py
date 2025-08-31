"""Service for handling drag operations in the game."""

import time
from typing import Tuple

from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.remote.webelement import WebElement

from application.interfaces import IBrowserService, ILoggingService
from domain.models import ElementPosition
from domain.services import GameMechanics


class DragService:
    """
    Service for drag operations extracted from utils.py.

    Handles:
    - smooth_drag_element() - Optimized drag with multiple steps
    - drag_element_to_workspace() - Drag from sidebar to workspace
    - Coordinate validation and bounds checking
    """

    def __init__(self, browser_service: IBrowserService, logging_service: ILoggingService):
        """
        Initialize drag service.

        Args:
            browser_service: Service for browser operations
            logging_service: Service for logging
        """
        self.browser = browser_service
        self.logger = logging_service

    def smooth_drag_element(self, source_element: WebElement, target_x: int, target_y: int, steps: int = None) -> bool:
        """
        Perform smooth drag operation with multiple steps.

        Extracted from utils.py smooth_drag_element method.
        Uses game mechanics for step calculation and timing.

        Args:
            source_element: Element to drag from
            target_x: Target X coordinate
            target_y: Target Y coordinate
            steps: Number of drag steps (auto-calculated if None)

        Returns:
            True if drag operation completed, False if failed
        """
        try:
            self.logger.debug("🎯 PRE-DRAG: Starting smooth drag operation")

            # Get fresh source position using getBoundingClientRect for consistency
            fresh_source_center = self.browser.execute_script(
                """
                const rect = arguments[0].getBoundingClientRect();
                return {
                    x: rect.left + rect.width / 2,
                    y: rect.top + rect.height / 2
                };
            """,
                source_element,
            )

            start_x = fresh_source_center["x"]
            start_y = fresh_source_center["y"]

            # Validate positions are within safe bounds
            start_pos = ElementPosition(int(start_x), int(start_y))
            target_pos = ElementPosition(target_x, target_y)

            if not GameMechanics.is_within_safe_bounds(target_pos):
                self.logger.warning(f"⚠️ Target position ({target_x}, {target_y}) outside safe bounds")
                return False

            # Calculate drag parameters
            distance = start_pos.distance_to(target_pos)
            if steps is None:
                steps = GameMechanics.calculate_drag_steps(distance)

            self.logger.debug(f"📍 COORDS: Start ({start_x:.0f},{start_y:.0f}) → Target ({target_x},{target_y})")
            self.logger.debug(f"📏 Distance: {distance:.1f}px, Steps: {steps}")

            # Log what element we're hovering (debugging info)
            try:
                hovered_element = self.browser.execute_script(
                    "return document.elementFromPoint(arguments[0], arguments[1]);", start_x, start_y
                )
                if hovered_element:
                    hover_info = self.browser.execute_script(
                        """
                        return {
                            tagName: arguments[0].tagName,
                            className: arguments[0].className || '',
                            textContent: (arguments[0].textContent || '').substring(0, 20)
                        };
                    """,
                        hovered_element,
                    )
                    self.logger.debug(f"🎯 HOVERED: {hover_info}")
            except Exception:
                pass  # Non-critical debugging info

            # Perform smooth drag with ActionChains
            action_chains = ActionChains(self.browser.driver)

            # Move to element and hold
            action_chains.move_to_element(source_element)
            action_chains.click_and_hold()

            # Calculate step increments
            step_x = (target_x - start_x) / steps if steps > 0 else 0
            step_y = (target_y - start_y) / steps if steps > 0 else 0

            # Perform smooth movement
            for i in range(1, steps + 1):
                start_x + (step_x * i)
                start_y + (step_y * i)

                action_chains.move_by_offset(step_x, step_y)

                if i < steps:  # Don't pause after the final step
                    action_chains.pause(GameMechanics.DRAG_HOLD_DURATION)

            # Release at target
            action_chains.release()

            # Execute the action chain
            start_time = time.time()
            action_chains.perform()
            execution_time = time.time() - start_time

            self.logger.info(f"⚡ Fast drag completed in {execution_time:.3f}s")
            return True

        except Exception as e:
            self.logger.error(f"❌ Drag operation failed: {e}")
            return False

    def drag_element_to_workspace(
        self,
        element_name: str,
        workspace_x: int = 400,
        workspace_y: int = 300,
        element_detection_service=None,  # Will be injected
    ) -> bool:
        """
        Drag an element from sidebar to workspace.

        Args:
            element_name: Name of element to drag
            workspace_x: Target X coordinate in workspace
            workspace_y: Target Y coordinate in workspace
            element_detection_service: Service for finding elements

        Returns:
            True if drag was successful, False otherwise
        """
        if not element_detection_service:
            self.logger.error("❌ ElementDetectionService not provided")
            return False

        try:
            self.logger.debug(f"🎯 Dragging '{element_name}' to workspace ({workspace_x}, {workspace_y})")

            # Find element in sidebar
            source_element = element_detection_service.find_element_by_name(element_name)
            if not source_element:
                self.logger.warning(f"❌ Element '{element_name}' not found in sidebar")
                return False

            # Ensure element is visible and scrolled into view
            if not element_detection_service.ensure_element_visible(source_element):
                self.logger.warning(f"❌ Could not make element '{element_name}' visible")
                return False

            # Perform smooth drag to workspace
            success = self.smooth_drag_element(source_element, workspace_x, workspace_y)

            if success:
                self.logger.debug(f"✅ Successfully dragged '{element_name}' to workspace")
            else:
                self.logger.warning(f"❌ Failed to drag '{element_name}' to workspace")

            return success

        except Exception as e:
            self.logger.error(f"❌ Failed to drag element '{element_name}' to workspace: {e}")
            return False

    def calculate_drag_path(self, start: ElementPosition, end: ElementPosition, steps: int) -> list[Tuple[int, int]]:
        """
        Calculate intermediate points for smooth drag path.

        Args:
            start: Starting position
            end: Ending position
            steps: Number of intermediate steps

        Returns:
            List of (x, y) coordinates for drag path
        """
        if steps <= 0:
            return [(end.x, end.y)]

        path = []
        step_x = (end.x - start.x) / steps
        step_y = (end.y - start.y) / steps

        for i in range(1, steps + 1):
            x = int(start.x + (step_x * i))
            y = int(start.y + (step_y * i))
            path.append((x, y))

        return path

    def validate_drag_coordinates(self, start: ElementPosition, end: ElementPosition) -> bool:
        """
        Validate that drag coordinates are within safe bounds.

        Args:
            start: Starting position
            end: Ending position

        Returns:
            True if both positions are safe, False otherwise
        """
        if not GameMechanics.is_within_safe_bounds(start):
            self.logger.warning(f"❌ Start position ({start.x}, {start.y}) outside safe bounds")
            return False

        if not GameMechanics.is_within_safe_bounds(end):
            self.logger.warning(f"❌ End position ({end.x}, {end.y}) outside safe bounds")
            return False

        return True
