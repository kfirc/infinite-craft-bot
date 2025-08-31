"""Domain model for game workspace."""

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional

from .element import Element, ElementPosition, PositionedElement


class WorkspaceState(Enum):
    """State of the workspace."""

    EMPTY = "empty"
    HAS_ELEMENTS = "has_elements"
    FULL = "full"
    CLEARING = "clearing"


@dataclass(frozen=True)
class WorkspaceLocation:
    """Predefined location in the workspace."""

    position: ElementPosition
    name: str
    is_safe: bool = True  # Whether this location is within safe bounds

    @classmethod
    def create_default_locations(cls) -> List["WorkspaceLocation"]:
        """Create the 5 predefined workspace locations from utils.py."""
        return [
            cls(ElementPosition(300, 250), "Top Left", True),
            cls(ElementPosition(700, 250), "Top Right", True),
            cls(ElementPosition(350, 350), "Bottom Left", True),
            cls(ElementPosition(650, 350), "Bottom Right", True),
            cls(ElementPosition(500, 300), "Center", True),
        ]


@dataclass
class Workspace:
    """
    Domain model representing the game workspace.

    Tracks elements currently in the workspace and manages location assignment.
    Mutable because workspace state changes frequently during automation.
    """

    elements: List[PositionedElement] = field(default_factory=list)
    predefined_locations: List[WorkspaceLocation] = field(default_factory=WorkspaceLocation.create_default_locations)
    current_location_index: int = 0
    max_elements_before_clear: int = 5

    @property
    def state(self) -> WorkspaceState:
        """Get current workspace state."""
        if not self.elements:
            return WorkspaceState.EMPTY
        elif len(self.elements) >= self.max_elements_before_clear:
            return WorkspaceState.FULL
        else:
            return WorkspaceState.HAS_ELEMENTS

    @property
    def element_count(self) -> int:
        """Get number of elements in workspace."""
        return len(self.elements)

    @property
    def is_empty(self) -> bool:
        """Check if workspace is empty."""
        return self.element_count == 0

    @property
    def is_full(self) -> bool:
        """Check if workspace should be cleared."""
        return self.element_count >= self.max_elements_before_clear

    def add_element(self, element: Element, position: ElementPosition) -> PositionedElement:
        """Add an element to the workspace at a specific position."""
        positioned_element = element.with_position(position)
        self.elements.append(positioned_element)
        return positioned_element

    def remove_element(self, element: Element) -> bool:
        """Remove an element from the workspace."""
        for i, positioned_elem in enumerate(self.elements):
            if positioned_elem.element == element:
                del self.elements[i]
                return True
        return False

    def find_element_by_name(self, name: str) -> Optional[PositionedElement]:
        """Find an element in workspace by name."""
        name_key = name.lower().strip()
        for positioned_elem in self.elements:
            if positioned_elem.element.cache_key == name_key:
                return positioned_elem
        return None

    def find_elements_near_position(
        self, target_position: ElementPosition, tolerance: int = 50
    ) -> List[PositionedElement]:
        """Find all elements within tolerance of a target position."""
        return [elem for elem in self.elements if elem.is_near_position(target_position, tolerance)]

    def get_next_location(self) -> WorkspaceLocation:
        """Get the next predefined location using round-robin."""
        location = self.predefined_locations[self.current_location_index]
        self.current_location_index = (self.current_location_index + 1) % len(self.predefined_locations)
        return location

    def clear(self) -> int:
        """Clear all elements from workspace and return count of removed elements."""
        count = len(self.elements)
        self.elements.clear()
        self.current_location_index = 0  # Reset location index
        return count

    def get_elements_by_name(self) -> List[str]:
        """Get list of element names currently in workspace."""
        return [elem.element.name for elem in self.elements]

    def has_element(self, element: Element) -> bool:
        """Check if workspace contains a specific element."""
        return any(positioned.element == element for positioned in self.elements)

    def has_element_named(self, name: str) -> bool:
        """Check if workspace contains an element with given name."""
        return self.find_element_by_name(name) is not None

    def get_workspace_summary(self) -> dict:
        """Get summary of workspace state for logging/debugging."""
        return {
            "element_count": self.element_count,
            "state": self.state.value,
            "elements": [elem.element.display_name for elem in self.elements],
            "current_location_index": self.current_location_index,
            "is_full": self.is_full,
        }
