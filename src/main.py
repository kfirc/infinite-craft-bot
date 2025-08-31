#!/usr/bin/env python3
"""
Infinite Craft Bot - Main Entry Point.

Single entry point for all automation functionality.
Uses Clean Architecture with service-oriented design.
"""

import argparse
from typing import Optional

from automations import ServiceAutomationController, ServiceTargetWordAutomation
from config import config


def run_element_discovery(target_elements: Optional[int] = None, max_attempts: Optional[int] = None) -> bool:
    """Run element discovery automation."""
    # Use config defaults if not provided
    target_elements = target_elements or config.DEFAULT_TARGET_ELEMENTS
    max_attempts = max_attempts or config.DEFAULT_MAX_DISCOVERY_ATTEMPTS

    print("🚀 Element Discovery Automation - Service Architecture")
    print("=" * 60)
    print("Discover new elements through intelligent combination testing")
    print("=" * 60)

    try:
        # Configure element discovery strategy
        strategy_config = {
            "type": "element_discovery",
            "target_new_elements": target_elements,
            "max_attempts_between_success": max_attempts,
            "save_on_completion": True,
            "clear_workspace_on_start": True,
        }

        # Create service-oriented automation controller with proper log level
        controller = ServiceAutomationController(strategy_config=strategy_config, log_level=config.LOG_LEVEL)

        print(f"🎯 Target: {target_elements} new elements")
        print(f"⚙️ Max attempts between success: {max_attempts}")
        print()

        # Run complete automation
        results = controller.run_complete_automation()

        # Print results summary
        print("\n" + "=" * 60)
        print("📊 AUTOMATION RESULTS")
        print("=" * 60)

        if results["success"]:
            print(f"✅ SUCCESS! Discovered {results['elements_created']} new elements")
            print(f"⏱️ Duration: {results['duration_minutes']:.1f} minutes")
            print(f"🧪 Combinations tested: {results['combinations_tested']}")
            print(f"📈 Final element count: {results['final_element_count']}")

            if results.get("target_achieved"):
                print("🎯 Target achieved!")
            else:
                print(f"⚠️ Partial success: {results['elements_created']}/{target_elements} elements")
        else:
            print(f"❌ FAILED: {results.get('error', 'Unknown error')}")
            if results.get("elements_created", 0) > 0:
                print(f"🆕 Created {results['elements_created']} elements before failure")

        print("=" * 60)

        # Clean up
        controller.close()
        return results["success"]

    except KeyboardInterrupt:
        print("\n⚠️ Automation interrupted by user")
        return False
    except Exception as e:
        print(f"❌ Automation failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def run_target_word_hunt(
    target_word: str, max_attempts: Optional[int] = None, combinations_per_iteration: Optional[int] = None
) -> bool:
    """Run target word hunting automation."""
    # Use config defaults if not provided
    max_attempts = max_attempts or config.DEFAULT_MAX_HUNT_ATTEMPTS
    combinations_per_iteration = combinations_per_iteration or config.DEFAULT_COMBINATIONS_PER_ITERATION

    print("🎯 Target Word Hunter - Service Architecture")
    print("=" * 60)
    print("Intelligently hunt for specific target words using semantic guidance")
    print("=" * 60)
    print(f"🎯 Target: {target_word}")

    try:
        # Configure target word hunting strategy
        strategy_config = {
            "type": "target_word_hunter",
            "target_word": target_word,
            "max_attempts": max_attempts,
            "top_combinations_per_iteration": combinations_per_iteration,
            "semantic_threshold": config.DEFAULT_SEMANTIC_THRESHOLD,
            "save_on_completion": True,
        }

        # Create service-oriented target word automation with proper log level
        controller = ServiceTargetWordAutomation(strategy_config=strategy_config, log_level=config.LOG_LEVEL)

        print(f"🧠 Semantic threshold: {strategy_config['semantic_threshold']}")
        print(f"🎯 Max attempts: {max_attempts}")
        print(f"📊 Top combinations per iteration: {combinations_per_iteration}")
        print()

        # Run complete automation
        results = controller.run_complete_automation()

        # Print results summary
        print("\n" + "=" * 60)
        print("📊 TARGET HUNT RESULTS")
        print("=" * 60)

        if results["success"]:
            print(f"🎉 SUCCESS! Found '{results['target_word']}'!")
            if results.get("target_element"):
                target_elem = results["target_element"]
                print(f"🏆 Target element: {target_elem.get('emoji', '')} {target_elem.get('name', '')}")

            print(f"⏱️ Duration: {results['duration_minutes']:.1f} minutes")
            print(f"🧪 Attempts made: {results['attempts_made']}")
            print(f"🆕 Elements created: {results['elements_created']}")
            print(f"📈 Final element count: {results['final_element_count']}")

            if results.get("discoveries"):
                print("🔬 Discoveries made:")
                for i, discovery in enumerate(results["discoveries"], 1):
                    print(
                        f"   {i}. {discovery['combination']} = {discovery['result']} (🧠 {discovery['similarity']:.3f})"
                    )

        else:
            print(f"❌ FAILED: Could not find '{results['target_word']}'")
            print(f"🧪 Attempts made: {results.get('attempts_made', 0)}")

            if results.get("elements_created", 0) > 0:
                print(f"🆕 Created {results['elements_created']} new elements along the way")
                if results.get("discoveries"):
                    print("🔬 Elements discovered:")
                    for discovery in results["discoveries"]:
                        print(f"   • {discovery['combination']} = {discovery['result']}")

        if results.get("error"):
            print(f"⚠️ Error: {results['error']}")

        print("=" * 60)

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


