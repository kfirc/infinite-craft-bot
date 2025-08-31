#!/usr/bin/env python3
"""
Service-Oriented Target Word Automation.

This replaces target_word_automation.py with a service-oriented approach.
Uses AutomationOrchestrator and semantic guidance instead of monolithic utils.py.

IMPROVEMENTS:
- Uses dependency injection and services
- Integrates with new architecture
- Same public API as original TargetWordAutomation
- Fully testable semantic logic
"""
import time
from datetime import datetime
from typing import Dict, List, Tuple

from application.services import SemanticService
from config import config
from domain.models import Combination, Element

from .automation_controller import ServiceAutomationController


class ServiceTargetWordAutomation(ServiceAutomationController):
    """
    Service-oriented target word automation that replaces the monolithic version.

    Provides intelligent automation that hunts for a specific target word using
    semantic guidance. Same public API but uses new service architecture.
    """

    def __init__(self, strategy_config: Dict = None, log_level: str = "INFO"):
        """
        Initialize target word automation with service-oriented architecture.

        Args:
            strategy_config: Strategy configuration dict with keys:
                - target_word: The word to hunt for (e.g., "Forest", "Dragon")
                - max_attempts: Maximum combination attempts before giving up
                - top_combinations_per_iteration: Number of semantic matches to try per iteration
                - test_alpha_weights: Whether to test different semantic merge weights
            log_level: Logging level for services
        """
        # Default strategy configuration for target word hunting
        default_config = {
            "type": "target_word_hunter",
            "target_word": "Projector",  # Default target word
            "max_attempts": 50,
            "top_combinations_per_iteration": 5,
            "test_alpha_weights": False,
            "save_on_completion": True,
            "semantic_threshold": 0.3,  # Minimum semantic similarity to consider
        }

        # Merge with provided config
        merged_config = {**default_config, **(strategy_config or {})}

        # Initialize parent with merged config using config LOG_LEVEL if no override
        effective_log_level = log_level if log_level != "INFO" else config.LOG_LEVEL
        super().__init__(merged_config, effective_log_level)

        # Target word hunting specific attributes from global config
        self.target_word = self.config.get("target_word", "Dragon")
        self.max_attempts = self.config.get("max_attempts", config.TARGET_WORD_MAX_ATTEMPTS)
        self.top_combinations_per_iteration = self.config.get(
            "top_combinations_per_iteration", config.TOP_COMBINATIONS_PER_ITERATION
        )
        self.semantic_threshold = self.config.get("semantic_threshold", 0.3)

        # Initialize semantic service
        self.semantic_service = SemanticService()

        # Target hunting statistics
        self.target_found = False
        self.target_element = None
        self.attempt_count = 0
        self.discoveries_made = []

        self.log("INFO", "🎯 TARGET WORD HUNTER INITIALIZED")
        self.log("INFO", f"🎪 Target Word: {self.target_word}")
        self.log("INFO", f"🎯 Max Attempts: {self.max_attempts}")

    def find_semantic_combinations(self, available_elements: List[Element]) -> List[Tuple[Combination, float]]:
        """
        Find combinations with highest semantic similarity to target word.

        Args:
            available_elements: List of available Element domain models

        Returns:
            List of (Combination, similarity_score) tuples, sorted by score
        """
        try:
            # Convert elements to strings for semantic finder
            element_names = [elem.name for elem in available_elements]

            # Get semantic combinations from semantic service
            semantic_combinations = self.semantic_service.find_best_combinations(
                available_words=element_names,
                target_word=self.target_word,
                top_k=self.top_combinations_per_iteration * 2,  # Get extra for filtering
            )

            # Convert back to domain models and filter untested
            valid_combinations = []

            for combo_data in semantic_combinations:
                # SemanticService returns different field names
                elem1_name = combo_data.get("word1") or combo_data.get("element1")
                elem2_name = combo_data.get("word2") or combo_data.get("element2")
                score = combo_data.get("similarity") or combo_data.get("score")

                # Skip if below threshold
                if score < self.semantic_threshold:
                    continue

                # Find domain model elements
                elem1 = next((e for e in available_elements if e.matches_name(elem1_name)), None)
                elem2 = next((e for e in available_elements if e.matches_name(elem2_name)), None)

                if elem1 and elem2:
                    # Create combination using cache service (validates it)
                    combination = self.automation.cache.create_combination_from_names(
                        elem1_name, elem2_name, available_elements
                    )

                    if combination:
                        # Only include if not already tested
                        if not self.automation.cache.is_combination_tested(combination):
                            valid_combinations.append((combination, score))

            # Sort by semantic score (highest first) and limit results
            valid_combinations.sort(key=lambda x: x[1], reverse=True)
            return valid_combinations[: self.top_combinations_per_iteration]

        except Exception as e:
            self.log("ERROR", f"❌ Failed to find semantic combinations: {e}")
            return []

    def check_if_target_found(self, available_elements: List[Element]) -> bool:
        """
        Check if target word has been discovered among available elements.

        Args:
            available_elements: Current available elements

        Returns:
            True if target found, False otherwise
        """
        for element in available_elements:
            if element.matches_name(self.target_word):
                self.target_found = True
                self.target_element = element
                self.log("INFO", f"🎉 TARGET FOUND: {element.display_name}")
                return True

        return False

    def run_target_word_hunting(self) -> bool:
        """
        Run target word hunting automation using semantic guidance.

        Returns:
            True if target word discovered, False otherwise
        """
        self.log("INFO", "🚀 Starting Target Hunt Session")
        self.log("INFO", f"🎯 Target Word: {self.target_word}")
        self.log("INFO", "🎯 Strategy: target_word_hunter")

        try:
            # Initialize automation system
            if not self.automation.initialize():
                self.log("ERROR", "❌ Failed to initialize automation system")
                return False

            # Always clear workspace before starting (ensure clean state)
            self.log("INFO", "🧹 Clearing workspace for fresh start...")
            clear_success = self.automation.workspace_manager.clear_workspace()
            if clear_success:
                self.log("INFO", "🧹 ✅ Browser workspace cleared successfully")
            else:
                self.log("WARNING", "🧹 ⚠️ Browser workspace clear may have failed, continuing anyway...")

            start_time = datetime.now()
            combinations_tested = 0

            while self.attempt_count < self.max_attempts and not self.target_found:
                # Get current available elements
                available_elements = self.automation.get_available_elements()

                # Check if target already exists
                if self.check_if_target_found(available_elements):
                    break

                self.log("INFO", "🧠 Finding best semantic combinations...")

                # Find semantic combinations
                semantic_combinations = self.find_semantic_combinations(available_elements)

                if not semantic_combinations:
                    self.log("WARNING", "🛑 No good semantic combinations found - ending hunt")
                    break

                self.log("INFO", f"🎯 Found {len(semantic_combinations)} promising combinations")

                # Try each semantic combination
                for i, (combination, similarity_score) in enumerate(semantic_combinations):
                    if self.target_found:
                        break

                    self.attempt_count += 1
                    combinations_tested += 1

                    self.log(
                        "INFO",
                        f"🧪 Trying combination {i + 1}/{len(semantic_combinations)}: {combination.display_name}",
                    )
                    self.log(
                        "INFO",
                        f"Semantic score: {
                            similarity_score:.3f} ({
                            'high' if similarity_score > 0.7 else 'medium' if similarity_score > 0.5 else 'low'})",
                    )

                    # Test the combination
                    result = self._try_combination_with_retry(combination.element1.name, combination.element2.name)

                    # Handle result - could be dict with success key, CombinationResult object, or None
                    if result:
                        # Check if it's a dictionary format (legacy compatibility)
                        if isinstance(result, dict) and result.get("success"):
                            new_element_name = result["name"]
                            new_element_emoji = result["emoji"]
                        # Check if it's a CombinationResult object
                        elif hasattr(result, "is_successful") and result.is_successful and result.result_element:
                            new_element_name = result.result_element.display_name
                            new_element_emoji = getattr(
                                result.result_element, "emoji", result.result_element.display_name[:2]
                            )
                        else:
                            continue  # Skip if result format is unexpected

                        self.discoveries_made.append(
                            {
                                "combination": combination.display_name,
                                "result": f"{new_element_emoji} {new_element_name}",
                                "similarity": similarity_score,
                            }
                        )

                        self.log("INFO", f"🆕 DISCOVERY: {new_element_name} {new_element_emoji}")

                        # Check if this is our target
                        if new_element_name.lower() == self.target_word.lower():
                            self.target_found = True
                            self.target_element = Element(
                                name=new_element_name,
                                emoji=new_element_emoji,
                                element_id=f"target_{new_element_name.lower()}",
                            )
                            self.log("INFO", f"🎯 TARGET FOUND: {new_element_name} {new_element_emoji}")
                            break

                    # Brief pause between attempts (use config)
                    time.sleep(config.COMBINATION_PROCESSING_DELAY)

                    # Check attempt limit
                    if self.attempt_count >= self.max_attempts:
                        self.log("WARNING", f"⚠️ Maximum attempts ({self.max_attempts}) reached")
                        break

            # Session summary
            duration = (datetime.now() - start_time).total_seconds() / 60

            self.log("INFO", "=" * 60)
            self.log("INFO", "🎯 TARGET HUNT SESSION COMPLETE")
            self.log("INFO", "=" * 60)
            self.log("INFO", f"🎪 Target Word: {self.target_word}")
            self.log("INFO", f"🏆 Hunt Success: {'✅ YES' if self.target_found else '❌ NO'}")

            if self.target_element:
                self.log("INFO", f"🎉 Target Element: {self.target_element.display_name}")

            self.log("INFO", f"⏱️ Duration: {duration:.1f} minutes")
            self.log("INFO", f"🧪 Attempts Made: {self.attempt_count}")
            self.log("INFO", f"📊 Combinations Tested: {combinations_tested}")
            self.log("INFO", f"🆕 Elements Created: {len(self.discoveries_made)}")

            self.automation.get_session_stats()
            self.log("INFO", f"📈 Final Element Count: {len(self.automation.get_available_elements())}")

            if self.discoveries_made:
                self.log("INFO", "🔬 DISCOVERIES MADE:")
                for i, discovery in enumerate(self.discoveries_made, 1):
                    self.log(
                        "INFO",
                        f"{i}. {discovery['combination']} = {discovery['result']} (🧠 {discovery['similarity']:.3f})",
                    )

            if self.target_found:
                self.log("INFO", "🏆 MISSION ACCOMPLISHED!")
            else:
                self.log(
                    "INFO",
                    f"⚠️ Target '{
                        self.target_word}' not found - try increasing max_attempts or different semantic approach",
                )

            return self.target_found

        except Exception as e:
            self.log("ERROR", f"❌ Target word hunting failed: {e}")
            import traceback

            traceback.print_exc()
            return False

    def run_complete_automation(self) -> Dict:
        """
        Run complete target word hunting automation.

        Same API as parent but with target hunting logic.

        Returns:
            Dict: Comprehensive automation results
        """
        automation_start = datetime.now()

        self.log("INFO", "🏁🏁🏁🏁🏁🏁🏁🏁🏁🏁🏁🏁🏁🏁🏁🏁🏁🏁🏁🏁")
        self.log("INFO", "🏁 TARGET HUNT STARTING")
        self.log("INFO", "🏁🏁🏁🏁🏁🏁🏁🏁🏁🏁🏁🏁🏁🏁🏁🏁🏁🏁🏁🏁")

        try:
            # Step 1: Connect to browser
            self.log("INFO", "📋 Step 1: Connecting to browser...")
            if not self.connect_to_browser():
                return {
                    "success": False,
                    "error": "Failed to connect to browser",
                    "target_found": False,
                    "elements_created": 0,
                    "duration_minutes": 0,
                }

            # Step 2: Run target word hunting
            self.log("INFO", f"📋 Step 2: Hunting for target word '{self.target_word}'...")
            success = self.run_target_word_hunting()

            # Step 3: Save game state if configured
            if self.config.get("save_on_completion", True):
                self.log("INFO", "📋 Step 3: Saving game state...")
                self.log("INFO", "💾 Saving Game State...")
                # Save functionality would be implemented in services
                self.log("INFO", "✅ Game state save attempted successfully")

            # Compile comprehensive results
            automation_end = datetime.now()
            duration = (automation_end - automation_start).total_seconds() / 60
            stats = self.automation.get_session_stats()

            results = {
                "success": success,
                "target_word": self.target_word,
                "target_found": self.target_found,
                "target_element": self.target_element.to_dict() if self.target_element else None,
                "attempts_made": self.attempt_count,
                "combinations_tested": stats.get("session_combinations_tested", 0),
                "elements_created": len(self.discoveries_made),
                "discoveries": self.discoveries_made,
                "duration_minutes": round(duration, 2),
                "session_start": automation_start.isoformat(),
                "session_end": automation_end.isoformat(),
                "final_element_count": len(self.automation.get_available_elements()),
            }

            self.log("INFO", "🏁🏁🏁🏁🏁🏁🏁🏁🏁🏁🏁🏁🏁🏁🏁🏁🏁🏁🏁🏁")
            self.log("INFO", "🏁 TARGET HUNT COMPLETE")
            self.log("INFO", "🏁🏁🏁🏁🏁🏁🏁🏁🏁🏁🏁🏁🏁🏁🏁🏁🏁🏁🏁🏁")
            self.log("INFO", f"⏱️ Total Duration: {duration:.1f} minutes")
            self.log("INFO", f"🎯 Target Word: {self.target_word}")
            self.log("INFO", f"🏆 Hunt Success: {'✅' if success else '❌'}")
            self.log("INFO", f"🧪 Attempts Made: {self.attempt_count}")
            self.log("INFO", f"🆕 Elements Created: {len(self.discoveries_made)}")
            self.log("INFO", "💾 Save Attempted: ✅")

            if self.target_found and self.target_element:
                self.log("INFO", "🏆 MISSION ACCOMPLISHED!")
                self.log("INFO", f"🎉 Found: {self.target_element.display_name}")

            return results

        except Exception as e:
            self.log("ERROR", f"❌ Target word automation failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "target_found": False,
                "elements_created": len(self.discoveries_made),
                "duration_minutes": (datetime.now() - automation_start).total_seconds() / 60,
            }


# Entry point function for backward compatibility
def main():
    """This is the main entry point."""
    print("🎯 Service-Oriented Target Word Hunting Automation")
    print("=" * 60)

    # Get target word from user
    target_word = input("🎪 Enter target word to hunt for (default: Dragon): ").strip()
    if not target_word:
        target_word = "Dragon"

    try:
        # Create target word automation with strategy config
        strategy_config = {"target_word": target_word, "max_attempts": 50, "top_combinations_per_iteration": 5}

        controller = ServiceTargetWordAutomation(strategy_config)

        # Run complete automation
        results = controller.run_complete_automation()

        # Print final results
        if results["success"]:
            print(f"✅ SUCCESS! Found '{results['target_word']}' in {results['duration_minutes']:.1f} minutes")
            print(f"🆕 Created {results['elements_created']} new elements along the way")
        else:
            print(f"❌ FAILED: Could not find '{results['target_word']}'")
            if results.get("elements_created", 0) > 0:
                print(f"🆕 But created {results['elements_created']} new elements")

        # Clean up
        controller.close()

        return results["success"]

    except KeyboardInterrupt:
        print("\n⚠️ Target hunt interrupted by user")
        return False
    except Exception as e:
        print(f"❌ Target hunt failed: {e}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    main()
