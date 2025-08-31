#!/usr/bin/env python3
"""
Infinite Craft Complete Automation Script
=========================================

This script provides complete automation for the Infinite Craft web game,
using the enhanced utilities from infinite_craft.py.

REQUIREMENTS:
1. Run ./launch_chrome_debug.sh first to start Chrome with remote debugging
2. Ensure Chrome is on https://neal.fun/infinite-craft/
3. Run: python infinite_craft_automation.py

FEATURES:
- Ultra-fast pixel-by-pixel smooth dragging
- Comprehensive sidebar element tracking and caching
- Combination result caching with success/failure tracking
- Enhanced logging with timestamps and levels
- Workspace management and cleaning
- Advanced save state detection via menu buttons
- Target: Create 20 new elements and save state

Author: AI Assistant  
Date: January 2025
"""

import time
from datetime import datetime
from typing import Dict, Optional

# Import our enhanced utilities
from utils import InfiniteCraftAutomation


class AutomationController:
    """
    Generic automation controller that uses InfiniteCraftAutomation utilities.
    
    Can be configured for different automation strategies:
    - Element discovery (create N new elements)
    - Combination exploration (test specific combinations)
    - Achievement hunting (target specific elements)
    - And more...
    """
    
    def __init__(self, strategy_config: Dict = None, log_level: str = "INFO"):
        """
        Initialize automation controller with flexible configuration.
        
        Args:
            strategy_config: Configuration dict for automation strategy
                           Defaults to discovery strategy with 20 elements
            log_level: Logging level for utilities
        """
        self.automation = InfiniteCraftAutomation(headless=False, log_level=log_level)
        
        # Default strategy: Element Discovery
        default_config = {
            'type': 'element_discovery',
            'target_new_elements': 20,
            'max_attempts_between_success': 50,
            'save_on_completion': True,
            'clear_workspace_on_start': True
        }
        
        self.config = {**default_config, **(strategy_config or {})}
        self.session_start = datetime.now()
        
        # Progress tracking (generic)
        self.elements_created_this_session = 0
        self.attempts_since_last_success = 0
        
        # Extract strategy-specific config
        self.target_new_elements = self.config.get('target_new_elements', 20)
        self.max_attempts_between_success = self.config.get('max_attempts_between_success', 50)
    
    def log(self, level: str, message: str):
        """Enhanced logging wrapper."""
        self.automation.log(level, message)
    
    def connect_to_browser(self, port: int = 9222) -> bool:
        """
        Connect to existing Chrome browser with remote debugging enabled.
        
        Returns:
            bool: True if connection successful
        """
        return self.automation.connect_to_existing_browser(port)
    
    def _try_combination_with_retry(self, word1: str, word2: str, max_retries: int = 3) -> Optional[Dict]:
        """
        Try a combination with retry mechanism for failed drag operations.
        
        This is a shared method that can be used by all automation types to
        prevent code divergence and ensure consistent retry behavior.
        
        Args:
            word1: First element name
            word2: Second element name
            max_retries: Maximum number of retry attempts
            
        Returns:
            Dict with result info if successful, None if all attempts failed
        """
        for attempt in range(max_retries):
            attempt_num = attempt + 1
            
            if attempt > 0:
                self.log("INFO", f"🔄 Retry attempt {attempt_num}/{max_retries} for {word1} + {word2}")
                # Brief pause between retries to let the game stabilize
                time.sleep(0.5)
            
            try:
                result = self.automation.test_combination(word1, word2)
                
                if result is not None:
                    # Success! 
                    if attempt > 0:
                        self.log("INFO", f"✅ Retry successful on attempt {attempt_num}")
                    return result
                else:
                    # Failed - but could be drag failure or legitimate "no result"
                    if attempt < max_retries - 1:  # Not the last attempt
                        self.log("WARNING", f"⚠️ Attempt {attempt_num} failed for {word1} + {word2} - will retry")
                    else:
                        self.log("WARNING", f"❌ All {max_retries} attempts failed for {word1} + {word2}")
                        
            except Exception as e:
                self.log("ERROR", f"💥 Exception during attempt {attempt_num} for {word1} + {word2}: {e}")
                if attempt < max_retries - 1:
                    self.log("INFO", f"🔄 Will retry after exception...")
                    time.sleep(1.0)  # Longer pause after exceptions
        
        # All attempts failed
        return None
    
    def run_discovery_session(self) -> Dict:
        """
        Main discovery session - create target number of new elements.
        This implements the 'element_discovery' strategy.
        
        Returns:
            Dict: Session results and statistics
        """
        strategy_type = self.config.get('type', 'element_discovery')
        self.log("INFO", f"🚀 Starting Automation Session")
        self.log("INFO", f"📋 Strategy: {strategy_type}")
        self.log("INFO", f"🎯 Target: {self.target_new_elements} new elements")
        self.log("INFO", "=" * 60)
        
        session_results = {
            'target_elements': self.target_new_elements,
            'elements_created': 0,
            'combinations_tested': 0,
            'success_rate': 0.0,
            'session_duration_minutes': 0,
            'discoveries': [],
            'final_element_count': 0
        }
        
        try:
            # STEP 1: Initialize workspace if configured to do so
            if self.config.get('clear_workspace_on_start', True):
                self.log("INFO", "📋 Step 1: Initializing clean workspace...")
                init_success = self.automation.initialize_clean_workspace()
                if not init_success:
                    self.log("WARNING", "⚠️ Workspace initialization had issues, continuing anyway...")
            
            # STEP 2: Map current situation
            self.log("INFO", "📋 Step 2: Mapping current game situation...")
            initial_situation = self.automation.map_current_situation()
            initial_element_count = initial_situation['sidebar_element_count']
            
            # STEP 3: Start discovery session
            self.log("INFO", "📋 Step 3: Starting element discovery session...")
            
            # Discovery loop
            while self.elements_created_this_session < self.target_new_elements:
                
                # Check if we've tried too many combinations without success
                if self.attempts_since_last_success >= self.max_attempts_between_success:
                    self.log("WARNING", f"⚠️ Reached {self.max_attempts_between_success} attempts without success")
                    break
                
                # Select two random elements for combination
                element_pair = self._select_combination_pair()
                if not element_pair:
                    self.log("WARNING", "⚠️ No more element pairs to test")
                    break
                
                element1, element2 = element_pair
                
                # Test the combination using retry mechanism
                result = self._try_combination_with_retry(element1, element2, max_retries=3)
                
                if result:
                    # Success! New element created
                    self.elements_created_this_session += result.get('new_elements_count', 1)
                    self.attempts_since_last_success = 0
                    
                    session_results['discoveries'].append({
                        'combination': result['combination'],
                        'result': f"{result['emoji']} {result['name']}",
                        'created_at': result['discovered_at'],
                        'bonus_elements': result['new_elements_count'] - 1
                    })
                    
                    # Progress update
                    progress = (self.elements_created_this_session / self.target_new_elements) * 100
                    self.log("INFO", f"📈 Progress: {self.elements_created_this_session}/{self.target_new_elements} ({progress:.1f}%)")
                    
                    # NO SLEEP - continue immediately
                    
                else:
                    # No result - increment attempt counter
                    self.attempts_since_last_success += 1
                
                # NO SLEEP between attempts - maximum speed!
                
                # Periodic progress update
                if self.automation.stats['combinations_tested'] % 10 == 0:
                    current_stats = self.automation.get_stats_summary()
                    self.log("INFO", f"⏱️ Session: {current_stats['combinations_tested_this_session']} tested, "
                                    f"Cache: {current_stats['total_cache_tested']} total, "
                                    f"Untested: {current_stats['untested_combinations']}, "
                                    f"Success: {current_stats['session_success_rate_percent']:.1f}%")
            
            # Final statistics
            final_stats = self.automation.get_stats_summary()
            session_duration = (datetime.now() - self.session_start).total_seconds() / 60
            
            session_results.update({
                'elements_created': self.elements_created_this_session,
                'combinations_tested': final_stats['combinations_tested_this_session'],
                'success_rate': final_stats['session_success_rate_percent'],
                'session_duration_minutes': session_duration,
                'final_element_count': final_stats['total_elements'],
                'total_cache_tested': final_stats['total_cache_tested'],
                'untested_combinations': final_stats['untested_combinations'],
                'workspace_clears': final_stats['workspace_clears'],
                'location_index': final_stats['current_location_index']
            })
            
            self._print_session_summary(session_results)
            
            return session_results
            
        except Exception as e:
            self.log("ERROR", f"❌ Discovery session failed: {e}")
            return session_results
    
    def _select_combination_pair(self) -> Optional[tuple]:
        """
        Select two elements for combination testing using O(1) cache lookup.
        
        Returns:
            Tuple of (element1_name, element2_name) or None if no untested pairs
        """
        try:
            # Use the efficient untested combination method
            untested_pair = self.automation.get_random_untested_combination()
            
            if untested_pair:
                return untested_pair
            else:
                self.log("INFO", "🎯 All available combinations have been tested!")
                return None
            
        except Exception as e:
            self.log("ERROR", f"❌ Error selecting combination pair: {e}")
            return None
    
    def _print_session_summary(self, results: Dict):
        """Print formatted session summary with cache statistics."""
        self.log("INFO", "\n" + "=" * 60)
        self.log("INFO", "🎯 DISCOVERY SESSION COMPLETE")
        self.log("INFO", "=" * 60)
        
        # Session statistics
        self.log("INFO", f"⏱️  Duration: {results['session_duration_minutes']:.1f} minutes")
        self.log("INFO", f"🎯 Target: {results['target_elements']} new elements")
        self.log("INFO", f"🎉 Created: {results['elements_created']} new elements")
        self.log("INFO", f"📊 Final Element Count: {results['final_element_count']}")
        
        # Testing statistics
        self.log("INFO", f"\n📊 TESTING STATISTICS:")
        self.log("INFO", f"   🧪 Combinations Tested (Session): {results['combinations_tested']}")
        self.log("INFO", f"   💾 Total Cache Tested: {results.get('total_cache_tested', 0)}")
        self.log("INFO", f"   📈 Session Success Rate: {results['success_rate']:.1f}%")
        self.log("INFO", f"   🔄 Workspace Clears: {results.get('workspace_clears', 0)}")
        self.log("INFO", f"   📍 Current Location: {results.get('location_index', 0)}/5")
        self.log("INFO", f"   ⏳ Untested Combinations: {results.get('untested_combinations', 0)}")
        
        # Discoveries
        if results['discoveries']:
            self.log("INFO", f"\n🆕 NEW ELEMENTS DISCOVERED:")
            for i, discovery in enumerate(results['discoveries'], 1):
                bonus_text = f" (+ {discovery['bonus_elements']} bonus!)" if discovery['bonus_elements'] > 0 else ""
                self.log("INFO", f"   {i:2d}. {discovery['combination']} = {discovery['result']}{bonus_text}")
        
        # Achievement status
        if results['elements_created'] >= results['target_elements']:
            self.log("INFO", "\n🏆 TARGET ACHIEVED!")
        else:
            remaining = results['target_elements'] - results['elements_created']
            self.log("INFO", f"\n⏳ {remaining} elements remaining to reach target")
        
        # Cache efficiency note
        untested = results.get('untested_combinations', 0)
        if untested == 0:
            self.log("INFO", "🎯 All available combinations have been tested!")
        elif untested > 100:
            self.log("INFO", f"📈 Plenty of combinations remaining ({untested}+ untested)")
        
        self.log("INFO", "=" * 60)
    
    def save_and_finish(self) -> bool:
        """Save game state and finish session."""
        try:
            self.log("INFO", "\n💾 Saving Game State...")
            
            # Clear workspace before saving for cleaner state
            self.automation.clear_workspace()
            time.sleep(2)
            
            # Attempt to save
            save_success = self.automation.save_game_state()
            
            if save_success:
                self.log("INFO", "✅ Game state save attempted successfully")
                self.log("INFO", "📥 Check your Downloads folder for the save file")
            else:
                self.log("WARNING", "⚠️ Save attempt may have failed - check Downloads folder")
            
            return save_success
            
        except Exception as e:
            self.log("ERROR", f"❌ Save and finish failed: {e}")
            return False
    
    def run_complete_automation(self) -> bool:
        """
        Run the complete automation: connect, discover elements, and save.
        
        Returns:
            bool: True if automation completed successfully
        """
        try:
            self.log("INFO", "🤖 INFINITE CRAFT COMPLETE AUTOMATION")
            self.log("INFO", "=" * 60)
            self.log("INFO", f"🎯 Goal: Create {self.target_new_elements} new elements and save state")
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
            
            # Step 2: Discovery session
            self.log("INFO", "\n📋 Step 2: Running discovery session...")
            results = self.run_discovery_session()
            
            # Step 3: Save state
            # Save game state if configured to do so
            if self.config.get('save_on_completion', True):
                self.log("INFO", "\n📋 Step 4: Saving game state...")
                save_success = self.save_and_finish()
            else:
                save_success = True
                self.log("INFO", "\n📋 Step 4: Skipping save (disabled in config)")
            
            # Final summary
            session_duration = (datetime.now() - self.session_start).total_seconds() / 60
            
            self.log("INFO", "\n" + "🏁" * 20)
            self.log("INFO", "🏁 AUTOMATION COMPLETE")
            self.log("INFO", "🏁" * 20)
            self.log("INFO", f"⏱️  Total Duration: {session_duration:.1f} minutes")
            self.log("INFO", f"🎯 Elements Created: {results['elements_created']}/{self.target_new_elements}")
            self.log("INFO", f"📊 Final Element Count: {results['final_element_count']}")
            self.log("INFO", f"💾 Save Attempted: {'✅' if save_success else '❌'}")
            
            # Success criteria
            success = results['elements_created'] >= self.target_new_elements
            if success:
                self.log("INFO", "🏆 MISSION ACCOMPLISHED!")
            else:
                remaining = self.target_new_elements - results['elements_created'] 
                self.log("INFO", f"⏳ Partially complete - {remaining} elements remaining")
            
            return success
            
        except Exception as e:
            self.log("ERROR", f"❌ Complete automation failed: {e}")
            return False
    
    def close(self):
        """Clean up automation resources."""
        if hasattr(self.automation, 'driver') and self.automation.driver:
            self.automation.log("INFO", "🔒 Keeping browser open for inspection...")
            # Don't close driver to allow manual inspection