def main():
    """Main entry point with command line interface."""
    parser = argparse.ArgumentParser(
        description="Infinite Craft Bot - Service-Oriented Automation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py discover                          # Discover 20 new elements
  python main.py discover --target 10             # Discover 10 new elements
  python main.py hunt Dragon                      # Hunt for Dragon element
  python main.py hunt --word Airplane --attempts 30    # Hunt for Airplane with 30 max attempts
  python main.py interactive                      # Interactive mode
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Element discovery command
    discover_parser = subparsers.add_parser("discover", help="Discover new elements")
    discover_parser.add_argument(
        "--target", type=int, default=20, help="Target number of elements to discover (default: 20)"
    )
    discover_parser.add_argument(
        "--max-attempts", type=int, default=50, help="Max attempts between successes (default: 50)"
    )

    # Target word hunting command
    hunt_parser = subparsers.add_parser("hunt", help="Hunt for specific target word")
    hunt_parser.add_argument("word", nargs="?", help="Target word to hunt for")
    hunt_parser.add_argument("--word", dest="target_word", help="Target word to hunt for (alternative syntax)")
    hunt_parser.add_argument("--attempts", type=int, default=50, help="Maximum attempts (default: 50)")
    hunt_parser.add_argument("--combinations", type=int, default=5, help="Combinations per iteration (default: 5)")

    # Interactive mode
    subparsers.add_parser("interactive", help="Interactive mode")

    args = parser.parse_args()

    # Handle commands
    if args.command == "discover":
        success = run_element_discovery(args.target, args.max_attempts)

    elif args.command == "hunt":
        target_word = args.word or args.target_word
        if not target_word:
            # Use environment default if available
            target_word = config.DEFAULT_TARGET_WORD
            print(f"🎪 Using default target word from config: {target_word}")

        if not target_word:
            target_word = input("🎪 Enter target word to hunt for: ").strip()
            if not target_word:
                print("❌ No target word provided")
                return 1

        success = run_target_word_hunt(target_word, args.attempts, args.combinations)

    elif args.command == "interactive":
        return interactive_mode()

    else:
        # No command specified, show help
        parser.print_help()
        return 0

    return 0 if success else 1


def interactive_mode() -> int:
    """Interactive mode for user-friendly operation."""
    print("🎮 Infinite Craft Bot - Interactive Mode")
    print("=" * 50)
    print("Choose your automation strategy:")
    print("1. 🔍 Element Discovery - Find new elements")
    print("2. 🎯 Target Word Hunt - Hunt for specific word")
    print("3. ❌ Exit")

    while True:
        choice = input("\nEnter your choice (1-3): ").strip()

        if choice == "1":
            target = input("🎯 Target number of elements (default: 20): ").strip()
            target = int(target) if target.isdigit() else 20

            max_attempts = input("⚙️ Max attempts between success (default: 50): ").strip()
            max_attempts = int(max_attempts) if max_attempts.isdigit() else 50

            success = run_element_discovery(target, max_attempts)
            return 0 if success else 1

        elif choice == "2":
            target_word = input("🎪 Enter target word to hunt for: ").strip()
            if not target_word:
                print("❌ Target word is required")
                continue

            attempts = input("🎯 Max attempts (default: 50): ").strip()
            attempts = int(attempts) if attempts.isdigit() else 50

            combinations = input("📊 Combinations per iteration (default: 5): ").strip()
            combinations = int(combinations) if combinations.isdigit() else 5

            success = run_target_word_hunt(target_word, attempts, combinations)
            return 0 if success else 1

        elif choice == "3":
            print("👋 Goodbye!")
            return 0

        else:
            print("❌ Invalid choice. Please enter 1, 2, or 3.")


if __name__ == "__main__":
    main()
