#!/usr/bin/env python3
"""
Target Word Automation for Infinite Craft.

This automation uses semantic similarity to intelligently guide combinations
toward a specific target word, rather than random exploration.

Usage:
    # As a strategy config for AutomationController
    strategy_config = {
        'type': 'target_word_hunter',
        'target_word': 'Forest',
        'max_attempts': 50,
        'top_combinations_per_iteration': 5
    }
    automation = TargetWordAutomation(strategy_config)
    result = automation.run_complete_automation()
"""

from datetime import datetime
from typing import Dict, Optional

from automation import AutomationController
from config import config
from semantic_finder import SemanticWordFinder


class TargetWordAutomation(AutomationController):
    """
    Target Word Automation for Infinite Craft.

    Intelligent automation that hunts for a specific target word using semantic guidance.
    Inherits from AutomationController to maintain generic patterns.
    """

    def __init__(self, strategy_config: Dict = None, log_level: str = "INFO"):
        """
        Initialize target word automation with strategy configuration.

        Args:
            strategy_config: Strategy configuration dict with keys:
                - target_word: The word to hunt for (e.g., "Forest", "Dragon")
                - max_attempts: Maximum combination attempts before giving up
                - top_combinations_per_iteration: Number of semantic matches to try per iteration
                - test_alpha_weights: Whether to test different semantic merge weights
            log_level: Logging level for utilities
        """
        # Default strategy configuration for target word hunting
        default_config = {
            "type": "target_word_hunter",
            "target_word": "Forest",
            "max_attempts": 50,
            "top_combinations_per_iteration": 5,
            "test_alpha_weights": False,
            "save_on_completion": True,
            "clear_workspace_on_start": True,
        }

        # Merge with provided config
        self.target_config = {**default_config, **(strategy_config or {})}

        # Initialize parent AutomationController
        super().__init__(strategy_config=self.target_config, log_level=log_level)

        # Initialize semantic finder
        self.semantic_finder = SemanticWordFinder()

        # Target word hunting specific tracking
        self.target_word = self.target_config["target_word"]
        self.max_attempts = self.target_config["max_attempts"]
        self.top_combinations = self.target_config["top_combinations_per_iteration"]
        self.test_alpha_weights = self.target_config["test_alpha_weights"]

        # Hunt-specific tracking
        self.attempts_made = 0
        self.combinations_tried = set()
        self.discovered_elements = []

        self.log("INFO", "🎯 TARGET WORD HUNTER INITIALIZED")
        self.log("INFO", f"   Target: {self.target_word}")
        self.log("INFO", f"   Max attempts: {self.max_attempts}")
        self.log("INFO", f"   Combinations per iteration: {self.top_combinations}")
        self.log(
            "INFO",
            f"   Semantic model: {
                '✅ Available' if self.semantic_finder.is_model_available() else '❌ Using heuristics'}",
        )

    def run_target_hunt_session(self) -> Dict:
        """
        Hunt for the target word using semantic guidance.

        This implements the 'target_word_hunter' strategy.

        Returns:
            Dict: Session results and statistics
        """
        self.log("INFO", "🚀 Starting Target Hunt Session")
        self.log("INFO", "🎯 Strategy: target_word_hunter")
        self.log("INFO", f"🎪 Target: {self.target_word}")
        self.log("INFO", "=" * 60)

        session_results = {
            "target_word": self.target_word,
            "target_found": False,
            "attempts_made": 0,
            "combinations_tested": 0,
            "elements_created": 0,
            "session_duration_minutes": 0,
            "discoveries": [],
            "target_element": None,
            "hunt_success": False,
        }

        try:
            # STEP 1: Initialize workspace if configured to do so
            if self.config.get("clear_workspace_on_start", True):
                self.log("INFO", "📋 Step 1: Initializing clean workspace...")
                init_success = self.automation.initialize_clean_workspace()
                if not init_success:
                    self.log("WARNING", "⚠️ Workspace initialization had issues, continuing anyway...")

            # STEP 2: Map current situation
            self.log("INFO", "📋 Step 2: Mapping current game situation...")
            initial_situation = self.automation.map_current_situation()
            initial_situation["sidebar_element_count"]

            # STEP 3: Check if target already exists
            self.log("INFO", "📋 Step 3: Checking if target already exists...")
            if self._check_target_found():
                target_element = self._find_target_in_sidebar()
                self.log("INFO", f"✅ TARGET '{self.target_word}' ALREADY EXISTS!")
                session_results.update(
                    {"target_found": True, "target_element": target_element, "hunt_success": True, "attempts_made": 0}
                )
                return session_results

            # STEP 4: Start semantic hunting session
            self.log("INFO", "📋 Step 4: Starting semantic hunting session...")

            # Hunting loop
            iteration = 0
            while self.attempts_made < self.max_attempts:
                iteration += 1
                self.log("INFO", f"🔄 ITERATION {iteration} - Attempts: {self.attempts_made}/{self.max_attempts}")

                # Get current available words
                available_words = [elem["name"] for elem in self.automation.sidebar_elements]

                # Find best semantic combinations
                self.log("INFO", "🧠 Finding best semantic combinations...")
                all_combinations = self.semantic_finder.find_best_combinations(
                    available_words,
                    self.target_word,
                    top_k=self.top_combinations * 3,  # Get more to account for filtering
                    test_alphas=self.test_alpha_weights,
                )

                if not all_combinations:
                    self.log("WARNING", "⚠️ No good combinations found - ending hunt")
                    break

                # CRITICAL: Filter out already-tested combinations to prevent infinite loop
                untested_combinations = []
                for combo in all_combinations:
                    combo_key = tuple(sorted([combo["word1"].lower(), combo["word2"].lower()]))
                    if combo_key not in self.combinations_tried:
                        untested_combinations.append(combo)

                # Take only the top combinations we actually want to try
                best_combinations = untested_combinations[: self.top_combinations]

                self.log("INFO", f"🔍 Found {len(all_combinations)} semantic matches")
                self.log("INFO", f"   📋 Untested: {len(untested_combinations)}")
                self.log("INFO", f"   🎯 Will try: {len(best_combinations)}")

                if not best_combinations:
                    self.log("WARNING", "🛑 All good combinations already tested - ending hunt")
                    self.log("WARNING", f"   Total combinations tried: {len(self.combinations_tried)}")
                    break

                # Try the best combinations (all are guaranteed to be untested)
                found_target = False

                for i, combo in enumerate(best_combinations, 1):
                    word1, word2 = combo["word1"], combo["word2"]
                    combo_key = tuple(sorted([word1.lower(), word2.lower()]))

                    self.log("INFO", f"🧪 Trying combination {i}/{len(best_combinations)}: {word1} + {word2}")
                    self.log("INFO", f"   Semantic score: {combo['score']:.3f} ({combo['confidence']})")

                    # CRITICAL: Try combination with shared retry mechanism - don't mark as
                    # tried until success/permanent failure
                    result = self._try_combination_with_retry(word1, word2, max_retries=3)

                    # Only mark as tried after we've exhausted retries
                    self.combinations_tried.add(combo_key)
                    self.attempts_made += 1

                    if result:
                        # New element discovered
                        self.discovered_elements.append(result)
                        session_results["discoveries"].append(
                            {
                                "combination": f"{word1} + {word2}",
                                "result": f"{result['emoji']} {result['name']}",
                                "created_at": result.get("discovered_at", "unknown"),
                                "semantic_score": combo["score"],
                            }
                        )

                        self.log("INFO", f"🆕 DISCOVERY: {result['name']} {result['emoji']}")

                        # Check if this is our target
                        if result["name"].lower() == self.target_word.lower():
                            self.log("INFO", f"🎉 TARGET FOUND: {result['name']} {result['emoji']}")
                            self.log("INFO", f"🏆 SUCCESS in {self.attempts_made} attempts!")
                            session_results.update(
                                {"target_found": True, "target_element": result, "hunt_success": True}
                            )
                            found_target = True
                            break
                    else:
                        self.log("DEBUG", f"⚪ No result from {word1} + {word2}")

                    # Check if target appeared from side effects
                    if self._check_target_found():
                        target_element = self._find_target_in_sidebar()
                        self.log(
                            "INFO", f"🎉 TARGET FOUND (indirect): {target_element['name']} {target_element['emoji']}"
                        )
                        session_results.update(
                            {"target_found": True, "target_element": target_element, "hunt_success": True}
                        )
                        found_target = True
                        break

                if found_target:
                    break

                # Update sidebar for next iteration
                self.automation.update_sidebar_cache()

                self.log(
                    "INFO",
                    f"📊 Iteration {
                        iteration} complete - Discovered: {len(self.discovered_elements)} new elements total",
                )

            # Final statistics
            final_stats = self.automation.get_stats_summary()
            session_duration = (datetime.now() - self.session_start).total_seconds() / 60

            session_results.update(
                {
                    "attempts_made": self.attempts_made,
                    "combinations_tested": len(self.combinations_tried),
                    "elements_created": len(self.discovered_elements),
                    "session_duration_minutes": session_duration,
                    "final_element_count": final_stats["total_elements"],
                }
            )

            # Final check if not found yet
            if not session_results["target_found"] and self._check_target_found():
                target_element = self._find_target_in_sidebar()
                self.log("INFO", f"🎉 TARGET FOUND (final check): {target_element['name']} {target_element['emoji']}")
                session_results.update({"target_found": True, "target_element": target_element, "hunt_success": True})

            self._print_hunt_summary(session_results)
            return session_results

        except Exception as e:
            self.log("ERROR", f"❌ Hunt failed with error: {e}")
            session_results["error"] = str(e)
            return session_results

    def _check_target_found(self) -> bool:
        """Check if target word exists in current sidebar."""
        self.automation.update_sidebar_cache()
        return any(elem["name"].lower() == self.target_word.lower() for elem in self.automation.sidebar_elements)

    def _find_target_in_sidebar(self) -> Optional[Dict]:
        """Find target element in sidebar."""
        for elem in self.automation.sidebar_elements:
            if elem["name"].lower() == self.target_word.lower():
                return {
                    "name": elem["name"],
                    "emoji": elem["emoji"],
                    "id": elem["id"],
                    "attempts_to_find": self.attempts_made,
                }
        return None

    def _print_hunt_summary(self, results: Dict):
        """Print formatted hunt session summary."""
        self.log("INFO", "\n" + "=" * 60)
        self.log("INFO", "🎯 TARGET HUNT SESSION COMPLETE")
        self.log("INFO", "=" * 60)

        # Target hunt results
        self.log("INFO", f"🎪 Target Word: {results['target_word']}")
        self.log("INFO", f"🏆 Hunt Success: {'✅ YES' if results['hunt_success'] else '❌ NO'}")
        if results["target_element"]:
            elem = results["target_element"]
            self.log("INFO", f"🎉 Target Element: {elem.get('emoji', '')} {elem.get('name', '')}")

        # Session statistics
        self.log("INFO", f"⏱️  Duration: {results['session_duration_minutes']:.1f} minutes")
        self.log("INFO", f"🧪 Attempts Made: {results['attempts_made']}")
        self.log("INFO", f"📊 Combinations Tested: {results['combinations_tested']}")
        self.log("INFO", f"🆕 Elements Created: {results['elements_created']}")
        self.log("INFO", f"📈 Final Element Count: {results['final_element_count']}")

        # Discoveries
        if results["discoveries"]:
            self.log("INFO", "\n🔬 DISCOVERIES MADE:")
            for i, discovery in enumerate(results["discoveries"], 1):
                score_text = f" (🧠 {discovery['semantic_score']:.3f})" if "semantic_score" in discovery else ""
                self.log("INFO", f"   {i:2d}. {discovery['combination']} = {discovery['result']}{score_text}")

        # Final status
        if results["hunt_success"]:
            self.log("INFO", "\n🏆 MISSION ACCOMPLISHED!")
        else:
            self.log("INFO", f"\n⏳ Hunt incomplete - target '{results['target_word']}' not found")

        self.log("INFO", "=" * 60)

    def run_complete_automation(self) -> bool:
        """
        Run the complete target word automation: connect, hunt target word, and save.

        Overrides parent method to use target_word_hunter strategy.

        Returns:
            bool: True if target word was found successfully
        """
        try:
            self.log("INFO", "🤖 INFINITE CRAFT TARGET WORD HUNTER")
            self.log("INFO", "=" * 60)
            self.log("INFO", f"🎯 Goal: Find target word '{self.target_word}'")
            self.log("INFO", f"🕒 Started at: {self.session_start.strftime('%Y-%m-%d %H:%M:%S')}")
            self.log("INFO", "=" * 60)

            # Step 1: Connect to browser
            self.log("INFO", "📋 Step 1: Connecting to Chrome browser...")
            if not self.connect_to_browser():
                self.log("ERROR", "❌ Failed to connect to browser")
                self.log("INFO", "📋 Instructions:")
                self.log("INFO", "   1. Run: ./launch_chrome_debug.sh")
                self.log("INFO", "   2. Wait for Chrome to load Infinite Craft")
                self.log("INFO", "   3. Run this script again")
                return False

            # Step 2: Target hunt session
            self.log("INFO", "\n📋 Step 2: Running target hunt session...")
            results = self.run_target_hunt_session()

            # Step 3: Save state if target found and configured to do so
            save_success = True
            if results["hunt_success"] and self.config.get("save_on_completion", True):
                self.log("INFO", "\n📋 Step 3: Saving game state...")
                save_success = self.save_and_finish()
            else:
                self.log("INFO", "\n📋 Step 3: Skipping save (target not found or disabled in config)")

            # Final summary
            session_duration = (datetime.now() - self.session_start).total_seconds() / 60

            self.log("INFO", "\n" + "🏁" * 20)
            self.log("INFO", "🏁 TARGET HUNT COMPLETE")
            self.log("INFO", "🏁" * 20)
            self.log("INFO", f"⏱️  Total Duration: {session_duration:.1f} minutes")
            self.log("INFO", f"🎯 Target Word: {self.target_word}")
            self.log("INFO", f"🏆 Hunt Success: {'✅' if results['hunt_success'] else '❌'}")
            self.log("INFO", f"🧪 Attempts Made: {results['attempts_made']}")
            self.log("INFO", f"🆕 Elements Created: {results['elements_created']}")
            self.log("INFO", f"💾 Save Attempted: {'✅' if save_success else '❌'}")

            # Success criteria
            if results["hunt_success"]:
                self.log("INFO", "🏆 MISSION ACCOMPLISHED!")
                if results["target_element"]:
                    elem = results["target_element"]
                    self.log("INFO", f"🎉 Found: {elem.get('emoji', '')} {elem.get('name', '')}")
            else:
                self.log(
                    "INFO", f"⏳ Hunt failed - '{self.target_word}' not found in {results['attempts_made']} attempts"
                )

            return results["hunt_success"]

        except Exception as e:
            self.log("ERROR", f"❌ Complete automation failed: {e}")
            return False


