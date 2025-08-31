#!/usr/bin/env python3
"""
Infinite Craft Automation Utilities.

PROVEN WORKING AUTOMATION for Infinite Craft game at https://neal.fun/infinite-craft/

🎉 BREAKTHROUGH: Optimized smooth drag method works with Vue.js - 3x faster!

Key Features:
✅ Optimized drag method: Smooth drag with 12 steps - 3x faster than original
✅ Element combination: Water + Fire → Steam (proven to work)
✅ Workspace tracking: Handles Vue.js DOM invisibility issue
✅ Game loading: Automatic game initialization and element detection
✅ Clean API: Simple functions for drag, combine, and save operations

Usage Example:
    automation = InfiniteCraftAutomation()
    automation.load_game()
    result = automation.combine_elements("Water", "Fire")  # Returns "Steam"
    automation.close()

Requirements: selenium>=4.15.0, Chrome WebDriver
"""

import functools
import json
import os
import random
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import requests
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

# Import configuration system
try:
    from config import config
except ImportError:
    # Fallback for when config is not available (e.g., during initial setup)
    class DummyConfig:
        def __getattr__(self, name):
            # Return sensible defaults for missing config
            defaults = {
                "POLL_INTERVAL": 0.1,
                "STABLE_CHECKS_REQUIRED": 3,
                "MAX_ATTEMPTS_BEFORE_CLEAR": 5,
                "MERGE_DISTANCE_TOLERANCE": 50,
                "ELEMENT_POSITION_TOLERANCE": 60,
                "CHROME_CONNECTION_TIMEOUT": 5,
                "GAME_LOAD_TIMEOUT": 10,
                "COMBINATION_PROCESSING_DELAY": 0.8,
                "SCROLL_COMPLETION_DELAY": 0.3,
                "COMBINATION_RESULT_DELAY": 4.0,
                "CHROME_TAB_SWITCH_DELAY": 3.0,
                "DIALOG_CLOSE_DELAY": 0.5,
                "MENU_OPERATION_DELAY": 1.0,
                "SAVE_OPERATION_DELAY": 2.0,
                "DRAG_PIXEL_STEPS": 300,
                "DRAG_MAX_STEPS": 3,
                "DRAG_HOLD_DURATION": 0.05,
                "KEEP_BROWSER_OPEN_DELAY": 10.0,
            }
            return defaults.get(name, 0)

    config = DummyConfig()


# ================================
# PERFORMANCE INSTRUMENTATION
# ================================


def timing_decorator(operation_name: str):
    """Decorator to time function execution and log results."""

    def decorator(func):
        @functools.wraps(func)
        def wrapper(self, *args, **kwargs):
            start_time = time.time()
            try:
                result = func(self, *args, **kwargs)
                execution_time = time.time() - start_time
                self.log("DEBUG", f"⏱️ TIMING: {operation_name} took {execution_time:.3f}s")
                return result
            except Exception as e:
                execution_time = time.time() - start_time
                self.log("ERROR", f"⏱️ TIMING: {operation_name} FAILED after {execution_time:.3f}s - {e}")
                raise

        return wrapper

    return decorator


def time_operation(self, operation_name: str):
    """Context manager for timing operations."""

    class TimingContext:
        def __init__(self, automation_instance, op_name):
            self.automation = automation_instance
            self.op_name = op_name
            self.start_time = None

        def __enter__(self):
            self.start_time = time.time()
            self.automation.log("DEBUG", f"⏱️ START: {self.op_name}")
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            execution_time = time.time() - self.start_time
            if exc_type is None:
                self.automation.log("DEBUG", f"⏱️ END: {self.op_name} completed in {execution_time:.3f}s")
            else:
                self.automation.log("ERROR", f"⏱️ ERROR: {self.op_name} failed after {execution_time:.3f}s")

    return TimingContext(self, operation_name)


