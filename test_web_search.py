#!/usr/bin/env python3
"""
Test web search functionality for web agents.
"""
import asyncio
from langchain_community.tools import DuckDuckGoSearchRun

async def test_web_search():
    """Test direct web search functionality."""
    print("🔍 Testing Web Search Capabilities...")

    try:
        search = DuckDuckGoSearchRun()

        # Test search for framework information
        print("\n1. Searching for Sidekiq information...")
        result1 = search.run("Sidekiq Ruby background jobs Redis queue")
        print(f"Result: {result1[:300]}...\n")

        print("2. Searching for Go worker frameworks...")
        result2 = search.run("Go asynq machinery worker queue frameworks 2024")
        print(f"Result: {result2[:300]}...\n")

        print("3. Searching for framework migration patterns...")
        result3 = search.run("Sidekiq to asynq migration Go worker patterns")
        print(f"Result: {result3[:300]}...\n")

        print("✅ Web search is working! Enhanced agents can now:")
        print("   • Research current framework information")
        print("   • Find equivalent frameworks in target languages")
        print("   • Discover migration patterns and best practices")
        print("   • Stay up-to-date with latest framework developments")

        return True

    except Exception as e:
        print(f"❌ Web search failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def main():
    """Main test function."""
    print("🧪 Testing Web Research Capabilities for Web Agents\n")

    success = await test_web_search()

    if success:
        print(f"\n🎉 Web agents are ready for intelligent framework detection!")
        print(f"\n💡 This enables the system to:")
        print(f"   • Recognize new frameworks like Temporal, Deno, Bun, etc.")
        print(f"   • Find current best practices and patterns")
        print(f"   • Discover framework alternatives and equivalents")
        print(f"   • Access up-to-date documentation and examples")
        print(f"   • Adapt to the rapidly changing tech landscape")
    else:
        print(f"\n❌ Web search setup needs attention")

if __name__ == "__main__":
    asyncio.run(main())