def hunt_specific_word(target_word: str, max_attempts: int = 50) -> bool:
    """
    Hunt for a specific word using the generic controller pattern.

    Args:
        target_word: Word to hunt for
        max_attempts: Maximum attempts before giving up

    Returns:
        bool: True if target word was found
    """
    strategy_config = {
        "type": "target_word_hunter",
        "target_word": target_word,
        "max_attempts": max_attempts,
        "top_combinations_per_iteration": 5,
        "test_alpha_weights": False,
        "save_on_completion": True,
        "clear_workspace_on_start": True,
    }

    automation = TargetWordAutomation(strategy_config=strategy_config, log_level="INFO")
    return automation.run_complete_automation()


def main():
    """Run target word automation."""
    import sys

    print("🎯 INFINITE CRAFT TARGET WORD HUNTER")
    print("=" * 60)
    print("🎪 Strategy: Semantic-guided word hunting")
    print("📋 Requirements:")
    print("   1. Chrome browser with remote debugging enabled")
    print("   2. Infinite Craft game loaded and ready")
    print("=" * 60)
    print()

    # Get target word from command line or user input
    if len(sys.argv) > 1:
        target = sys.argv[1]
        print(f"🎯 Target word from command line: '{target}'")
    else:
        target = input("🎯 Enter target word to hunt for: ").strip()

    if not target:
        print("❌ No target word provided")
        sys.exit(1)

    # Wait for user confirmation
    if not config.SKIP_ENTER_PROMPT and not config.AUTO_ASSUME_WEBSITE_READY:
        input(f"Press Enter when Chrome is ready to hunt for '{target}'...")
    else:
        print(f"Auto-starting hunt for '{target}' (skip_enter_prompt enabled)...")

    # Create target word automation with configuration
    strategy_config = {
        "type": "target_word_hunter",
        "target_word": target,
        "max_attempts": 100,
        "top_combinations_per_iteration": 5,
        "test_alpha_weights": False,
        "save_on_completion": True,
        "clear_workspace_on_start": True,
    }

    automation = TargetWordAutomation(strategy_config=strategy_config, log_level="INFO")

    try:
        # Run complete automation
        success = automation.run_complete_automation()

        if success:
            print("\n🎉 TARGET FOUND SUCCESSFULLY!")
            print(f"🎪 Successfully hunted down: '{target}'")
            print("📥 Check your Downloads folder for the save file")
        else:
            print("\n⚠️ HUNT UNSUCCESSFUL")
            print(f"🔍 Could not find '{target}' - check the logs above for details")

    except KeyboardInterrupt:
        print("\n\n🛑 HUNT INTERRUPTED BY USER")
        automation.log("INFO", "User interrupted target hunt")

    except Exception as e:
        print(f"\n💥 HUNT CRASHED: {e}")
        import traceback

        traceback.print_exc()

    finally:
        automation.close()
        print("\n👋 Hunt finished - browser kept open for inspection")


if __name__ == "__main__":
    main()
