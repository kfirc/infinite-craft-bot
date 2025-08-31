"""Service for handling element combination testing logic."""

from typing import List, Optional

from application.interfaces import ILoggingService
from domain.models import Combination, CombinationResult, Element
from domain.services import GameMechanics


class CombinationService:
    """
    Service responsible for testing element combinations.

    This service coordinates the actual combination testing process:
    - Workspace location validation
    - Element positioning for merge
    - Merge detection and result evaluation

    Follows Clean Architecture - delegates to other services for specific operations.
    """

    def __init__(
        self,
        drag_service,  # DragService
        workspace_service,  # WorkspaceService
        element_service,  # ElementDetectionService
        logging_service: ILoggingService,
    ):
        """
        Initialize combination service with dependencies.

        Args:
            drag_service: Service for drag operations
            workspace_service: Service for workspace management
            element_service: Service for element detection
            logging_service: Service for logging
        """
        self.drag_handler = drag_service
        self.workspace_manager = workspace_service
        self.element_detector = element_service
        self.logger = logging_service

    def test_combination(
        self, combination: Combination, available_elements: List[Element]
    ) -> Optional[CombinationResult]:
        """
        Test a single element combination.

        This is the main combination testing logic extracted from AutomationOrchestrator.
        Coordinates the process but delegates specific operations to services.

        Args:
            combination: Combination to test
            available_elements: Currently available elements

        Returns:
            CombinationResult with outcome or None if failed
        """
        try:
            pass

            # IGNORE_CACHE only affects initial cache loading, not runtime behavior
            # Step 1: Get and validate workspace location
            target_location = self.workspace_manager.get_next_workspace_location()

            if not self.workspace_manager.is_location_empty(target_location):
                self.logger.warning(
                    f"❌ Target location ({
                        target_location.x}, {
                        target_location.y}) is not empty - invalidating combination"
                )
                return CombinationResult.error(combination, "Target location occupied")

            # Step 2: Record initial workspace state
            initial_workspace = self.workspace_manager.get_workspace_elements()

            # Step 3: Drag first element to workspace
            self.logger.info(f"🎯 Testing: {combination.display_name}")

            drag1_success = self.drag_handler.drag_element_to_workspace(
                combination.element1.name, target_location.x, target_location.y, self.element_detector
            )

            if not drag1_success:
                self.logger.warning(f"❌ Failed to drag {combination.element1.name} to workspace")
                return CombinationResult.drag_failed(combination, "First element drag failed")

            # Step 4: Wait and get first element's actual position
            import time

            time.sleep(0.5)  # Brief wait for element to appear

            workspace_after_first = self.workspace_manager.get_workspace_elements()

            merge_target_x, merge_target_y = self._find_first_element_position(
                initial_workspace, workspace_after_first, target_location, combination.element1.name
            )

            # Step 5: Drag second element ONTO first element

            drag2_success = self.drag_handler.drag_element_to_workspace(
                combination.element2.name, merge_target_x, merge_target_y, self.element_detector
            )

            if not drag2_success:
                self.logger.warning(f"❌ Failed to drag {combination.element2.name} to workspace")
                return CombinationResult.drag_failed(combination, "Second element drag failed")

            # Step 6: Wait for merge and detect results
            time.sleep(GameMechanics.get_merge_timeout())

            return self._evaluate_combination_result(combination, available_elements)

        except Exception as e:
            self.logger.error(f"❌ Combination testing failed: {e}")
            return CombinationResult.error(combination, str(e))

    def _find_first_element_position(
        self, initial_workspace: List, workspace_after_first: List, target_location, element1_name: str
    ) -> tuple:
        """
        Find the actual position where the first element landed.

        Args:
            initial_workspace: Workspace before first drag
            workspace_after_first: Workspace after first drag
            target_location: Original target location
            element1_name: Name of first element

        Returns:
            Tuple of (x, y) coordinates for merge target
        """
        merge_target_x, merge_target_y = target_location.x, target_location.y
        self.logger.debug(f"🎯 STEP 2: Initial merge target: ({merge_target_x}, {merge_target_y})")

        if len(workspace_after_first) > len(initial_workspace):
            self.logger.debug("🔍 More elements found after first drag - looking for first element's actual position")

            # Find the newest element by comparing names
            initial_names = {elem.element.display_name for elem in initial_workspace}
            newest_elements = [elem for elem in workspace_after_first if elem.element.display_name not in initial_names]

            if newest_elements:
                newest_element = newest_elements[0]
                merge_target_x = newest_element.position.x
                merge_target_y = newest_element.position.y
                self.logger.debug(
                    "🎯 FOUND 1ST ELEMENT: "
                    f"{newest_element.element.display_name} at ({merge_target_x}, {merge_target_y})"
                )
                self.logger.debug("🎯 Will drag 2nd element ONTO this position!")
            else:
                self.logger.debug(
                    f"🎯 No new elements by name comparison - using original target: "
                    f"({merge_target_x}, {merge_target_y})"
                )
        else:
            self.logger.debug(
                f"🎯 No new elements detected - using original target: ({merge_target_x}, {merge_target_y})"
            )

        return merge_target_x, merge_target_y

    def _evaluate_combination_result(
        self, combination: Combination, initial_elements: List[Element]
    ) -> CombinationResult:
        """
        Evaluate the result of a combination attempt.

        Args:
            combination: The combination that was tested
            initial_elements: Elements available before combination

        Returns:
            CombinationResult with appropriate status
        """
        # Check if new elements were discovered
        current_elements = self.element_detector.get_sidebar_elements()

        if len(current_elements) > len(initial_elements):
            # New element discovered - find it
            initial_names = {elem.display_name for elem in initial_elements}
            new_elements = [elem for elem in current_elements if elem.display_name not in initial_names]

            if new_elements:
                new_element = new_elements[0]  # Take the first new element
                self.logger.info(f"🎉 SUCCESS! {combination.display_name} → {new_element.display_name}")
                return CombinationResult.success(combination, new_element)

        # No new elements - combination attempted but no result
        self.logger.debug(f"⚪ No new elements: {combination.display_name} (combination attempted)")
        return CombinationResult.no_result(combination)
