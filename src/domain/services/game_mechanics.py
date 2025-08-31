"""Pure game mechanics and rules - no external dependencies."""

from typing import List, Tuple

from ..models.element import Element, ElementPosition


class GameMechanics:
    """
    Pure game mechanics and rules.

    Contains all game-specific constants and rules extracted from utils.py.
    No external dependencies - only pure logic.
    """

    # Game timing constants (extracted from utils.py)
    MERGE_TIMEOUT = 2.0  # Elements merge within 2 seconds or never
    ELEMENT_APPEARANCE_MAX_WAIT = 2.0  # Max wait for element to appear after drag
    POLL_INTERVAL = 0.1  # Polling interval for state checks
    STABLE_CHECKS_REQUIRED = 3  # Number of stable checks before considering state final

    # Workspace constants (from utils.py predefined_locations)
    WORKSPACE_SAFE_BOUNDS = {"min_x": 200, "max_x": 1000, "min_y": 200, "max_y": 392}

    # Tolerance constants (from utils.py)
    MERGE_DISTANCE_TOLERANCE = 50  # Distance elements can be apart and still merge
    ELEMENT_POSITION_TOLERANCE = 60  # Tolerance for element position detection

    # Drag constants (from utils.py)
    DRAG_PIXEL_STEPS = 300  # Pixels per drag step
    DRAG_MAX_STEPS = 3  # Maximum drag steps for performance
    DRAG_HOLD_DURATION = 0.05  # Duration to hold during drag

    # Workspace management (from utils.py)
    MAX_ELEMENTS_BEFORE_CLEAR = 5  # Clear workspace after 5 attempts
    PREDEFINED_LOCATIONS = [
        (300, 250),  # Top left (safe zone)
        (700, 250),  # Top right (safe zone)
        (350, 350),  # Bottom left (safe zone)
        (650, 350),  # Bottom right (safe zone)
        (500, 300),  # Center (safe zone)
    ]

    # Basic starting elements
    BASIC_ELEMENTS = {"fire", "water", "earth", "wind", "air"}

    @classmethod
    def is_valid_combination(cls, elem1: Element, elem2: Element) -> bool:
        """
        Check if two elements can be combined.

        Args:
            elem1: First element
            elem2: Second element

        Returns:
            True if combination is valid, False otherwise
        """
        # Cannot combine element with itself
        if elem1 == elem2:
            return False

        # Cannot combine elements with same name (case-insensitive)
        if elem1.cache_key == elem2.cache_key:
            return False

        return True

    @classmethod
    def get_merge_timeout(cls) -> float:
        """Get the timeout for element merging."""
        return cls.MERGE_TIMEOUT

    @classmethod
    def get_element_appearance_timeout(cls) -> float:
        """Get timeout for element appearance after drag."""
        return cls.ELEMENT_APPEARANCE_MAX_WAIT

    @classmethod
    def is_within_safe_bounds(cls, position: ElementPosition) -> bool:
        """Check if position is within workspace safe bounds."""
        bounds = cls.WORKSPACE_SAFE_BOUNDS
        return bounds["min_x"] <= position.x <= bounds["max_x"] and bounds["min_y"] <= position.y <= bounds["max_y"]

    @classmethod
    def get_predefined_locations(cls) -> List[Tuple[int, int]]:
        """Get list of predefined safe workspace locations."""
        return cls.PREDEFINED_LOCATIONS.copy()

    @classmethod
    def is_basic_element(cls, element: Element) -> bool:
        """Check if element is one of the basic starting elements."""
        return element.cache_key in cls.BASIC_ELEMENTS

    @classmethod
    def calculate_drag_steps(cls, distance: float) -> int:
        """Calculate optimal number of drag steps based on distance."""
        steps = max(int(distance / cls.DRAG_PIXEL_STEPS), 1)
        return min(steps, cls.DRAG_MAX_STEPS)

    @classmethod
    def should_clear_workspace(cls, element_count: int) -> bool:
        """Determine if workspace should be cleared based on element count."""
        return element_count >= cls.MAX_ELEMENTS_BEFORE_CLEAR

    @classmethod
    def elements_can_merge(cls, pos1: ElementPosition, pos2: ElementPosition) -> bool:
        """Check if two elements at given positions can merge."""
        return pos1.is_within_tolerance(pos2, cls.MERGE_DISTANCE_TOLERANCE)

    @classmethod
    def is_element_positioned_correctly(cls, actual_pos: ElementPosition, target_pos: ElementPosition) -> bool:
        """Check if element is positioned within acceptable tolerance of target."""
        return actual_pos.is_within_tolerance(target_pos, cls.ELEMENT_POSITION_TOLERANCE)
