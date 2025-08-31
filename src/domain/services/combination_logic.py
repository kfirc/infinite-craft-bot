"""Business logic for element combinations."""

from datetime import datetime
from typing import Dict, List, Optional, Set

from ..models.combination import Combination, CombinationResult, CombinationStatus
from ..models.element import Element
from .game_mechanics import GameMechanics


class CombinationLogic:
    """
    Business logic for managing element combinations.

    Handles combination validation, caching, and state management.
    Extracted from the combination logic in utils.py.
    """

    def __init__(self):
        """Initialize combination logic."""
        self._successful_combinations: Dict[str, Element] = {}
        self._failed_combinations: Set[str] = set()
        self._tested_combinations: Set[str] = set()

    def is_combination_valid(self, elem1: Element, elem2: Element) -> bool:
        """Check if combination is valid according to game rules."""
        return GameMechanics.is_valid_combination(elem1, elem2)

    def create_combination(self, elem1: Element, elem2: Element) -> Combination:
        """Create a new combination if valid."""
        if not self.is_combination_valid(elem1, elem2):
            raise ValueError(f"Invalid combination: {elem1.name} + {elem2.name}")

        return Combination(element1=elem1, element2=elem2)

    def is_combination_tested(self, combination: Combination) -> bool:
        """Check if combination has been tested before."""
        return combination.cache_key in self._tested_combinations

    def is_combination_successful(self, combination: Combination) -> bool:
        """Check if combination is known to be successful."""
        return combination.cache_key in self._successful_combinations

    def is_combination_failed(self, combination: Combination) -> bool:
        """Check if combination is known to have failed."""
        return combination.cache_key in self._failed_combinations

    def get_successful_result(self, combination: Combination) -> Optional[Element]:
        """Get the result element for a successful combination."""
        return self._successful_combinations.get(combination.cache_key)

    def record_combination_result(self, result: CombinationResult) -> None:
        """Record the result of a combination attempt."""
        combination = result.combination
        cache_key = combination.cache_key

        # Mark as tested
        self._tested_combinations.add(cache_key)

        # Record result based on status
        if result.status == CombinationStatus.SUCCESS and result.result_element:
            self._successful_combinations[cache_key] = result.result_element
            # Remove from failed if it was there (shouldn't happen, but defensive)
            self._failed_combinations.discard(cache_key)

        elif result.status == CombinationStatus.NO_RESULT:
            # Combination was attempted successfully but produced no result
            self._failed_combinations.add(cache_key)
            # Remove from successful if it was there
            self._successful_combinations.pop(cache_key, None)

        elif result.should_retry:
            # Don't record drag failures or errors as permanently failed
            # They can be retried later
            pass

    def should_skip_combination(self, combination: Combination, available_elements: List[Element]) -> Optional[str]:
        """
        Check if combination should be skipped.

        Returns None if should proceed, or reason string if should skip.
        """
        # Check if already successful and result exists in available elements
        if self.is_combination_successful(combination):
            result_element = self.get_successful_result(combination)
            if result_element and any(elem.matches_name(result_element.name) for elem in available_elements):
                return f"Result '{result_element.name}' already exists in available elements"

        # Check if known to fail (but allow retry after some time)
        if self.is_combination_failed(combination):
            return "Combination known to produce no result"

        return None

    def get_combination_stats(self) -> Dict[str, int]:
        """Get statistics about combination attempts."""
        return {
            "total_tested": len(self._tested_combinations),
            "successful": len(self._successful_combinations),
            "failed": len(self._failed_combinations),
            "success_rate": (
                len(self._successful_combinations) / len(self._tested_combinations) * 100
                if self._tested_combinations
                else 0
            ),
        }

    def get_untested_combinations(self, available_elements: List[Element]) -> List[Combination]:
        """Get all untested combinations from available elements."""
        untested = []

        for i, elem1 in enumerate(available_elements):
            for elem2 in available_elements[i + 1 :]:  # Avoid duplicates and self-combinations
                try:
                    combination = self.create_combination(elem1, elem2)
                    if not self.is_combination_tested(combination):
                        untested.append(combination)
                except ValueError:
                    # Invalid combination, skip
                    continue

        return untested

    def get_cached_combinations_for_export(self) -> Dict:
        """Get combination cache in format suitable for file export."""
        return {
            "successful": {key: element.to_dict() for key, element in self._successful_combinations.items()},
            "failed": list(self._failed_combinations),
            "tested": list(self._tested_combinations),
            "exported_at": datetime.now().isoformat(),
        }

    def load_cached_combinations_from_import(self, cache_data: Dict) -> None:
        """Load combination cache from imported data."""
        # Load successful combinations
        successful_data = cache_data.get("successful", {})
        for key, element_data in successful_data.items():
            try:
                element = Element.from_dict(element_data)
                self._successful_combinations[key] = element
            except Exception:
                # Skip invalid elements
                continue

        # Load failed and tested sets
        self._failed_combinations = set(cache_data.get("failed", []))
        self._tested_combinations = set(cache_data.get("tested", []))

        # Ensure consistency: all successful/failed combinations are marked as tested
        self._tested_combinations.update(self._successful_combinations.keys())
        self._tested_combinations.update(self._failed_combinations)

    def clear_cache(self) -> None:
        """Clear all cached combination data."""
        self._successful_combinations.clear()
        self._failed_combinations.clear()
        self._tested_combinations.clear()
