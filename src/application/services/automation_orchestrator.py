"""Service-oriented automation orchestrator - the new lightweight automation class."""

from datetime import datetime
from typing import Dict, List, Optional

from application.interfaces import IBrowserService, ICacheService, ILoggingService
from domain.models import Combination, CombinationResult, Element
from domain.services import GameMechanics

from .combination_service import CombinationService
from .drag_service import DragService
from .element_detection_service import ElementDetectionService
from .timing_service import TimingService
from .workspace_service import WorkspaceService


class AutomationOrchestrator:
    """
    Service-oriented automation orchestrator following Clean Architecture principles.

    RESPONSIBILITIES (Coordination Only):
    - Initialize and coordinate between services
    - Manage automation session state
    - Provide unified interface for automation operations

    WHAT IT DOESN'T DO (Delegated to Services):
    - Direct browser interaction (→ BrowserService)
    - Element detection logic (→ ElementDetectionService)
    - Workspace management (→ WorkspaceService)
    - Drag operations (→ DragService)
    - Combination testing logic (→ CombinationService)
    - Cache management (→ CacheService)

    This is a TRUE orchestrator - it coordinates but doesn't implement business logic.
    """

    def __init__(
        self,
        browser_service: IBrowserService,
        cache_service: ICacheService,
        logging_service: ILoggingService,
        headless: bool = False,
    ):
        """
        Initialize automation orchestrator with injected services.

        Args:
            browser_service: Service for browser operations
            cache_service: Service for combination caching
            logging_service: Service for logging
            headless: Run in headless mode
        """
        # Injected services (dependency injection)
        self.browser = browser_service
        self.cache = cache_service
        self.logger = logging_service

        # Initialize supporting services
        self.element_detector = ElementDetectionService(browser_service, logging_service)
        self.drag_handler = DragService(browser_service, logging_service)
        self.workspace_manager = WorkspaceService(browser_service, logging_service)
        self.timing = TimingService(logging_service)

        # Create combination service (coordinates combination testing)
        self.combination_service = CombinationService(
            self.drag_handler, self.workspace_manager, self.element_detector, logging_service
        )

        # Session tracking
        self.session_start = datetime.now()
        self.session_stats = {"combinations_attempted": 0, "elements_created": 0, "workspace_clears": 0}

    def initialize(self) -> bool:
        """
        Initialize the automation system.

        Returns:
            True if initialization successful, False otherwise
        """
        try:
            self.logger.info("🚀 Initializing service-oriented automation system...")

            # Initialize browser (if not already done)
            if not hasattr(self.browser, "driver") or not self.browser.driver:
                self.browser.setup_driver()

            # Initialize element detection
            if not self.element_detector.initialize_sidebar_tracking():
                self.logger.error("❌ Failed to initialize element detection")
                return False

            self.logger.info("✅ Automation orchestrator initialized successfully")
            return True

        except Exception as e:
            self.logger.error(f"❌ Failed to initialize automation orchestrator: {e}")
            return False

    def connect_to_game(self, port: int = 9222) -> bool:
        """
        Connect to existing game browser and initialize tracking.

        Args:
            port: Chrome debug port

        Returns:
            True if connected successfully
        """
        try:
            # Connect to browser
            if not self.browser.connect_to_existing_browser(port):
                return False

            # Initialize element tracking
            return self.initialize()

        except Exception as e:
            self.logger.error(f"❌ Failed to connect to game: {e}")
            return False

    def test_combination(self, element1_name: str, element2_name: str) -> Optional[CombinationResult]:
        """
        Test a combination of two elements.

        CLEAN ARCHITECTURE: This orchestrator method just coordinates services.
        The actual combination testing logic is delegated to CombinationService.

        Args:
            element1_name: Name of first element
            element2_name: Name of second element

        Returns:
            CombinationResult with outcome details
        """
        try:
            # Prepare combination domain model
            available_elements = self.element_detector.get_sidebar_elements()
            element1 = self._find_element_by_name(available_elements, element1_name)
            element2 = self._find_element_by_name(available_elements, element2_name)

            if not element1 or not element2:
                missing = element1_name if not element1 else element2_name
                self.logger.warning(f"❌ Element '{missing}' not found in sidebar")
                return None

            combination = Combination(element1, element2)

            # Check cache first (coordination responsibility) - unless IGNORE_CACHE is set
            from config import config

            if not config.IGNORE_CACHE:
                cached_result = self.cache.get_successful_result(combination)
                if cached_result:
                    result_exists = any(elem.display_name == cached_result.display_name for elem in available_elements)
                    if result_exists:
                        self.logger.debug(
                            f"⏭️ CACHED RESULT: {
                                combination.display_name} → {
                                cached_result.display_name}"
                        )
                        from domain.models import CombinationResult

                        return CombinationResult.success(combination, cached_result)
            else:
                self.logger.debug(f"🔄 IGNORE_CACHE enabled - forcing retest of {combination.display_name}")

            # DELEGATE to CombinationService (clean architecture)
            result = self.combination_service.test_combination(combination, available_elements)

            # Update session statistics and cache (coordination responsibilities)
            if result:
                self.session_stats["combinations_attempted"] += 1
                if result.is_successful:
                    self.session_stats["elements_created"] += 1

                # Cache the result
                self.cache.record_combination_result(result)

                # Check if workspace should be cleared (both browser and tracking)
                if self.workspace_manager.should_clear_workspace():
                    # Clear the actual browser workspace first
                    browser_cleared = self.workspace_manager.clear_workspace()
                    if browser_cleared:
                        self.logger.info("🧹 REAL CLEAR: Browser workspace cleared successfully")

                    # Then clear tracking
                    cleared_count = self.workspace_manager.clear_workspace_tracking()
                    self.session_stats["workspace_clears"] += 1

                    if browser_cleared:
                        self.logger.info(f"🧹 Full workspace clear: browser + {cleared_count} tracked elements")
                    else:
                        self.logger.warning(f"🧹 Partial clear: tracking only - {cleared_count} elements removed")

            return result

        except Exception as e:
            self.logger.error(f"❌ Failed to test combination {element1_name} + {element2_name}: {e}")
            return None

    def _find_element_by_name(self, available_elements: List[Element], element_name: str) -> Optional[Element]:
        """
        Find an element by name from the available elements list.

        Args:
            available_elements: List of available elements
            element_name: Name of element to find

        Returns:
            Element if found, None otherwise
        """
        for element in available_elements:
            if element.name == element_name or element.display_name == element_name:
                return element
        return None

    def _perform_combination_test(
        self, combination: Combination, available_elements: List[Element]
    ) -> Optional[CombinationResult]:
        """
        Perform the actual combination test with drag operations.

        Args:
            combination: Combination to test
            available_elements: Current available elements

        Returns:
            CombinationResult with outcome
        """
        try:
            # Get target location for combination (only need ONE location for merging)
            target_location = self.workspace_manager.get_next_workspace_location()

            # Validate that target location is empty before dragging
            if not self.workspace_manager.is_location_empty(target_location):
                self.logger.warning(
                    f"❌ Target location ({
                        target_location.x}, {
                        target_location.y}) is not empty - invalidating combination"
                )
                result = CombinationResult.error(combination, "Target location occupied")
                self.cache.record_combination_result(result)
                return result

            # Record initial workspace state for merge detection
            initial_elements = available_elements[:]
            initial_workspace = self.workspace_manager.get_workspace_elements()
            self.logger.debug(f"📊 Workspace before: {len(initial_workspace)} elements")

            # STEP 1: Drag first element to target location
            self.logger.info(
                f"🎯 STEP 1: Dragging {
                    combination.element1.name} to target location ({
                    target_location.x}, {
                    target_location.y})"
            )
            drag1_success = self.drag_handler.drag_element_to_workspace(
                combination.element1.name, target_location.x, target_location.y, self.element_detector
            )

            if not drag1_success:
                self.logger.warning(f"❌ Failed to drag {combination.element1.name} to workspace")
                result = CombinationResult.drag_failed(combination, "First element drag failed")
                self.cache.record_combination_result(result)
                return result

            # STEP 2: Wait for first element to appear and get its actual position
            import time

            time.sleep(0.5)  # Brief wait for element to appear
            workspace_after_first = self.workspace_manager.get_workspace_elements()
            self.logger.debug(f"📊 Workspace after 1st drag: {len(workspace_after_first)} elements")

            # Find the actual position of the first element for precise merging
            merge_target_x, merge_target_y = target_location.x, target_location.y
            self.logger.info(f"🎯 STEP 2: Initial merge target: ({merge_target_x}, {merge_target_y})")

            self.logger.info(f"📊 Initial workspace: {len(initial_workspace)} elements")
            self.logger.info(f"📊 After first drag: {len(workspace_after_first)} elements")

            if len(workspace_after_first) > len(initial_workspace):
                self.logger.info(
                    "🔍 More elements found after first drag - looking for first element's actual position"
                )

                # List all elements in workspace after first drag for debugging
                for i, elem in enumerate(workspace_after_first):
                    self.logger.info(f"  [{i}] {elem.element.display_name} at ({elem.position.x}, {elem.position.y})")

                # Find the newest element by comparing names (more reliable than object comparison)
                initial_names = {elem.element.display_name for elem in initial_workspace}
                newest_elements = [
                    elem for elem in workspace_after_first if elem.element.display_name not in initial_names
                ]

                if newest_elements:
                    newest_element = newest_elements[0]  # Take the first new element
                    merge_target_x = newest_element.position.x
                    merge_target_y = newest_element.position.y
                    self.logger.info(
                        "🎯 FOUND 1ST ELEMENT: "
                        f"{newest_element.element.display_name} at ({merge_target_x}, {merge_target_y})"
                    )
                    self.logger.info("🎯 Will drag 2nd element ONTO this position!")
                else:
                    self.logger.info(
                        "🎯 No new elements by name comparison - using original target: "
                        f"({merge_target_x}, {merge_target_y})"
                    )
            else:
                self.logger.info(
                    f"🎯 No new elements detected - using original target: ({merge_target_x}, {merge_target_y})"
                )

            # STEP 3: Drag second element DIRECTLY ONTO first element for merge
            self.logger.info(
                f"🎯 STEP 3: Dragging {
                    combination.element2.name} ONTO {
                    combination.element1.name} at ({merge_target_x}, {merge_target_y})"
            )
            self.logger.info(
                f"🎯 COORDINATES: First element at ({
                    target_location.x}, {
                    target_location.y}) -> Second element to ({merge_target_x}, {merge_target_y})"
            )
            drag2_success = self.drag_handler.drag_element_to_workspace(
                combination.element2.name, merge_target_x, merge_target_y, self.element_detector
            )

            if not drag2_success:
                self.logger.warning(f"❌ Failed to drag {combination.element2.name} to workspace")
                result = CombinationResult.drag_failed(combination, "Second element drag failed")
                self.cache.record_combination_result(result)
                return result

            # Wait for potential merge and check for new elements
            import time

            time.sleep(GameMechanics.get_merge_timeout())  # Wait for merge timeout

            # Check if new elements were discovered
            self.element_detector.get_sidebar_elements()
            new_elements = self.element_detector.detect_new_elements(initial_elements)

            if new_elements:
                # Success - new element created
                new_element = new_elements[0]  # Take first new element
                self.logger.info(f"🎉 SUCCESS! {combination.display_name} → {new_element.display_name}")

                result = CombinationResult.success(combination, new_element)
                self.cache.record_combination_result(result)
                return result
            else:
                # No new element, but drag was successful
                self.logger.info(f"⚪ No new elements: {combination.display_name} (combination attempted)")

                result = CombinationResult.no_result(combination)
                self.cache.record_combination_result(result)
                return result

        except Exception as e:
            self.logger.error(f"❌ Error during combination test: {e}")
            result = CombinationResult.error(combination, str(e))
            self.cache.record_combination_result(result)
            return result

    def get_session_stats(self) -> Dict:
        """Get statistics for current session."""
        cache_stats = self.cache.get_cache_stats()
        duration_minutes = (datetime.now() - self.session_start).total_seconds() / 60

        return {
            **self.session_stats,
            **cache_stats,
            "session_duration_minutes": round(duration_minutes, 2),
            "element_count": self.element_detector.get_element_count(),
            "workspace_elements": len(self.workspace_manager.get_workspace_elements()),
        }

    def get_available_elements(self) -> List[Element]:
        """Get list of currently available elements."""
        return self.element_detector.get_sidebar_elements()

    def get_untested_combinations(self) -> List[Combination]:
        """Get list of untested combinations."""
        available_elements = self.get_available_elements()
        return self.cache.get_untested_combinations(available_elements)

    def close(self) -> None:
        """Clean up and close automation system."""
        try:
            self.logger.info("🔚 Shutting down automation orchestrator...")

            # Log final session statistics
            stats = self.get_session_stats()
            self.logger.info(
                f"📊 Session Summary: {
                    stats['combinations_attempted']} combinations tested, {
                    stats['elements_created']} elements created"
            )

            # Close browser
            self.browser.close()

            self.logger.info("✅ Automation orchestrator shut down")

        except Exception as e:
            self.logger.error(f"❌ Error during shutdown: {e}")

    # Backward compatibility methods for gradual migration

    def combine_elements(self, element1_name: str, element2_name: str) -> Optional[str]:
        """Backward compatibility method that returns element name or None."""
        result = self.test_combination(element1_name, element2_name)

        if result and result.is_successful and result.result_element:
            return result.result_element.name
        return None