def main():
    """Main entry point for automation script."""
    print("🎮 INFINITE CRAFT GENERIC AUTOMATION")
    print("=" * 60)
    print("🎯 Default Strategy: Element Discovery (create 20 new elements)")
    print("📋 Requirements:")
    print("   1. Chrome browser with remote debugging enabled")
    print("   2. Infinite Craft game loaded and ready")
    print("=" * 60)
    print()
    
    # Wait for user confirmation
    input("Press Enter when Chrome is ready with Infinite Craft loaded...")
    
    # Create automation controller with default element discovery strategy
    # 
    # Examples of other strategies that could be implemented:
    #
    # Combination Explorer Strategy:
    # strategy_config = {
    #     'type': 'combination_explorer', 
    #     'target_combinations': ['Fire + Water', 'Earth + Air'],
    #     'save_results': True
    # }
    #
    # Achievement Hunter Strategy:  
    # strategy_config = {
    #     'type': 'achievement_hunter',
    #     'target_elements': ['Dragon', 'Unicorn', 'Phoenix'],
    #     'max_attempts': 1000
    # }
    
    strategy_config = {
        'type': 'element_discovery',
        'target_new_elements': 20,
        'max_attempts_between_success': 50,
        'save_on_completion': True,
        'clear_workspace_on_start': True
    }
    
    automation = AutomationController(strategy_config=strategy_config, log_level="INFO")
    
    try:
        # Run complete automation
        success = automation.run_complete_automation()
        
        if success:
            print("\n🎉 AUTOMATION COMPLETED SUCCESSFULLY!")
            print("📥 Check your Downloads folder for the save file")
        else:
            print("\n⚠️ AUTOMATION PARTIALLY COMPLETED")
            print("🔍 Check the logs above for details")
            
    except KeyboardInterrupt:
        print("\n\n🛑 AUTOMATION INTERRUPTED BY USER")
        automation.log("INFO", "User interrupted automation")
        
    except Exception as e:
        print(f"\n💥 AUTOMATION CRASHED: {e}")
        import traceback
        traceback.print_exc()
        
    finally:
        automation.close()
        print("\n👋 Automation finished - browser kept open for inspection")


if __name__ == "__main__":
    main()
