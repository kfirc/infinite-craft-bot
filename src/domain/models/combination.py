"""Domain model for element combinations."""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional

from .element import Element


class CombinationStatus(Enum):
    """Status of a combination attempt."""

    PENDING = "pending"  # Not yet attempted
    SUCCESS = "success"  # Successful combination with new element
    NO_RESULT = "no_result"  # Successfully attempted but no new element
    DRAG_FAILED = "drag_failed"  # Failed to drag elements to workspace
    TIMEOUT = "timeout"  # Combination attempt timed out
    ERROR = "error"  # Error during combination


@dataclass(frozen=True)
class Combination:
    """
    Domain model representing an element combination.

    Tracks two elements being combined and the result.
    Immutable to ensure data consistency.
    """

    element1: Element
    element2: Element
    attempted_at: Optional[datetime] = None

    def __post_init__(self):
        """Validate combination on creation."""
        if self.element1 == self.element2:
            raise ValueError("Cannot combine element with itself")

        # Auto-set attempt time if not provided
        if self.attempted_at is None:
            object.__setattr__(self, "attempted_at", datetime.now())

    @property
    def cache_key(self) -> str:
        """Get normalized cache key for this combination."""
        # Always sort elements for consistent caching
        names = sorted([self.element1.cache_key, self.element2.cache_key])
        return "+".join(names)

    @property
    def display_name(self) -> str:
        """Get human-readable combination name."""
        return f"{self.element1.name} + {self.element2.name}"

    def get_other_element(self, element: Element) -> Element:
        """Get the other element in this combination."""
        if element == self.element1:
            return self.element2
        elif element == self.element2:
            return self.element1
        else:
            raise ValueError(f"Element {element.name} is not part of this combination")

    def contains_element(self, element: Element) -> bool:
        """Check if combination contains a specific element."""
        return element in (self.element1, self.element2)

    def contains_element_name(self, element_name: str) -> bool:
        """Check if combination contains an element with given name."""
        name_key = element_name.lower().strip()
        return self.element1.cache_key == name_key or self.element2.cache_key == name_key


@dataclass(frozen=True)
class CombinationResult:
    """
    Result of attempting a combination.

    Captures the outcome and any element that was created.
    """

    combination: Combination
    status: CombinationStatus
    result_element: Optional[Element] = None
    error_message: Optional[str] = None
    completed_at: Optional[datetime] = None

    def __post_init__(self):
        """Validate result on creation."""
        # Auto-set completion time if not provided
        if self.completed_at is None:
            object.__setattr__(self, "completed_at", datetime.now())

        # Validate status consistency
        if self.status == CombinationStatus.SUCCESS and self.result_element is None:
            raise ValueError("Success status requires a result element")

        if self.status != CombinationStatus.SUCCESS and self.result_element is not None:
            raise ValueError("Non-success status cannot have a result element")

        if self.status == CombinationStatus.ERROR and not self.error_message:
            raise ValueError("Error status requires an error message")

    @property
    def is_successful(self) -> bool:
        """Check if combination was successful."""
        return self.status == CombinationStatus.SUCCESS

    @property
    def should_retry(self) -> bool:
        """Check if combination should be retried."""
        return self.status in (CombinationStatus.DRAG_FAILED, CombinationStatus.TIMEOUT, CombinationStatus.ERROR)

    @property
    def was_attempted(self) -> bool:
        """Check if combination was actually attempted (not just failed to start)."""
        return self.status != CombinationStatus.DRAG_FAILED

    def get_cache_value(self) -> Optional[dict]:
        """Get dictionary representation for caching."""
        if self.is_successful:
            return self.result_element.to_dict()
        return None

    @classmethod
    def success(cls, combination: Combination, result_element: Element) -> "CombinationResult":
        """Create a successful combination result."""
        return cls(combination=combination, status=CombinationStatus.SUCCESS, result_element=result_element)

    @classmethod
    def no_result(cls, combination: Combination) -> "CombinationResult":
        """Create a no-result combination result."""
        return cls(combination=combination, status=CombinationStatus.NO_RESULT)

    @classmethod
    def drag_failed(cls, combination: Combination, error: str = None) -> "CombinationResult":
        """Create a drag-failed combination result."""
        return cls(combination=combination, status=CombinationStatus.DRAG_FAILED, error_message=error)

    @classmethod
    def error(cls, combination: Combination, error: str) -> "CombinationResult":
        """Create an error combination result."""
        return cls(combination=combination, status=CombinationStatus.ERROR, error_message=error)
