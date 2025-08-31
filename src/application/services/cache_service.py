"""Cache service for combination tracking and persistence."""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from application.interfaces import ICacheService, ILoggingService
from domain.models import Combination, CombinationResult, Element
from domain.services import CombinationLogic


class CacheService(ICacheService):
    """
    Service for managing combination cache with file persistence.

    Extracted from utils.py combination_cache logic with improvements:
    - Uses domain models instead of raw strings/dicts
    - Implements proper interface for dependency injection
    - Separates file I/O from business logic
    - Better error handling and logging
    """

    def __init__(self, file_path: str, logging_service: ILoggingService):
        """
        Initialize cache service.

        Args:
            file_path: Path to cache file for persistence
            logging_service: Service for logging operations
        """
        self.file_path = file_path
        self.logger = logging_service

        # Use domain service for business logic
        self.combination_logic = CombinationLogic()

        # Statistics tracking
        self.stats = {
            "combinations_tested": 0,
            "combinations_successful": 0,
            "session_start": datetime.now(),
        }

        # Auto-load cache on initialization
        self.load_cache_from_file(file_path)

    def load_cache_from_file(self, file_path: str) -> None:
        """Load combination cache from file with proper domain model conversion."""
        try:
            if os.path.exists(file_path):
                self.logger.info(f"📥 Loading combination cache from {file_path}")

                with open(file_path, "r") as f:
                    cache_data = json.load(f)

                # Load cache data into domain service
                self.combination_logic.load_cached_combinations_from_import(cache_data)

                # Update statistics
                stats = self.combination_logic.get_combination_stats()
                self.logger.info(
                    f"✅ Cache loaded: {stats['successful']} successful, "
                    f"{stats['failed']} failed, {stats['total_tested']} total tested"
                )

            else:
                self.logger.info("📝 No existing cache found, starting fresh")
                # combination_logic already initializes with empty cache

        except Exception as e:
            self.logger.error(f"❌ Failed to load cache: {e}")
            # Clear cache on error - combination_logic will handle this
            self.combination_logic.clear_cache()

    def save_cache_to_file(self, file_path: str) -> None:
        """Save combination cache to file for persistence."""
        try:
            # Ensure directory exists
            cache_path = Path(file_path)
            cache_path.parent.mkdir(parents=True, exist_ok=True)

            # Get cache data from domain service
            cache_data = self.combination_logic.get_cached_combinations_for_export()

            # Add additional metadata
            stats = self.combination_logic.get_combination_stats()
            cache_data.update(
                {
                    "last_updated": datetime.now().isoformat(),
                    "total_successful": stats["successful"],
                    "total_failed": stats["failed"],
                    "total_tested": stats["total_tested"],
                    "success_rate": stats["success_rate"],
                }
            )

            with open(file_path, "w") as f:
                json.dump(cache_data, f, indent=2, default=str)

            self.logger.debug(f"💾 Cache saved to {file_path}")

        except Exception as e:
            self.logger.error(f"❌ Failed to save cache: {e}")

    def is_combination_tested(self, combination: Combination) -> bool:
        """Check if combination has been tested."""
        return self.combination_logic.is_combination_tested(combination)

    def is_combination_successful(self, combination: Combination) -> bool:
        """Check if combination is known to be successful."""
        return self.combination_logic.is_combination_successful(combination)

    def is_combination_failed(self, combination: Combination) -> bool:
        """Check if combination is known to have failed."""
        return self.combination_logic.is_combination_failed(combination)

    def get_successful_result(self, combination: Combination) -> Optional[Element]:
        """Get result element for successful combination."""
        return self.combination_logic.get_successful_result(combination)

    def record_combination_result(self, result: CombinationResult) -> None:
        """
        Record the result of a combination attempt.

        Updates internal cache and saves to file immediately.
        """
        # Record in domain service
        self.combination_logic.record_combination_result(result)

        # Update session statistics
        self.stats["combinations_tested"] += 1
        if result.is_successful:
            self.stats["combinations_successful"] += 1

        # Log the operation
        if result.is_successful and result.result_element:
            self.logger.info(
                f"💾 CACHED SUCCESS: {result.combination.cache_key} → " f"{result.result_element.display_name}"
            )
        else:
            self.logger.info(f"💾 CACHED FAILURE: {result.combination.cache_key} → No result")

        # Save to file immediately (matches original behavior)
        self.save_cache_to_file(self.file_path)

    def get_cache_stats(self) -> Dict[str, int]:
        """Get cache statistics including session data."""
        domain_stats = self.combination_logic.get_combination_stats()

        # Combine with session stats
        return {
            **domain_stats,
            "session_combinations_tested": self.stats["combinations_tested"],
            "session_combinations_successful": self.stats["combinations_successful"],
            "session_duration_minutes": int((datetime.now() - self.stats["session_start"]).total_seconds() / 60),
        }

    def result_already_in_sidebar(self, combination: Combination, available_elements: List[Element]) -> bool:
        """
        Check if combination result already exists in available elements.

        This helps skip combinations where the result is already discovered.
        """
        if not self.is_combination_successful(combination):
            return False

        result_element = self.get_successful_result(combination)
        if not result_element:
            return False

        # Check if any available element matches the result
        return any(elem.matches_name(result_element.name) for elem in available_elements)

    def get_untested_combinations(self, available_elements: List[Element]) -> List[Combination]:
        """Get all untested combinations from available elements."""
        return self.combination_logic.get_untested_combinations(available_elements)

    def should_skip_combination(self, combination: Combination, available_elements: List[Element]) -> Optional[str]:
        """
        Check if combination should be skipped with reason.

        Returns None if should proceed, or reason string if should skip.
        """
        return self.combination_logic.should_skip_combination(combination, available_elements)

    # Backward compatibility methods for gradual migration

    def is_combination_tested_by_names(self, elem1_name: str, elem2_name: str) -> bool:
        """Backward compatibility: Check if combination is tested using element names."""
        # This would require converting names to elements, but for migration we can use
        # the original cache key approach
        cache_key = "+".join(sorted([elem1_name.lower(), elem2_name.lower()]))
        self.combination_logic.get_combination_stats()
        # This is a simplified check - in full migration we'd create proper Elements
        return any(cache_key in str(combo_key) for combo_key in self.combination_logic._tested_combinations)

    def create_combination_from_names(
        self, elem1_name: str, elem2_name: str, available_elements: List[Element]
    ) -> Optional[Combination]:
        """Helper to create Combination from names using available elements."""
        elem1 = next((e for e in available_elements if e.matches_name(elem1_name)), None)
        elem2 = next((e for e in available_elements if e.matches_name(elem2_name)), None)

        if elem1 and elem2:
            try:
                return self.combination_logic.create_combination(elem1, elem2)
            except ValueError:
                # Invalid combination (e.g., same element)
                return None
        return None
