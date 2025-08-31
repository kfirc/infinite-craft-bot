"""Interface for cache service."""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional

from domain.models import Combination, CombinationResult, Element


class ICacheService(ABC):
    """Interface for combination caching operations."""

    @abstractmethod
    def load_cache_from_file(self, file_path: str) -> None:
        """Load combination cache from file."""

    @abstractmethod
    def save_cache_to_file(self, file_path: str) -> None:
        """Save combination cache to file."""

    @abstractmethod
    def is_combination_tested(self, combination: Combination) -> bool:
        """Check if combination has been tested."""

    @abstractmethod
    def is_combination_successful(self, combination: Combination) -> bool:
        """Check if combination is known to be successful."""

    @abstractmethod
    def is_combination_failed(self, combination: Combination) -> bool:
        """Check if combination is known to have failed."""

    @abstractmethod
    def get_successful_result(self, combination: Combination) -> Optional[Element]:
        """Get result element for successful combination."""

    @abstractmethod
    def record_combination_result(self, result: CombinationResult) -> None:
        """Record the result of a combination attempt."""

    @abstractmethod
    def get_cache_stats(self) -> Dict[str, int]:
        """Get cache statistics."""

    @abstractmethod
    def result_already_in_sidebar(self, combination: Combination, available_elements: List[Element]) -> bool:
        """Check if combination result already exists in available elements."""