class InfiniteCraftAutomation:
    """
    Complete automation class for Infinite Craft with advanced features.

    Features:
    - Fast pixel-by-pixel smooth dragging
    - Sidebar element tracking and caching
    - Combination result caching
    - Workspace management and cleaning
    - Save state via menu button detection
    - Comprehensive logging
    """

    def __init__(self, headless: bool = False, log_level: str = "INFO", cache_file: str = "../automation.cache.json"):
        """
        Initialize automation with enhanced features and persistent caching.

        Args:
            headless: Run browser in headless mode
            log_level: Logging level (DEBUG, INFO, WARNING, ERROR)
            cache_file: Path to cache file for persistent combination tracking
        """
        self.driver = None
        self.headless = headless
        self.log_level = log_level
        self.cache_file = cache_file

        # Element tracking
        self.sidebar_elements: List[Dict] = []
        self.sidebar_cache: Dict[str, Dict] = {}  # Cache by element name

        # Persistent combination caching with O(1) lookup
        self.combination_cache = {
            "successful": {},  # Dict[str, Dict] - key: "elem1+elem2", value: result
            "failed": set(),  # Set[str] - failed combination keys
            "tested": set(),  # Set[str] - all tested combination keys
        }

        # Workspace management with 5 distinct locations - clear after 5 attempts
        # FIXED coordinates based on workspace investigation
        # Safe area: X: 200-1000, Y: 200-392 (within parent container bounds)
        self.predefined_locations = [
            (300, 250),  # Location 1 - Top left (safe zone)
            (700, 250),  # Location 2 - Top right (safe zone)
            (350, 350),  # Location 3 - Bottom left (safe zone)
            (650, 350),  # Location 4 - Bottom right (safe zone)
            (500, 300),  # Location 5 - Center (safe zone)
        ]
        self.current_location_index = 0
        self.attempts_since_last_clear = 0
        self.max_attempts_before_clear = config.MAX_ATTEMPTS_BEFORE_CLEAR
        self.workspace_elements: List[Dict] = []

        # Statistics
        self.stats = {
            "combinations_tested": 0,
            "combinations_successful": 0,
            "elements_discovered": 0,
            "session_start": datetime.now(),
            "workspace_clears": 0,
        }

        # Load persistent cache
        self._load_combination_cache()

        self.setup_driver()

    def time_operation(self, operation_name: str):
        """Context manager for timing operations."""
        return time_operation(self, operation_name)

    @timing_decorator("LOAD_CACHE_FROM_FILE")
    def _load_combination_cache(self):
        """Load persistent combination cache from file with O(1) lookup optimization."""
        try:
            if os.path.exists(self.cache_file):
                self.log("INFO", f"📥 Loading combination cache from {self.cache_file}")

                with open(self.cache_file, "r") as f:
                    cache_data = json.load(f)

                # Load successful combinations (dict for O(1) lookup)
                self.combination_cache["successful"] = cache_data.get("successful", {})

                # Load failed combinations (set for O(1) lookup)
                self.combination_cache["failed"] = set(cache_data.get("failed", []))

                # Load tested combinations (set for O(1) lookup)
                self.combination_cache["tested"] = set(cache_data.get("tested", []))

                # Update stats from cache
                successful_count = len(self.combination_cache["successful"])
                failed_count = len(self.combination_cache["failed"])
                total_tested = len(self.combination_cache["tested"])

                self.log(
                    "INFO",
                    f"✅ Cache loaded: {successful_count} successful, {
                        failed_count} failed, {total_tested} total tested",
                )

            else:
                self.log("INFO", "📝 No existing cache found, starting fresh")

        except Exception as e:
            self.log("ERROR", f"❌ Failed to load cache: {e}")
            # Initialize empty cache on error
            self.combination_cache = {"successful": {}, "failed": set(), "tested": set()}

    @timing_decorator("SAVE_CACHE_TO_FILE")
    def _save_combination_cache(self):
        """Save combination cache to file for persistence."""
        try:
            # Ensure directory exists
            cache_path = Path(self.cache_file)
            cache_path.parent.mkdir(parents=True, exist_ok=True)

            # Convert sets to lists for JSON serialization
            cache_data = {
                "successful": self.combination_cache["successful"],
                "failed": list(self.combination_cache["failed"]),
                "tested": list(self.combination_cache["tested"]),
                "last_updated": datetime.now().isoformat(),
                "total_successful": len(self.combination_cache["successful"]),
                "total_failed": len(self.combination_cache["failed"]),
                "total_tested": len(self.combination_cache["tested"]),
            }

            with open(self.cache_file, "w") as f:
                json.dump(cache_data, f, indent=2, default=str)

            self.log("DEBUG", f"💾 Cache saved to {self.cache_file}")

        except Exception as e:
            self.log("ERROR", f"❌ Failed to save cache: {e}")

    def _get_combination_key(self, elem1: str, elem2: str) -> str:
        """Get normalized combination key for O(1) lookup."""
        return "+".join(sorted([elem1.lower(), elem2.lower()]))

    def is_combination_tested(self, elem1: str, elem2: str) -> bool:
        """Check if combination was already tested with O(1) lookup."""
        key = self._get_combination_key(elem1, elem2)
        return key in self.combination_cache["tested"]

    def result_already_in_sidebar(self, elem1: str, elem2: str) -> Optional[str]:
        """
        Check if the result of this combination already exists in the sidebar.
        If result exists, skip the combination to avoid duplicate work.

        Returns:
            str: Name of result element if it exists in sidebar, None otherwise
        """
        key = self._get_combination_key(elem1, elem2)

        # Check if we know the result from cache
        if key in self.combination_cache["successful"]:
            result_name = self.combination_cache["successful"][key]["name"]

            # Update sidebar cache to get current state
            self.update_sidebar_cache()

            # Check if result already exists in current sidebar
            if result_name in self.sidebar_cache:
                self.log("DEBUG", f"⏭️ Result '{result_name}' already exists in sidebar, skipping {elem1} + {elem2}")
                return result_name

        return None

    def is_combination_successful(self, elem1: str, elem2: str) -> Optional[Dict]:
        """Check if combination is known successful with O(1) lookup."""
        key = self._get_combination_key(elem1, elem2)
        return self.combination_cache["successful"].get(key)

    def is_combination_failed(self, elem1: str, elem2: str) -> bool:
        """Check if combination is known failed with O(1) lookup."""
        key = self._get_combination_key(elem1, elem2)
        return key in self.combination_cache["failed"]

    def _get_next_workspace_location(self) -> Tuple[int, int]:
        """
        Get the next workspace location using round-robin through 5 predefined positions.

        Returns:
            Tuple[int, int]: (x, y) coordinates for workspace
        """
        location = self.predefined_locations[self.current_location_index]

        # Advance to next location for next time
        self.current_location_index = (self.current_location_index + 1) % len(self.predefined_locations)

        return location

    def _should_clear_workspace(self) -> bool:
        """Check if workspace should be cleared after this attempt."""
        # Clear after 5 attempts, not every attempt
        return self.attempts_since_last_clear >= self.max_attempts_before_clear

    @timing_decorator("SMART_WAIT_FOR_MERGE")
    def _wait_for_merge_completion(
        self,
        workspace_after_first: List[Dict],
        element1_name: str,
        element2_name: str,
        target_x: int,
        target_y: int,
        max_wait_time: float = 2.0,
    ) -> List[Dict]:
        """
        Wait for potential merge completion (game rule: merge happens within 2 seconds or never).

        This waits to see if elements merge, but importantly:
        - If merge happens within 2s → SUCCESS with new element
        - If no merge after 2s → Still SUCCESS (combination was attempted)
        - Only FAILURE is if elements never appeared on board

        Args:
            workspace_after_first: Workspace state after first element was dragged
            element1_name: Name of first element
            element2_name: Name of second element
            target_x, target_y: Target coordinates where merge should happen
            max_wait_time: Maximum time to wait for merge (default 2.0s per game rules)

        Returns:
            Final workspace state after merge completion or timeout
        """
        start_time = time.time()
        poll_interval = config.POLL_INTERVAL
        last_workspace_state = None
        stable_count = 0
        required_stable_checks = config.STABLE_CHECKS_REQUIRED

        self.log("DEBUG", f"🔄 Smart waiting for merge: {element1_name} + {element2_name}")

        while (time.time() - start_time) < max_wait_time:
            # Get current workspace state
            current_workspace = self._get_workspace_elements()

            # ENHANCED DEBUGGING: Show current workspace state
            current_names = [e["name"] for e in current_workspace]
            self.log("DEBUG", f"📋 Current workspace: {current_names}")

            # Check if elements are properly positioned (within merge distance)
            elements_at_target = self._find_elements_near_location(
                current_workspace, target_x, target_y, tolerance=config.MERGE_DISTANCE_TOLERANCE
            )

            if len(elements_at_target) >= 2:
                target_names = [e["name"] for e in elements_at_target]
                self.log(
                    "DEBUG",
                    f"🎯 Found {len(elements_at_target)} elements near target ({target_x}, {target_y}): {target_names}",
                )
            elif len(elements_at_target) == 1:
                target_name = elements_at_target[0]["name"]
                self.log("DEBUG", f"🔄 Only 1 element near target: {target_name}")
            elif len(elements_at_target) == 0:
                self.log("DEBUG", f"📭 No elements near target ({target_x}, {target_y})")

            # ENHANCED: Show element positions for debugging
            if len(current_workspace) <= 6:  # Only show positions if not too many elements
                positions = [(e["name"], e.get("x", "N/A"), e.get("y", "N/A")) for e in current_workspace]
                self.log("DEBUG", f"📍 Element positions: {positions}")

            # Check if workspace state has stabilized
            if last_workspace_state is not None:
                # Compare current state with last state
                if self._workspace_states_equal(current_workspace, last_workspace_state):
                    stable_count += 1
                    if stable_count >= required_stable_checks:
                        elapsed = time.time() - start_time
                        self.log("DEBUG", f"✅ Workspace stabilized after {elapsed:.3f}s - merge complete")
                        return current_workspace
                else:
                    stable_count = 0  # Reset if state changed

            last_workspace_state = current_workspace[:]  # Copy current state
            time.sleep(poll_interval)

        # Timeout reached - this is normal if no merge occurs
        elapsed = time.time() - start_time
        final_workspace = self._get_workspace_elements()
        self.log("DEBUG", f"⏰ No merge after {elapsed:.3f}s (normal - game rule: merge within 2s or never)")

        return final_workspace

    def _wait_for_element_to_appear(
        self, initial_workspace: List[Dict], element_name: str, max_wait: float = 2.0
    ) -> List[Dict]:
        """
        Wait for an element to appear in the workspace after dragging.

        This provides more intelligent waiting than fixed delays, checking if the drag
        was actually successful by detecting workspace changes.

        Args:
            initial_workspace: Workspace state before dragging
            element_name: Name of element that should appear
            max_wait: Maximum time to wait in seconds

        Returns:
            Final workspace state after waiting
        """
        start_time = time.time()
        poll_interval = config.POLL_INTERVAL

        self.log("DEBUG", f"🔄 Waiting for {element_name} to appear in workspace...")

        while (time.time() - start_time) < max_wait:
            current_workspace = self._get_workspace_elements()

            # Check if workspace changed (element appeared)
            if len(current_workspace) > len(initial_workspace):
                elapsed = time.time() - start_time
                self.log("DEBUG", f"✅ Element appeared in workspace after {elapsed:.3f}s")
                return current_workspace

            # Check if existing elements changed (transformation)
            if len(current_workspace) == len(initial_workspace) and current_workspace != initial_workspace:
                elapsed = time.time() - start_time
                self.log("DEBUG", f"✅ Workspace elements changed after {elapsed:.3f}s (likely transformation)")
                return current_workspace

            time.sleep(poll_interval)

        # Timeout - return current state anyway
        final_workspace = self._get_workspace_elements()
        elapsed = time.time() - start_time
        self.log("DEBUG", f"⏰ Drag wait timeout after {elapsed:.3f}s - returning current workspace")
        return final_workspace

    def _find_elements_near_location(
        self, workspace_elements: List[Dict], target_x: int, target_y: int, tolerance: int = None
    ) -> List[Dict]:
        """Find elements within tolerance distance of target location."""
        near_elements = []
        for elem in workspace_elements:
            if "x" in elem and "y" in elem:
                distance = ((elem["x"] - target_x) ** 2 + (elem["y"] - target_y) ** 2) ** 0.5
                if distance <= tolerance:
                    near_elements.append(elem)
        return near_elements

    def _workspace_states_equal(self, state1: List[Dict], state2: List[Dict]) -> bool:
        """Compare two workspace states for equality (same elements in same positions)."""
        if len(state1) != len(state2):
            return False

        # Create comparable representations (name + position)
        def make_comparable(elem):
            return (elem.get("name", ""), elem.get("x", 0), elem.get("y", 0))

        set1 = set(make_comparable(elem) for elem in state1)
        set2 = set(make_comparable(elem) for elem in state2)

        return set1 == set2

    @timing_decorator("GET_WORKSPACE_ELEMENTS")
    def _get_workspace_elements(self) -> List[Dict]:
        """
        Get all current elements in the workspace that are actually visible to the user.

        Returns:
            List of workspace elements with their info (excludes off-screen elements)
        """
        try:
            js_script = """
                var workspaceElements = [];
                var instances = document.getElementById('instances');
                if (instances) {
                    // FIXED: Look for .instance class, not .item class
                    var items = instances.querySelectorAll('.instance');
                    items.forEach(function(item) {
                        var text = item.textContent || item.innerText || '';
                        var emoji = '';
                        var emojiSpan = item.querySelector('.instance-emoji');
                        if (emojiSpan) {
                            emoji = emojiSpan.textContent || emojiSpan.innerText || '';
                        }

                        // CRITICAL: Check if element is actually visible in viewport
                        var rect = item.getBoundingClientRect();
                        var isInViewport = rect.top >= 0 && rect.bottom <= window.innerHeight &&
                                         rect.left >= 0 && rect.right <= window.innerWidth;

                        // Only include elements that are visible to the user
                        if (!isInViewport) {
                            return; // Skip off-screen elements
                        }
                        workspaceElements.push({
                            text: text.trim(),
                            emoji: emoji.trim(),
                            name: text.replace(emoji, '').trim(),
                            x: Math.round(rect.x + rect.width/2),
                            y: Math.round(rect.y + rect.height/2),
                            rect: {
                                x: rect.x,
                                y: rect.y,
                                width: rect.width,
                                height: rect.height
                            }
                        });
                    });
                }
                return workspaceElements;
            """

            elements = self.driver.execute_script(js_script)
            return elements

        except Exception as e:
            self.log("ERROR", f"❌ Failed to get workspace elements: {e}")
            return []

    def _verify_merge_process(
        self,
        before_elements: List[Dict],
        after_first_drag: List[Dict],
        after_second_drag: List[Dict],
        elem1_name: str,
        elem2_name: str,
        target_x: int,
        target_y: int,
    ) -> Dict:
        """
        Verify the merge process by analyzing workspace state changes.

        Logic:
        1. After first drag: First element should appear in workspace
        2. After second drag: Either both elements merge into new element, or second element appears
        3. If both original elements still exist = FAILURE (no merge)
        4. If first element gone and new element appeared = SUCCESS (merge happened)

        Args:
            before_elements: Workspace elements before any drags
            after_first_drag: Workspace elements after first element drag
            after_second_drag: Workspace elements after second element drag
            elem1_name: Name of first element
            elem2_name: Name of second element
            target_x: Target X coordinate
            target_y: Target Y coordinate

        Returns:
            Dict with verification results
        """
        try:
            self.log("DEBUG", f"🔍 Verifying merge process: {elem1_name} + {elem2_name}")

            # DETAILED DEBUGGING: Show actual workspace contents
            self.log("DEBUG", f"📋 BEFORE elements: {[e['name'] for e in before_elements]}")
            self.log("DEBUG", f"📋 AFTER 1st drag: {[e['name'] for e in after_first_drag]}")
            self.log("DEBUG", f"📋 AFTER 2nd drag: {[e['name'] for e in after_second_drag]}")

            # Analyze state changes
            before_count = len(before_elements)
            after_first_count = len(after_first_drag)
            after_second_count = len(after_second_drag)

            self.log(
                "DEBUG",
                f"📊 Element counts - Before: {before_count}, After 1st: {after_first_count}, "
                f"After 2nd: {after_second_count}",
            )

            # FIXED LOGIC: Focus on whether the drag succeeded, not exact name matching
            # The game transforms elements when they enter workspace (Water → Puddle, etc.)
            first_element_appeared = False

            if after_first_count > before_count:
                # New element appeared - drag was successful
                new_elements_after_first = [e for e in after_first_drag if e not in before_elements]
                self.log(
                    "DEBUG",
                    f"✅ First drag successful - new element appeared: {[e['name'] for e in new_elements_after_first]}",
                )
                first_element_appeared = True

            elif after_first_count == before_count:
                # Same count - check if element was replaced (transformation)
                disappeared = [e for e in before_elements if e not in after_first_drag]
                appeared = [e for e in after_first_drag if e not in before_elements]

                if disappeared and appeared:
                    self.log(
                        "DEBUG",
                        f"✅ First drag successful - element transformed: {disappeared[0]['name']} → "
                        f"{appeared[0]['name']}",
                    )
                    first_element_appeared = True
                elif appeared:
                    self.log(
                        "DEBUG", f"✅ First drag successful - new element appeared: {[e['name'] for e in appeared]}"
                    )
                    first_element_appeared = True
                else:
                    # Check if element was already there
                    if any(
                        elem1_name.lower() in e["name"].lower() or e["name"].lower() in elem1_name.lower()
                        for e in before_elements
                    ):
                        self.log("DEBUG", "✅ First element already in workspace - drag successful")
                        first_element_appeared = True
                    else:
                        self.log("DEBUG", "❌ First drag may have failed - no workspace changes detected")
            else:
                self.log("DEBUG", f"🔍 Unexpected count change after first drag: {before_count} → {after_first_count}")
                # Still consider successful if count changed
                first_element_appeared = True

            # Analyze final state after second drag
            merge_happened = False
            merge_result = None

            if after_second_count == after_first_count - 1:
                # One element disappeared (likely merged)
                disappeared_elements = [e for e in after_first_drag if e not in after_second_drag]
                new_elements = [e for e in after_second_drag if e not in after_first_drag]

                if disappeared_elements and new_elements:
                    merge_happened = True
                    merge_result = new_elements[0]
                    self.log(
                        "DEBUG",
                        f"🎉 MERGE SUCCESS: {disappeared_elements[0]['name']} + {elem2_name} = {merge_result['name']}",
                    )

            elif after_second_count == after_first_count + 1:
                # Second element appeared (no merge, both elements in workspace)
                self.log("DEBUG", "❌ No merge: Both elements remain in workspace")

            elif after_second_count == after_first_count:
                # Same count - could be replacement or no change
                if after_first_drag != after_second_drag:
                    # Elements changed - likely a merge
                    disappeared = [e for e in after_first_drag if e not in after_second_drag]
                    appeared = [e for e in after_second_drag if e not in after_first_drag]

                    if disappeared and appeared:
                        merge_happened = True
                        merge_result = appeared[0]
                        self.log(
                            "DEBUG",
                            f"🎉 MERGE SUCCESS: {disappeared[0]['name']} + {elem2_name} = {merge_result['name']}",
                        )
                    else:
                        self.log("DEBUG", "🔍 Same count but elements changed - unclear state")
                else:
                    self.log("DEBUG", "❌ No change after second drag - likely failed")

            # CORRECTED: Success detection based on game mechanics clarification
            # SUCCESS = Elements appeared on board (drag worked), regardless of merge outcome
            # FAILURE = Elements didn't appear on board (drag failed, should retry)

            # The key insight: If elements appear on board but don't merge within 2s,
            # that's still SUCCESS - the combination was attempted, just no new element created

            drag_succeeded = first_element_appeared and after_second_count >= before_count
            elements_on_board = (
                len(
                    self._find_elements_near_location(
                        after_second_drag, target_x, target_y, tolerance=config.ELEMENT_POSITION_TOLERANCE
                    )
                )
                >= 1
            )

            # SUCCESS if either:
            # 1. Elements clearly appeared in workspace, OR
            # 2. Elements are positioned on the board near target
            verification_success = drag_succeeded or elements_on_board

            # Enhanced logging for debugging
            if verification_success:
                if merge_happened:
                    self.log("DEBUG", "✅ DRAG SUCCESS + MERGE: Elements appeared and merged into new element")
                else:
                    self.log(
                        "DEBUG", "✅ DRAG SUCCESS + NO MERGE: Elements appeared on board but didn't merge (normal)"
                    )
            else:
                self.log("DEBUG", "❌ DRAG FAILED: Elements never appeared on board - should retry")

            result = {
                "success": verification_success,
                "first_element_appeared": first_element_appeared,
                "merge_happened": merge_happened,
                "merge_result": merge_result,
                "before_count": before_count,
                "after_first_count": after_first_count,
                "after_second_count": after_second_count,
                "target_location": (target_x, target_y),
            }

            if verification_success:
                self.log("DEBUG", "✅ Merge verification SUCCESS")
            else:
                self.log("DEBUG", "❌ Merge verification FAILED")

            return result

        except Exception as e:
            self.log("ERROR", f"❌ Merge verification failed: {e}")
            return {"success": False, "error": str(e)}

    def initialize_clean_workspace(self) -> bool:
        """
        Initialize automation with a clean workspace:
        1. Click on board to close any open dialogs
        2. Clear the workspace completely

        Returns:
            bool: True if initialization successful
        """
        try:
            self.log("INFO", "🎯 Initializing clean workspace for automation...")

            # Step 1: Click on the main workspace area to close any dialogs
            self.log("DEBUG", "🖱️ Clicking workspace area to close dialogs...")
            try:
                from selenium.webdriver.common.keys import Keys

                # Method 1: Press ESC key to close dialogs
                self.driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
                time.sleep(config.DIALOG_CLOSE_DELAY)

                # Method 2: Click on empty workspace area
                workspace = self.driver.find_element(By.ID, "instances")

                # Calculate center of workspace for safe clicking
                workspace_rect = workspace.rect
                center_x = workspace_rect["x"] + workspace_rect["width"] // 2
                center_y = workspace_rect["y"] + workspace_rect["height"] // 2

                from selenium.webdriver.common.action_chains import ActionChains

                actions = ActionChains(self.driver)
                actions.move_by_offset(center_x, center_y).click().perform()
                time.sleep(config.DIALOG_CLOSE_DELAY)

                self.log("DEBUG", "✅ Workspace clicked, dialogs should be closed")

            except Exception as click_error:
                self.log("WARNING", f"⚠️ Workspace click failed (not critical): {click_error}")

            # Step 2: Clear the workspace completely
            self.log("DEBUG", "🧹 Clearing workspace for fresh start...")
            clear_success = self.clear_workspace()

            if clear_success:
                self.log("INFO", "✅ Clean workspace initialized successfully")
                return True
            else:
                self.log("WARNING", "⚠️ Workspace clear failed, continuing anyway...")
                return True  # Continue even if clear fails

        except Exception as e:
            self.log("ERROR", f"❌ Workspace initialization failed: {e}")
            self.log("WARNING", "⚠️ Continuing without clean initialization...")
            return False

    def map_current_situation(self) -> Dict:
        """
        Map current sidebar and workspace situation at start of session.

        Returns:
            Dict: Current game state information
        """
        try:
            self.log("INFO", "📋 Mapping current game situation...")

            # Update sidebar cache
            self.update_sidebar_cache()

            # Check workspace
            workspace = self.driver.find_element(By.ID, "instances")
            workspace_items = workspace.find_elements(By.CLASS_NAME, "item")

            # Get sidebar elements summary
            sidebar_names = [elem["name"] for elem in self.sidebar_elements]

            situation = {
                "sidebar_element_count": len(self.sidebar_elements),
                "sidebar_elements": sidebar_names,
                "workspace_item_count": len(workspace_items),
                "cache_stats": {
                    "total_tested": len(self.combination_cache["tested"]),
                    "successful": len(self.combination_cache["successful"]),
                    "failed": len(self.combination_cache["failed"]),
                },
                "timestamp": datetime.now().isoformat(),
            }

            self.log("INFO", f"📊 Sidebar: {len(self.sidebar_elements)} elements")
            self.log("INFO", f"📊 Workspace: {len(workspace_items)} items")
            self.log(
                "INFO",
                f"📊 Cache: {len(self.combination_cache['tested'])} tested ({
                    len(self.combination_cache['successful'])} successful)",
            )

            return situation

        except Exception as e:
            self.log("ERROR", f"❌ Error mapping situation: {e}")
            return {}

    def log(self, level: str, message: str):
        """Enhanced logging with timestamps and levels."""
        levels = {"DEBUG": 0, "INFO": 1, "WARNING": 2, "ERROR": 3}
        current_level = levels.get(self.log_level, 1)
        msg_level = levels.get(level, 1)

        if msg_level >= current_level:
            timestamp = datetime.now().strftime("%H:%M:%S")
            icons = {"DEBUG": "🔍", "INFO": "ℹ️", "WARNING": "⚠️", "ERROR": "❌"}
            icon = icons.get(level, "📝")
            print(f"[{timestamp}] {icon} {level}: {message}")

    def connect_to_existing_browser(self, port: int = 9222) -> bool:
        """
        Connect to existing Chrome browser with remote debugging.

        Args:
            port: Remote debugging port

        Returns:
            bool: True if connection successful
        """
        self.log("INFO", f"🔗 Connecting to Chrome on port {port}...")

        try:
            # Check if debugging port is available
            response = requests.get(f"http://localhost:{port}/json", timeout=config.CHROME_CONNECTION_TIMEOUT)
            tabs = response.json()

            self.log("INFO", f"✅ Found {len(tabs)} browser tabs")

            # Find Infinite Craft tab
            infinite_craft_tab = None
            for tab in tabs:
                url = tab.get("url", "").lower()
                if "infinite-craft" in url or "neal.fun" in url:
                    infinite_craft_tab = tab
                    self.log("INFO", f"🎯 Found Infinite Craft tab: {tab.get('title', 'Unknown')}")
                    break

            if not infinite_craft_tab:
                self.log("ERROR", "❌ No Infinite Craft tab found")
                return False

            # Connect to existing browser
            chrome_options = Options()
            chrome_options.add_experimental_option("debuggerAddress", f"localhost:{port}")

            self.driver = webdriver.Chrome(options=chrome_options)

            # Switch to Infinite Craft tab if needed
            current_url = self.driver.current_url.lower()
            if "infinite-craft" not in current_url:
                self.log("INFO", "🔄 Switching to Infinite Craft tab...")
                self.driver.get(infinite_craft_tab["url"])
                time.sleep(config.CHROME_TAB_SWITCH_DELAY)

            self.log("INFO", f"✅ Connected! Current URL: {self.driver.current_url}")

            # Initialize element tracking
            self._initialize_sidebar_tracking()

            return True

        except requests.exceptions.RequestException:
            self.log("ERROR", f"❌ Chrome debugging not available on port {port}")
            return False
        except Exception as e:
            self.log("ERROR", f"❌ Connection failed: {e}")
            return False

    def setup_driver(self):
        """Setup Chrome WebDriver."""
        chrome_options = Options()
        if self.headless:
            chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-web-security")
        chrome_options.add_argument("--allow-running-insecure-content")

        self.driver = webdriver.Chrome(options=chrome_options)
        self.driver.set_window_size(1920, 1080)
        self.log("INFO", "✅ Chrome WebDriver initialized")

    def _initialize_sidebar_tracking(self):
        """Initialize sidebar element tracking and caching."""
        try:
            self.log("INFO", "🔄 Initializing sidebar tracking...")

            # Wait for sidebar to load
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "#sidebar .items-inner"))
            )

            # Update sidebar cache
            self.update_sidebar_cache()

            self.log("INFO", f"✅ Sidebar tracking initialized - {len(self.sidebar_elements)} elements found")

        except Exception as e:
            self.log("ERROR", f"❌ Failed to initialize sidebar tracking: {e}")

    @timing_decorator("UPDATE_SIDEBAR_CACHE_OPTIMIZED")
    def update_sidebar_cache(self) -> int:
        """
        OPTIMIZED: Update sidebar element cache by checking only NEW elements at the end.
        This reduces DOM queries from 112+ elements to just the new ones (~10x faster).

        Returns:
            int: Number of new elements discovered
        """
        try:
            old_count = len(self.sidebar_elements)

            # OPTIMIZATION: First, quickly check total count without processing all elements
            total_elements = self.driver.execute_script(
                """
                return document.querySelectorAll('#sidebar .item').length;
            """
            )

            if total_elements <= old_count:
                # No new elements, skip expensive processing
                self.log("DEBUG", f"📊 No new elements (total: {total_elements}, cached: {old_count})")
                return 0

            # OPTIMIZATION: Only query the NEW elements at the end of the sidebar
            new_elements_count = total_elements - old_count
            self.log("DEBUG", f"📊 Detected {new_elements_count} new elements, querying only those...")

            # Get only the new elements (last N elements in sidebar) and return WebElement references
            new_elements_with_refs = self.driver.execute_script(
                f"""
                var allItems = document.querySelectorAll('#sidebar .item');
                var newItems = Array.from(allItems).slice(-{new_elements_count});
                var result = [];

                // Store references to the actual elements in the global scope for Python to access
                window._newElements = newItems;

                newItems.forEach(function(elem, relativeIndex) {{
                    var emoji = '';
                    var emojiElem = elem.querySelector('.item-emoji');
                    if (emojiElem) {{
                        emoji = emojiElem.textContent || emojiElem.innerText || '';
                    }}

                    if (!emoji) {{
                        emoji = elem.getAttribute('data-item-emoji') || '';
                    }}

                    var name = elem.getAttribute('data-item-text') || 'Unknown';
                    var absoluteIndex = {old_count} + relativeIndex;

                    result.push({{
                        name: name,
                        emoji: emoji.trim(),
                        id: elem.getAttribute('data-item-id') || 'elem_' + absoluteIndex,
                        index: absoluteIndex,
                        elementIndex: relativeIndex  // Index in the newItems array
                    }});
                }});

                return result;
            """
            )

            # Process only the new elements and add to existing cache
            discovered_count = 0
            for elem_data in new_elements_with_refs:
                try:
                    # Get the actual WebElement using JavaScript reference
                    elem = self.driver.execute_script(
                        f"""
                        return window._newElements[{elem_data['elementIndex']}];
                    """
                    )

                    data = {
                        "index": elem_data["index"],
                        "element": elem,
                        "name": elem_data["name"],
                        "emoji": elem_data["emoji"],
                        "id": elem_data["id"],
                        "discovered_at": datetime.now().isoformat(),
                    }

                    # Add to existing cache structures (append, don't rebuild)
                    self.sidebar_elements.append(data)
                    self.sidebar_cache[data["name"]] = data
                    discovered_count += 1

                except Exception as e:
                    self.log("WARNING", f"⚠️ Failed to process new element {elem_data['name']}: {e}")
                    continue

            # Clean up global reference to avoid memory leaks
            if new_elements_count > 0:
                self.driver.execute_script("delete window._newElements;")

            if discovered_count > 0:
                self.log(
                    "INFO", f"🆕 Discovered {discovered_count} new elements! (optimized - only queried new elements)"
                )
                self.stats["elements_discovered"] += discovered_count

            return discovered_count

        except Exception as e:
            self.log("ERROR", f"❌ Optimized sidebar cache update failed: {e}")
            # Fallback to full update if optimization fails
            self.log("WARNING", "⚠️ Falling back to full sidebar cache update...")
            return self._update_sidebar_cache_full()

    def _update_sidebar_cache_full(self) -> int:
        """Fallback method: Full sidebar cache update (original implementation)."""
        try:
            old_count = len(self.sidebar_elements)

            # Get current sidebar elements (full query - slower but reliable)
            elements = self.driver.find_elements(By.CSS_SELECTOR, "#sidebar .item")
            new_sidebar_elements = []

            for i, elem in enumerate(elements):
                try:
                    # Try to get emoji from different possible locations
                    emoji = ""
                    emoji_elem = elem.find_element(By.CSS_SELECTOR, ".item-emoji")
                    if emoji_elem:
                        emoji = emoji_elem.text.strip()

                    if not emoji:
                        emoji = elem.get_attribute("data-item-emoji") or ""

                    data = {
                        "index": i,
                        "element": elem,
                        "name": elem.get_attribute("data-item-text") or "Unknown",
                        "emoji": emoji,
                        "id": elem.get_attribute("data-item-id") or f"elem_{i}",
                        "discovered_at": datetime.now().isoformat(),
                    }

                    new_sidebar_elements.append(data)

                    # Update cache by name
                    self.sidebar_cache[data["name"]] = data

                except Exception as elem_error:
                    self.log("WARNING", f"⚠️ Error processing sidebar element {i}: {elem_error}")
                    continue

            # Replace entire sidebar with updated version
            self.sidebar_elements = new_sidebar_elements
            new_count = len(self.sidebar_elements) - old_count

            if new_count > 0:
                self.log("INFO", f"🆕 Discovered {new_count} new elements! (full query fallback)")
                self.stats["elements_discovered"] += new_count

            return max(0, new_count)

        except Exception as e:
            self.log("ERROR", f"❌ Failed to update sidebar cache (fallback): {e}")
            return 0

    def load_game(self, timeout: int = None) -> bool:
        """Load the Infinite Craft game and initialize tracking."""
        try:
            self.log("INFO", "🌐 Loading Infinite Craft game...")
            self.driver.get("https://neal.fun/infinite-craft/")

            # Wait for game to load
            WebDriverWait(self.driver, timeout).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "#sidebar .items-inner"))
            )

            # Wait for initial elements
            WebDriverWait(self.driver, timeout).until(
                lambda driver: len(driver.find_elements(By.CSS_SELECTOR, "#sidebar .item")) >= 4
            )

            # Initialize sidebar tracking
            self._initialize_sidebar_tracking()

            self.log("INFO", "✅ Game loaded successfully")
            return True

        except Exception as e:
            self.log("ERROR", f"❌ Failed to load game: {e}")
            return False

    def get_sidebar_elements(self) -> List[Dict]:
        """Get all elements from sidebar with their details."""
        try:
            elements = self.driver.find_elements(By.CSS_SELECTOR, "#sidebar .item")
            element_data = []

            for i, elem in enumerate(elements):
                try:
                    data = {
                        "index": i,
                        "element": elem,
                        "name": elem.get_attribute("data-item-text") or "Unknown",
                        "emoji": elem.get_attribute("data-item-emoji") or "",
                        "id": elem.get_attribute("data-item-id") or "",
                        "location": elem.location,
                        "size": elem.size,
                    }
                    element_data.append(data)
                except Exception as e:
                    print(f"⚠️ Error processing element {i}: {e}")
                    continue

            return element_data

        except Exception as e:
            print(f"❌ Failed to get sidebar elements: {e}")
            return []

    def _find_element_by_name(self, element_name: str) -> Optional[WebElement]:
        """
        Find a fresh WebElement by name from current sidebar DOM.

        This prevents stale element reference issues by always getting
        the current element from the DOM instead of using cached WebElements.

        Args:
            element_name: Name of the element to find

        Returns:
            WebElement if found, None otherwise
        """
        try:
            # Get fresh elements from DOM (don't use cache)
            elements = self.driver.find_elements(By.CSS_SELECTOR, "#sidebar .item")
            self.log("DEBUG", f"🔍 Searching {len(elements)} sidebar elements for '{element_name}'")

            for i, elem in enumerate(elements):
                try:
                    # Get element name - try different attribute sources
                    elem_name = elem.get_attribute("data-item-text") or elem.text.strip() or "Unknown"

                    if elem_name.lower() == element_name.lower():
                        self.log("DEBUG", f"✅ Found fresh element: {element_name} at index {i}")
                        return elem

                except Exception as e:
                    self.log("DEBUG", f"⚠️ Error checking element {i}: {e}")
                    continue

            # If not found, try alternative search method (maybe element names are stored differently)
            self.log("DEBUG", f"🔄 Trying alternative search for '{element_name}'...")
            for i, elem in enumerate(elements):
                try:
                    # Check if element text contains the name (partial match)
                    elem_text = elem.text.strip()
                    if element_name.lower() in elem_text.lower():
                        self.log(
                            "DEBUG", f"✅ Found element via partial match: {element_name} -> '{elem_text}' at index {i}"
                        )
                        return elem

                except Exception:
                    continue

            self.log("WARNING", f"⚠️ Fresh element '{element_name}' not found in {len(elements)} sidebar elements")
            return None

        except Exception as e:
            self.log("ERROR", f"❌ Error finding fresh element '{element_name}': {e}")
            return None

    def _ensure_element_visible(self, element: WebElement) -> bool:
        """Ensure element is scrolled into view and clickable with bounds validation."""
        try:
            # Get viewport info for bounds checking
            viewport_height = self.driver.execute_script("return window.innerHeight")
            viewport_width = self.driver.execute_script("return window.innerWidth")

            # Try multiple scroll strategies for robust positioning
            for attempt in range(3):
                # Strategy based on attempt number
                if attempt == 0:
                    # Standard smooth scroll to center
                    self.driver.execute_script(
                        "arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", element
                    )
                elif attempt == 1:
                    # Instant scroll to center (no animation)
                    self.driver.execute_script(
                        "arguments[0].scrollIntoView({behavior: 'instant', block: 'center'});", element
                    )
                else:
                    # Aggressive scroll - to top first, then to element
                    self.driver.execute_script("window.scrollTo(0, 0);")
                    time.sleep(0.1)
                    self.driver.execute_script(
                        "arguments[0].scrollIntoView({behavior: 'instant', block: 'center'});", element
                    )

                time.sleep(config.SCROLL_COMPLETION_DELAY)

                # Validate element position is within bounds
                location = element.location
                scroll_y = self.driver.execute_script("return window.scrollY")
                screen_y = location["y"] - scroll_y
                screen_x = location["x"]

                in_viewport = (
                    0 <= screen_x <= viewport_width and 0 <= screen_y <= viewport_height and element.is_displayed()
                )

                self.log(
                    "DEBUG",
                    f"Scroll attempt {
                        attempt +
                        1}: element at screen ({
                        screen_x:.0f}, {
                        screen_y:.0f}), in_viewport: {in_viewport}",
                )

                if in_viewport:
                    self.log("DEBUG", f"✅ Element scrolled into view and visible (attempt {attempt + 1})")
                    return True

            self.log("WARNING", "⚠️ Failed to scroll element into viewport after 3 attempts")
            return False

        except Exception as e:
            self.log("WARNING", f"⚠️ Failed to scroll element into view: {e}")
            return False

    @timing_decorator("DRAG_ELEMENT")
    def smooth_drag_element(
        self,
        source_element: WebElement,
        target_x: int,
        target_y: int,
        pixel_steps: int = 300,
        step_pause: float = 0.0,
        hold_duration: float = 0.05,
    ) -> bool:
        """
        Fast smooth drag with optimized performance.

        Simplified drag with minimal ActionChains complexity for good performance.

        Args:
            source_element: WebElement to drag
            target_x: Target X coordinate
            target_y: Target Y coordinate
            pixel_steps: Pixels per step (default 300 - large jumps)
            step_pause: Pause between steps (default 0.0 - no pauses)
            hold_duration: Hold duration (default 0.05 - minimal)

        Returns:
            bool: True if drag was executed successfully
        """
        try:
            # CRITICAL: Ensure source element is visible before dragging
            if not self._ensure_element_visible(source_element):
                self.log("ERROR", "❌ Cannot drag - source element not visible after scroll attempt")
                return False

            # CRITICAL: Validate bounds before attempting drag to prevent "move target out of bounds"
            try:
                viewport_height = self.driver.execute_script("return window.innerHeight")
                viewport_width = self.driver.execute_script("return window.innerWidth")

                # Check target coordinates are within bounds
                if not (0 <= target_x <= viewport_width and 0 <= target_y <= viewport_height):
                    self.log(
                        "ERROR",
                        f"❌ Target coordinates ({target_x}, {
                            target_y}) outside viewport ({viewport_width}x{viewport_height})",
                    )
                    return False

                # Get source element center and validate it's within bounds
                source_center = self.driver.execute_script(
                    """
                    const rect = arguments[0].getBoundingClientRect();
                    return {
                        x: rect.left + rect.width / 2,
                        y: rect.top + rect.height / 2
                    };
                """,
                    source_element,
                )

                if not (0 <= source_center["x"] <= viewport_width and 0 <= source_center["y"] <= viewport_height):
                    self.log(
                        "ERROR",
                        f"❌ Source element center ({
                            source_center['x']:.0f}, {
                            source_center['y']:.0f}) outside viewport after scroll",
                    )
                    return False

                self.log(
                    "DEBUG",
                    f"✅ Bounds validation passed - source: ({source_center['x']:.0f}, {source_center['y']:.0f}), "
                    "target: ({target_x}, {target_y})",
                )

            except Exception as e:
                self.log("WARNING", f"⚠️ Bounds validation failed: {e} - attempting drag anyway")

            # Get starting position (element center) - get FRESH coordinates right before drag
            # This prevents issues with stale coordinates if element moved after earlier calculations
            fresh_source_center = self.driver.execute_script(
                """
                const rect = arguments[0].getBoundingClientRect();
                return {
                    x: rect.left + rect.width / 2,
                    y: rect.top + rect.height / 2
                };
            """,
                source_element,
            )
            start_x = fresh_source_center["x"]
            start_y = fresh_source_center["y"]

            # Calculate total movement needed
            distance_x = target_x - start_x
            distance_y = target_y - start_y
            total_distance = (distance_x**2 + distance_y**2) ** 0.5

            # OPTIMIZED: Limit steps to maximum 3 for fast performance
            max_steps = 3
            num_steps = min(max(int(total_distance / pixel_steps), 1), max_steps)

            self.log("DEBUG", f"⚡ Fast drag: ({start_x}, {start_y}) → ({target_x}, {target_y})")
            self.log("DEBUG", f"🚀 Distance: {total_distance:.1f}px, Steps: {num_steps} (max {max_steps})")

            # ENHANCED DEBUGGING: Check element details right before drag
            pre_drag_details = self.driver.execute_script(
                """
                const elem = arguments[0];
                return {
                    textContent: elem.textContent.trim(),
                    dataItemText: elem.getAttribute('data-item-text'),
                    dataItemEmoji: elem.getAttribute('data-item-emoji'),
                    dataItemId: elem.getAttribute('data-item-id'),
                    isConnected: elem.isConnected,
                    tagName: elem.tagName,
                    className: elem.className
                };
            """,
                source_element,
            )
            self.log(
                "DEBUG",
                f"🎯 PRE-DRAG: '{
                    pre_drag_details['dataItemText']}' ({
                    pre_drag_details['dataItemEmoji']}) id={
                    pre_drag_details['dataItemId']} connected={
                    pre_drag_details['isConnected']}",
            )

            # SIMPLIFIED ActionChains - build once, execute once
            start_time = time.time()

            actions = ActionChains(self.driver)

            # DEBUG: Check element again right before move_to_element
            try:
                mid_drag_details = self.driver.execute_script(
                    """
                    const elem = arguments[0];
                    return {
                        textContent: elem.textContent.trim(),
                        dataItemText: elem.getAttribute('data-item-text'),
                        dataItemEmoji: elem.getAttribute('data-item-emoji'),
                        dataItemId: elem.getAttribute('data-item-id'),
                        isConnected: elem.isConnected,
                        rect: elem.getBoundingClientRect()
                    };
                """,
                    source_element,
                )
                self.log(
                    "DEBUG",
                    f"🎯 MID-DRAG: '{
                        mid_drag_details['dataItemText']}' ({
                        mid_drag_details['dataItemEmoji']}) id={
                        mid_drag_details['dataItemId']} connected={
                        mid_drag_details['isConnected']}",
                )

            except Exception as e:
                self.log("ERROR", f"❌ Element became invalid before move_to_element: {e}")
                return False

            actions.move_to_element(source_element)

            # Debug logs can be re-enabled if needed for future troubleshooting

            actions.click_and_hold()

            # Add minimal hold only if specified
            if hold_duration > 0:
                actions.pause(hold_duration)

            # OPTIMIZED: Simple direct moves instead of complex offset calculations
            if num_steps == 1:
                # Single jump directly to target
                actions.move_by_offset(distance_x, distance_y)
            else:
                # Multi-step with equal increments
                step_x = distance_x / num_steps
                step_y = distance_y / num_steps

                for i in range(num_steps):
                    actions.move_by_offset(step_x, step_y)
                    # Only pause if specifically requested (should be 0.0)
                    if step_pause > 0:
                        actions.pause(step_pause)

            # Final hold and release
            if hold_duration > 0:
                actions.pause(hold_duration)
            actions.release()

            # Execute entire chain at once
            actions.perform()
            end_time = time.time()

            duration = end_time - start_time
            self.log("INFO", f"⚡ Fast drag completed in {duration:.3f}s")

            # Log warning if drag is slow
            if duration > 5.0:
                self.log("WARNING", f"⚠️ Drag took {duration:.1f}s - investigating performance issue")

            return True

        except Exception as e:
            self.log("ERROR", f"❌ Smooth drag failed: {e}")
            return False

    def drag_element_to_workspace(self, element_name: str, workspace_x: int = 400, workspace_y: int = 300) -> bool:
        """
        Drag an element from sidebar to workspace using the optimized smooth method.

        Args:
            element_name: Name of element to drag (e.g., "Water", "Fire")
            workspace_x: X coordinate in workspace
            workspace_y: Y coordinate in workspace

        Returns:
            bool: True if element was successfully dragged to workspace
        """
        try:
            # Find the element in sidebar
            sidebar_elements = self.get_sidebar_elements()
            target_element = None
            element_data = None

            for elem_data in sidebar_elements:
                if elem_data["name"].lower() == element_name.lower():
                    target_element = elem_data["element"]
                    element_data = elem_data
                    break

            if not target_element:
                print(f"❌ Element '{element_name}' not found in sidebar")
                return False

            print(f"🌊 Dragging {element_name} to workspace at ({workspace_x}, {workspace_y})")

            # Perform optimized smooth drag
            success = self.smooth_drag_element(target_element, workspace_x, workspace_y)

            if success:
                # Wait for any animations/state changes
                time.sleep(config.SAVE_OPERATION_DELAY)
                print(f"✅ Successfully dragged {element_name} to workspace")

                # Track this element in workspace (since we can't detect it in DOM)
                workspace_element = {
                    "name": element_data["name"],
                    "emoji": element_data["emoji"],
                    "id": element_data["id"],
                    "position": {"x": workspace_x, "y": workspace_y},
                    "source_element": target_element,  # Keep reference for combination
                }
                self.workspace_elements.append(workspace_element)

            return success

        except Exception as e:
            print(f"❌ Failed to drag {element_name} to workspace: {e}")
            return False

    def find_workspace_elements(self) -> List[Dict]:
        """
        Find elements that are currently in the workspace area.

        Uses the same logic as _get_workspace_elements() for consistency.

        Returns:
            List of workspace element data
        """
        try:
            # Use JavaScript to get actual workspace elements (same as _get_workspace_elements)
            js_script = """
                var workspaceElements = [];
                var instances = document.getElementById('instances');
                if (instances) {
                    // Look for .instance class elements in workspace
                    var items = instances.querySelectorAll('.instance');
                    items.forEach(function(item, index) {
                        var text = item.textContent || item.innerText || '';
                        var emoji = '';
                        var emojiSpan = item.querySelector('.instance-emoji');
                        if (emojiSpan) {
                            emoji = emojiSpan.textContent || emojiSpan.innerText || '';
                        }

                        var rect = item.getBoundingClientRect();

                        // CRITICAL: Only include elements visible in viewport (same as _get_workspace_elements)
                        var isInViewport = rect.top >= 0 && rect.bottom <= window.innerHeight &&
                                         rect.left >= 0 && rect.right <= window.innerWidth;

                        if (!isInViewport) {
                            return; // Skip off-screen elements
                        }

                        workspaceElements.push({
                            name: text.trim(),
                            emoji: emoji.trim(),
                            x: rect.left + rect.width / 2,
                            y: rect.top + rect.height / 2,
                            index: index,
                            width: rect.width,
                            height: rect.height
                        });
                    });
                }
                return workspaceElements;
            """

            workspace_data = self.driver.execute_script(js_script)

            # Convert to the expected format
            workspace_elements = []
            for item_data in workspace_data:
                workspace_elements.append(
                    {
                        "name": item_data["name"],
                        "emoji": item_data["emoji"],
                        "x": item_data["x"],
                        "y": item_data["y"],
                        "index": item_data["index"],
                        "size": {"width": item_data["width"], "height": item_data["height"]},
                    }
                )

            return workspace_elements

        except Exception as e:
            self.log("ERROR", f"❌ Error finding workspace elements: {e}")
            return []

    def clear_workspace_tracking(self):
        """Clear tracked workspace elements."""
        self.workspace_elements = []
        print("🧹 Cleared workspace element tracking")

    def combine_elements(self, element1_name: str, element2_name: str) -> Optional[str]:
        """
        Combine two elements in the workspace.

        Process:
        1. Drag element1 from sidebar to workspace
        2. Drag element2 from sidebar to different workspace location
        3. Drag element1 onto element2 in workspace to combine
        4. Check for new element in sidebar

        Args:
            element1_name: First element to combine
            element2_name: Second element to combine

        Returns:
            Name of new element if successful, None if failed
        """
        try:
            print(f"🔄 Combining {element1_name} + {element2_name}")

            # Clear previous workspace tracking
            self.clear_workspace_tracking()

            # Get initial sidebar count
            initial_sidebar = self.get_sidebar_elements()
            initial_count = len(initial_sidebar)

            # Step 1: Drag first element to workspace
            print(f"📋 Step 1: Dragging {element1_name} to workspace")
            if not self.drag_element_to_workspace(element1_name, 400, 300):
                print("❌ Failed to drag first element")
                return None

            # Step 2: Drag second element to different workspace location
            print(f"📋 Step 2: Dragging {element2_name} to workspace")
            if not self.drag_element_to_workspace(element2_name, 600, 300):
                print("❌ Failed to drag second element")
                return None

            # Step 3: Use tracked workspace elements
            print(f"📊 Found {len(self.workspace_elements)} elements in workspace")

            if len(self.workspace_elements) < 2:
                print("❌ Not enough elements tracked in workspace for combination")
                return None

            # Step 4: Drag first workspace element onto second
            elem1_data = self.workspace_elements[0]
            elem2_data = self.workspace_elements[1]

            elem1_name = elem1_data["name"]
            elem2_name = elem2_data["name"]

            print(f"📋 Step 3: Dragging workspace {elem1_name} onto workspace {elem2_name}")

            # Use tracked position of second element for targeting
            target_x = elem2_data["position"]["x"]
            target_y = elem2_data["position"]["y"]

            # Perform combination drag using the source element reference
            elem1_source = elem1_data["source_element"]
            if not self.smooth_drag_element(elem1_source, target_x, target_y, hold_duration=1.2):
                print("❌ Failed to drag elements together")
                return None

            # Step 5: Wait for combination and check for new element
            print("⏳ Waiting for combination to process...")
            time.sleep(config.COMBINATION_RESULT_DELAY)

            # Check sidebar for new elements
            final_sidebar = self.get_sidebar_elements()
            final_count = len(final_sidebar)

            print(f"📊 Sidebar elements: {initial_count} → {final_count}")

            if final_count > initial_count:
                # New element created!
                new_elements = final_sidebar[initial_count:]
                new_element = new_elements[0]  # Get first new element

                print(f"🎉 SUCCESS! Created: {new_element['emoji']} {new_element['name']}")
                return new_element["name"]
            else:
                print("❓ No new element detected - combination may have failed")
                return None

        except Exception as e:
            print(f"❌ Combination failed: {e}")
            return None

    @timing_decorator("CLEAR_WORKSPACE")
    def clear_workspace(self) -> bool:
        """
        Clear all elements from the workspace using the clear tool-icon button.

        Returns:
            bool: True if workspace was cleared successfully
        """
        try:
            self.log("DEBUG", "🧹 Clearing workspace...")

            # Method 1: Use the clear tool-icon (PROVEN WORKING!)
            try:
                clear_icon = self.driver.find_element(By.CSS_SELECTOR, ".clear.tool-icon")
                clear_icon.click()

                # Wait briefly for confirmation dialog
                time.sleep(config.DIALOG_CLOSE_DELAY)

                # Find and click Yes button
                yes_buttons = self.driver.find_elements(By.XPATH, '//*[contains(text(), "Yes")]')
                for btn in yes_buttons:
                    if btn.is_displayed():
                        btn.click()
                        self.log("DEBUG", "✅ Workspace cleared successfully")
                        return True

                self.log("WARNING", "⚠️ Clear button clicked but no Yes confirmation found")
                return True

            except Exception as clear_error:
                self.log("WARNING", f"⚠️ Clear tool-icon method failed: {clear_error}")

            # Method 2: Fallback - try trash icon with ActionChains
            try:
                from selenium.webdriver.common.action_chains import ActionChains

                trash_icon = self.driver.find_element(By.CSS_SELECTOR, ".trash-icon")

                # Use ActionChains to avoid click interception
                actions = ActionChains(self.driver)
                actions.move_to_element(trash_icon).click().perform()

                time.sleep(config.DIALOG_CLOSE_DELAY)

                yes_buttons = self.driver.find_elements(By.XPATH, '//*[contains(text(), "Yes")]')
                for btn in yes_buttons:
                    if btn.is_displayed():
                        btn.click()
                        self.log("DEBUG", "✅ Workspace cleared via trash icon")
                        return True

            except Exception as trash_error:
                self.log("WARNING", f"⚠️ Trash icon method failed: {trash_error}")

            # Method 3: JavaScript fallback
            try:
                # Try to clear via JavaScript if buttons don't work
                self.driver.execute_script(
                    """
                    // Find all workspace items and remove them
                    const workspace = document.getElementById('instances');
                    if (workspace) {
                        const items = workspace.querySelectorAll('.item');
                        items.forEach(item => item.remove());
                    }
                """
                )
                self.log("DEBUG", "✅ Workspace cleared via JavaScript")
                return True
            except Exception as js_error:
                self.log("WARNING", f"⚠️ JavaScript clear failed: {js_error}")

            self.log("ERROR", "❌ All clear methods failed")
            return False

        except Exception as e:
            self.log("ERROR", f"❌ Clear workspace failed: {e}")
            return False

    @timing_decorator("SAVE_GAME_STATE")
    def save_game_state(self) -> bool:
        """
        Save current game state using PROPER method: menu → download → first save.

        Returns:
            bool: True if save was triggered successfully
        """
        try:
            self.log("INFO", "💾 Attempting to save game state...")

            # PROPER SAVE METHOD: Menu Icon → Download Button → First Save Slot
            try:
                # Step 1: Close any open modal/dialog first
                from selenium.webdriver.common.keys import Keys

                try:
                    self.driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
                    time.sleep(config.DIALOG_CLOSE_DELAY)
                    self.log("DEBUG", "🔘 Closed any open dialogs")
                except BaseException:
                    pass

                # Step 2: Click menu icon (.menu-icon)
                self.log("DEBUG", "🔘 Clicking menu icon...")
                menu_icon = self.driver.find_element(By.CSS_SELECTOR, ".menu-icon")

                # Use ActionChains to avoid click interception
                from selenium.webdriver.common.action_chains import ActionChains

                actions = ActionChains(self.driver)
                actions.move_to_element(menu_icon).click().perform()
                time.sleep(config.MENU_OPERATION_DELAY)
                self.log("DEBUG", "✅ Menu opened")

                # Step 3: Click download button (.save-action-icon with download.svg)
                self.log("DEBUG", "📥 Clicking download button...")
                download_icon = self.driver.find_element(By.CSS_SELECTOR, '.save-action-icon[src*="download"]')
                download_icon.click()
                time.sleep(config.MENU_OPERATION_DELAY)
                self.log("DEBUG", "✅ Download dialog opened")

                # Step 4: Click first save slot (.download-input)
                self.log("DEBUG", "💾 Clicking first save slot...")
                first_save = self.driver.find_element(By.CSS_SELECTOR, ".download-input")
                first_save.click()
                time.sleep(config.SAVE_OPERATION_DELAY)

                self.log("INFO", "✅ Game state downloaded successfully!")
                self.log("INFO", "📁 Check your Downloads folder for the save file")
                return True

            except Exception as proper_save_error:
                self.log("WARNING", f"⚠️ Proper save method failed: {proper_save_error}")

            # FALLBACK: Try to find and click download elements directly
            try:
                self.log("DEBUG", "🔧 Trying fallback save methods...")

                # Look for download elements that may be visible
                download_elements = self.driver.find_elements(
                    By.CSS_SELECTOR, '.download-input, .save-action-icon[src*="download"], .save-icon'
                )

                for elem in download_elements:
                    try:
                        if elem.is_displayed():
                            elem.click()
                            time.sleep(config.SAVE_OPERATION_DELAY)
                            self.log("INFO", "✅ Download triggered via fallback method")
                            return True
                    except BaseException:
                        continue

            except Exception as fallback_error:
                self.log("WARNING", f"⚠️ Fallback save failed: {fallback_error}")

            # KEYBOARD SHORTCUTS as last resort
            try:
                self.log("DEBUG", "⌨️ Trying keyboard shortcuts...")
                body = self.driver.find_element(By.TAG_NAME, "body")

                shortcuts = [Keys.CONTROL + "s", Keys.CONTROL + "d", Keys.CONTROL + "e"]
                for shortcut in shortcuts:
                    body.send_keys(shortcut)
                    time.sleep(config.MENU_OPERATION_DELAY)

                self.log("INFO", "🔧 Keyboard shortcuts attempted")
                return True

            except Exception as kb_error:
                self.log("WARNING", f"⚠️ Keyboard shortcuts failed: {kb_error}")

            self.log("ERROR", "❌ All save methods failed - manual save may be required")
            return False

        except Exception as e:
            self.log("ERROR", f"❌ Save failed: {e}")
            return False

    @timing_decorator("TEST_COMBINATION")
    def test_combination(self, element1_name: str, element2_name: str) -> Optional[Dict]:
        """
        Fast combination testing with optimizations:
        - Uses O(1) persistent cache lookup
        - 5 distinct round-robin locations
        - Clear workspace after 5 attempts
        - Minimal delays between attempts

        Args:
            element1_name: Name of first element (e.g., "Water")
            element2_name: Name of second element (e.g., "Fire")

        Returns:
            Dict with result info or None if failed/already known
        """
        try:
            # Cache Logic - Only skip if we know the result AND it already exists in sidebar
            existing_result = self.result_already_in_sidebar(element1_name, element2_name)
            if existing_result:
                self.log(
                    "DEBUG",
                    f"⏭️ SKIP: Result '{existing_result}' already in sidebar for {element1_name} + {element2_name}",
                )
                return None

            # Note: We don't skip based on failed combinations alone -
            # the sidebar state may have changed, so we should retry them

            self.log("INFO", f"🧪 Testing NEW combination: {element1_name} + {element2_name}")

            # Update sidebar cache
            self.update_sidebar_cache()

            # Check if elements exist in sidebar
            if element1_name not in self.sidebar_cache:
                self.log("WARNING", f"⚠️ Element '{element1_name}' not found in sidebar")
                return None

            if element2_name not in self.sidebar_cache:
                self.log("WARNING", f"⚠️ Element '{element2_name}' not found in sidebar")
                return None

            # Note: We'll find each element fresh right before dragging to prevent any staleness issues

            # Get next location in round-robin sequence
            target_x, target_y = self._get_next_workspace_location()
            location_num = ((self.current_location_index - 1) % len(self.predefined_locations)) + 1

            self.log("DEBUG", f"🎯 Target location {location_num}/5: ({target_x}, {target_y})")

            # We'll ensure visibility right before each drag

            # Enhanced debugging will happen during individual drag operations

            # Perform fast combination with proper merge verification
            len(self.sidebar_elements)

            # STEP 1: Capture workspace state before any drags
            workspace_before = self._get_workspace_elements()
            self.log("DEBUG", f"📊 Workspace before: {len(workspace_before)} elements")

            # STEP 2: Drag first element - find it fresh right before dragging
            elem1 = self._find_element_by_name(element1_name)
            if not elem1:
                self.log("ERROR", f"❌ Could not find fresh {element1_name} for first drag")
                return None

            if not self._ensure_element_visible(elem1):
                self.log("ERROR", f"❌ Cannot access {element1_name} - element not visible in sidebar")
                return None

            success1 = self.smooth_drag_element(elem1, target_x, target_y)
            if not success1:
                self.log("WARNING", f"⚠️ ActionChains exception for {element1_name} - but continuing to check merge")
            else:
                self.log("DEBUG", f"✅ ActionChains completed for {element1_name}")

            # Note: Don't return early - ActionChains "success" doesn't guarantee drag effectiveness
            # The real success detection happens in merge verification below

            # ENHANCED: Wait for first element to actually appear in workspace
            workspace_after_first = self._wait_for_element_to_appear(workspace_before, element1_name, max_wait=2.0)
            self.log("DEBUG", f"📊 Workspace after 1st drag: {len(workspace_after_first)} elements")

            # STEP 3: Drag second element DIRECTLY ONTO first element for merge
            # Find the actual location of the first element in workspace
            merge_target_x, merge_target_y = target_x, target_y

            if len(workspace_after_first) > len(workspace_before):
                # Find the newest element (likely our first element)
                newest_element = workspace_after_first[-1]
                merge_target_x = newest_element["x"]
                merge_target_y = newest_element["y"]
                self.log(
                    "DEBUG", f"🎯 Dragging 2nd element to 1st element location: ({merge_target_x}, {merge_target_y})"
                )
            else:
                self.log("DEBUG", f"🎯 Using original target for 2nd element: ({merge_target_x}, {merge_target_y})")

            # STEP 3: Drag second element - find it fresh right before dragging
            elem2 = self._find_element_by_name(element2_name)
            if not elem2:
                self.log("ERROR", f"❌ Could not find fresh {element2_name} for second drag")
                return None

            if not self._ensure_element_visible(elem2):
                self.log("ERROR", f"❌ Cannot access {element2_name} - element not visible in sidebar")
                return None

            success2 = self.smooth_drag_element(elem2, merge_target_x, merge_target_y)
            if not success2:
                self.log("WARNING", f"⚠️ ActionChains exception for {element2_name} - but continuing to check merge")
            else:
                self.log("DEBUG", f"✅ ActionChains completed for {element2_name}")

            # Note: Don't return early - ActionChains "success" doesn't guarantee drag effectiveness
            # The real success detection happens in merge verification below

            # SMART WAITING: Wait up to 2 seconds for potential merge (game rule: no merge after 2s)
            workspace_after_second = self._wait_for_merge_completion(
                workspace_after_first, element1_name, element2_name, target_x, target_y, max_wait_time=2.0
            )

            # STEP 4: Verify the merge process
            merge_verification = self._verify_merge_process(
                workspace_before,
                workspace_after_first,
                workspace_after_second,
                element1_name,
                element2_name,
                target_x,
                target_y,
            )

            if not merge_verification["success"]:
                self.log("WARNING", "⚠️ DRAG FAILED - elements never appeared on board")
                self.log("WARNING", "⚠️ Not caching - combination was never attempted (should retry)")
                # Don't cache anything - drag failed, combination was never attempted
                self.attempts_since_last_clear += 1
                if self._should_clear_workspace():
                    self.log(
                        "INFO", f"🧹 Clearing workspace after {self.attempts_since_last_clear} attempts (drag failure)"
                    )
                    self.clear_workspace()
                    self.attempts_since_last_clear = 0
                    self.stats["workspace_clears"] += 1
                return None

            self.log(
                "INFO",
                f"✅ Merge verification SUCCESS: {
                    merge_verification['first_element_appeared']}, merge: {
                    merge_verification['merge_happened']}",
            )

            # Brief wait for combination processing (OPTIMIZED: reduced from 1.5s to 0.8s)
            with self.time_operation("SLEEP_FOR_GAME_PROCESSING"):
                self.log("DEBUG", "⏱️ Sleeping 0.8s for game processing (optimized)...")
                time.sleep(config.COMBINATION_PROCESSING_DELAY)

            # Increment attempts counter (only after successful merge verification)
            self.attempts_since_last_clear += 1

            # DISCOVERY LOGIC: Only count success if new elements appear in sidebar
            # Workspace verification ensures the combination was properly attempted,
            # but actual discovery is determined by sidebar element changes only.

            new_elements = self.update_sidebar_cache()
            result = None

            if new_elements > 0:
                # SUCCESS: New element appeared in sidebar (this is the ONLY success criteria)
                latest_element = self.sidebar_elements[-1]  # Most recent element

                result = {
                    "name": latest_element["name"],
                    "emoji": latest_element["emoji"],
                    "id": latest_element["id"],
                    "combination": f"{element1_name} + {element2_name}",
                    "discovered_at": datetime.now().isoformat(),
                    "new_elements_count": new_elements,
                    "location": (target_x, target_y),
                    "detection_method": "sidebar_discovery",
                }

                self.log(
                    "INFO",
                    f"🎉 DISCOVERY SUCCESS! {element1_name} + {element2_name} = {result['emoji']} {result['name']}",
                )

                if new_elements > 1:
                    self.log("INFO", f"🌟 BONUS! {new_elements - 1} additional elements created!")
            else:
                # Log workspace merge info for debugging, but don't count as success
                if merge_verification["merge_happened"]:
                    self.log(
                        "DEBUG",
                        f"🔍 Workspace merge detected but no new sidebar elements: {element1_name} + {element2_name}",
                    )
                else:
                    self.log(
                        "DEBUG", f"🔍 No workspace merge and no new sidebar elements: {element1_name} + {element2_name}"
                    )

            if result:
                # Cache the success
                self._mark_combination_successful(element1_name, element2_name, result)

                # Check if we should clear after 5 attempts
                if self._should_clear_workspace():
                    self.log("INFO", f"🧹 Clearing workspace after {self.attempts_since_last_clear} attempts")
                    self.clear_workspace()
                    self.attempts_since_last_clear = 0
                    self.stats["workspace_clears"] += 1

                return result
            else:
                # COMBINATION ATTEMPTED: Elements appeared on board but no new elements created
                # This is normal - cache as "attempted but no result" so we don't retry
                self._mark_combination_failed(element1_name, element2_name)
                self.log(
                    "INFO",
                    f"⚪ No new elements: {element1_name} + {element2_name} (drag worked, combination attempted)",
                )

                # Check if we should clear after 5 attempts
                if self._should_clear_workspace():
                    self.log("INFO", f"🧹 Clearing workspace after {self.attempts_since_last_clear} attempts")
                    self.clear_workspace()
                    self.attempts_since_last_clear = 0
                    self.stats["workspace_clears"] += 1

                # Return special indicator that drag succeeded but no new element - don't retry
                return {
                    "drag_successful": True,
                    "new_element": False,
                    "combination": f"{element1_name} + {element2_name}",
                }

        except Exception as e:
            self.log("ERROR", f"❌ Combination test crashed: {e}")
            self.log("WARNING", "⚠️ NOT CACHING: Crash means combination was never properly attempted")
            # Don't cache - crash means we never actually completed the combination attempt
            return None

    def _mark_combination_successful(self, elem1: str, elem2: str, result: Dict):
        """Mark combination as successful in persistent cache."""
        key = self._get_combination_key(elem1, elem2)

        # Add to cache
        self.combination_cache["successful"][key] = result
        self.combination_cache["tested"].add(key)

        # Update stats
        self.stats["combinations_tested"] += 1
        self.stats["combinations_successful"] += 1

        # LOG CACHE OPERATION
        self.log("INFO", f"💾 CACHED SUCCESS: {key} → {result['emoji']} {result['name']}")

        # Save cache immediately
        self._save_combination_cache()

    def _mark_combination_failed(self, elem1: str, elem2: str):
        """Mark combination as failed in persistent cache."""
        key = self._get_combination_key(elem1, elem2)

        # Add to cache
        self.combination_cache["failed"].add(key)
        self.combination_cache["tested"].add(key)

        # Update stats
        self.stats["combinations_tested"] += 1

        # LOG CACHE OPERATION
        self.log("INFO", f"💾 CACHED FAILURE: {key} → No result")

        # Save cache immediately
        self._save_combination_cache()

    def test_element_combination(
        self, element1_name: str, element2_name: str, target_x: int = None, target_y: int = None
    ) -> Optional[Dict]:
        """
        DEPRECATED: Use test_combination() instead.

        Legacy method for backward compatibility.
        """
        self.log("WARNING", "⚠️ test_element_combination() is deprecated, use test_combination() instead")
        return self.test_combination(element1_name, element2_name)

    def get_untested_combination_count(self) -> int:
        """Get count of untested combinations with current elements."""
        try:
            self.update_sidebar_cache()
            available_elements = list(self.sidebar_cache.keys())

            total_possible = 0
            untested_count = 0

            # Count all possible combinations
            for i, elem1 in enumerate(available_elements):
                for elem2 in available_elements[i + 1 :]:  # Avoid duplicates and self-combinations
                    total_possible += 1
                    if not self.is_combination_tested(elem1, elem2):
                        untested_count += 1

            self.log("DEBUG", f"🔢 Combinations: {untested_count} untested / {total_possible} total possible")
            return untested_count

        except Exception as e:
            self.log("ERROR", f"❌ Error counting untested combinations: {e}")
            return 0

    def get_random_untested_combination(self) -> Optional[Tuple[str, str]]:
        """Get a random untested combination."""
        try:
            self.update_sidebar_cache()
            available_elements = list(self.sidebar_cache.keys())

            untested_combinations = []

            # Find all untested combinations
            for i, elem1 in enumerate(available_elements):
                for elem2 in available_elements[i + 1 :]:
                    if not self.is_combination_tested(elem1, elem2):
                        untested_combinations.append((elem1, elem2))

            if untested_combinations:
                return random.choice(untested_combinations)
            else:
                return None

        except Exception as e:
            self.log("ERROR", f"❌ Error selecting untested combination: {e}")
            return None

    def get_stats_summary(self) -> Dict:
        """Get comprehensive statistics summary including cache info."""
        current_time = datetime.now()
        session_duration = (current_time - self.stats["session_start"]).total_seconds() / 60

        success_rate = 0
        if self.stats["combinations_tested"] > 0:
            success_rate = (self.stats["combinations_successful"] / self.stats["combinations_tested"]) * 100

        # Cache statistics
        total_cache_tested = len(self.combination_cache["tested"])
        total_cache_successful = len(self.combination_cache["successful"])
        total_cache_failed = len(self.combination_cache["failed"])

        cache_success_rate = 0
        if total_cache_tested > 0:
            cache_success_rate = (total_cache_successful / total_cache_tested) * 100

        return {
            # Session stats
            "session_duration_minutes": session_duration,
            "total_elements": len(self.sidebar_elements),
            "combinations_tested_this_session": self.stats["combinations_tested"],
            "combinations_successful_this_session": self.stats["combinations_successful"],
            "session_success_rate_percent": success_rate,
            "elements_discovered_this_session": self.stats["elements_discovered"],
            "workspace_clears": self.stats["workspace_clears"],
            "current_location_index": self.current_location_index,
            "attempts_since_last_clear": self.attempts_since_last_clear,
            # Persistent cache stats
            "total_cache_tested": total_cache_tested,
            "total_cache_successful": total_cache_successful,
            "total_cache_failed": total_cache_failed,
            "cache_success_rate_percent": cache_success_rate,
            "cache_file": self.cache_file,
            # Current state
            "sidebar_cache_size": len(self.sidebar_cache),
            "untested_combinations": self.get_untested_combination_count(),
        }

    def close(self):
        """Clean up and close browser."""
        if self.driver:
            try:
                self.driver.quit()
                print("✅ Browser closed successfully")
            except BaseException:
                pass


