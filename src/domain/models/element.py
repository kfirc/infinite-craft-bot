"""Domain model for game elements."""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional


class ElementSource(Enum):
    """Source where element was discovered."""

    INITIAL = "initial"  # Starting elements (Fire, Water, Earth, Wind)
    DISCOVERED = "discovered"  # Created through combination
    IMPORTED = "imported"  # Loaded from cache/save file


@dataclass(frozen=True)
class ElementPosition:
    """Represents an element's position in the game."""

    x: int
    y: int

    def distance_to(self, other: "ElementPosition") -> float:
        """Calculate distance to another position."""
        return ((self.x - other.x) ** 2 + (self.y - other.y) ** 2) ** 0.5

    def is_within_tolerance(self, other: "ElementPosition", tolerance: int) -> bool:
        """Check if position is within tolerance of another position."""
        return self.distance_to(other) <= tolerance


@dataclass(frozen=True)
class Element:
    """
    Domain model representing a game element.

    This is immutable to prevent accidental mutations and ensure data consistency.
    All element data should flow through this model rather than using raw dictionaries.
    """

    name: str
    emoji: str
    element_id: str
    source: ElementSource = ElementSource.DISCOVERED
    discovered_at: Optional[datetime] = None
    sidebar_index: Optional[int] = None

    def __post_init__(self):
        """Validate element data on creation."""
        if not self.name.strip():
            raise ValueError("Element name cannot be empty")

        if not self.element_id.strip():
            raise ValueError("Element ID cannot be empty")

        # Auto-set discovery time if not provided
        if self.discovered_at is None and self.source == ElementSource.DISCOVERED:
            object.__setattr__(self, "discovered_at", datetime.now())

    @property
    def display_name(self) -> str:
        """Get display name with emoji."""
        return f"{self.emoji} {self.name}" if self.emoji else self.name

    @property
    def cache_key(self) -> str:
        """Get normalized cache key for this element."""
        return self.name.lower().strip()

    def is_basic_element(self) -> bool:
        """Check if this is one of the four basic starting elements."""
        basic_elements = {"fire", "water", "earth", "wind", "air"}
        return self.cache_key in basic_elements

    def matches_name(self, name: str) -> bool:
        """Check if element matches a given name (case-insensitive)."""
        return self.cache_key == name.lower().strip()

    @classmethod
    def from_dict(cls, data: dict) -> "Element":
        """Create Element from dictionary (for migration compatibility)."""
        return cls(
            name=data.get("name", ""),
            emoji=data.get("emoji", ""),
            element_id=data.get("id", data.get("element_id", "")),
            source=ElementSource.DISCOVERED,  # Default for now
            discovered_at=datetime.fromisoformat(data["discovered_at"]) if data.get("discovered_at") else None,
            sidebar_index=data.get("index"),
        )

    def to_dict(self) -> dict:
        """Convert to dictionary (for backward compatibility during migration)."""
        return {
            "name": self.name,
            "emoji": self.emoji,
            "id": self.element_id,
            "element_id": self.element_id,  # Both for compatibility
            "source": self.source.value,
            "discovered_at": self.discovered_at.isoformat() if self.discovered_at else None,
            "index": self.sidebar_index,
        }

    def with_position(self, position: ElementPosition) -> "PositionedElement":
        """Create a positioned version of this element."""
        return PositionedElement(element=self, position=position)


@dataclass(frozen=True)
class PositionedElement:
    """An element with a specific position (used for workspace tracking)."""

    element: Element
    position: ElementPosition

    @property
    def name(self) -> str:
        """Delegate to element name for convenience."""
        return self.element.name

    @property
    def emoji(self) -> str:
        """Delegate to element emoji for convenience."""
        return self.element.emoji

    @property
    def display_name(self) -> str:
        """Delegate to element display name."""
        return self.element.display_name

    def distance_to_position(self, target_position: ElementPosition) -> float:
        """Calculate distance to a target position."""
        return self.position.distance_to(target_position)

    def is_near_position(self, target_position: ElementPosition, tolerance: int = 50) -> bool:
        """Check if element is near a target position."""
        return self.position.is_within_tolerance(target_position, tolerance)