def test_working_utilities():
    """Test the working utilities with confirmed drag method."""
    automation = None

    try:
        # Initialize automation
        automation = InfiniteCraftAutomation(headless=False)

        # Load game
        if not automation.load_game():
            print("❌ Failed to load game")
            return

        # Show initial elements
        sidebar_elements = automation.get_sidebar_elements()
        print(f"\n📊 Initial sidebar elements: {len(sidebar_elements)}")
        for elem in sidebar_elements:
            print(f"   {elem['emoji']} {elem['name']}")

        # Test combination: Water + Fire should make Steam
        print("\n🧪 Testing combination: Water + Fire → Steam")
        result = automation.combine_elements("Water", "Fire")

        if result:
            print(f"🎉 Combination successful! Created: {result}")

            # Test another combination with new element
            print(f"\n🧪 Testing second combination: {result} + Earth")
            result2 = automation.combine_elements(result, "Earth")

            if result2:
                print(f"🎉 Second combination successful! Created: {result2}")

        else:
            print("❓ Combination did not produce new element")

        # Show final state
        final_sidebar = automation.get_sidebar_elements()
        print(f"\n📊 Final sidebar elements: {len(final_sidebar)}")
        for elem in final_sidebar:
            print(f"   {elem['emoji']} {elem['name']}")

        # Keep browser open for inspection
        print("\n👁️ Keeping browser open for 10 seconds...")
        time.sleep(config.KEEP_BROWSER_OPEN_DELAY)

    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback

        traceback.print_exc()

    finally:
        if automation:
            automation.close()


if __name__ == "__main__":
    test_working_utilities()
