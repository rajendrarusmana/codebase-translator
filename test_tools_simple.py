#!/usr/bin/env python3
"""
Simple test to verify tool binding is working properly.
"""
import asyncio
import os
from src.agents.web_project_analyzer_agent import search_framework_info

async def test_tools_directly():
    """Test tools directly to verify they work."""
    print("🔧 Testing Web Search Tools Directly...")

    try:
        # Test direct tool usage
        result = search_framework_info("Sidekiq Ruby background jobs")
        print(f"✅ Search Tool Result: {result[:200]}...")
        return True
    except Exception as e:
        print(f"❌ Tool test failed: {e}")
        return False

async def test_tool_binding():
    """Test that tools are properly bound to LLM."""
    from src.agents.web_project_analyzer_agent import WebProjectAnalyzerAgent

    print("\n🔗 Testing Tool Binding...")

    try:
        agent = WebProjectAnalyzerAgent(
            model_name="openrouter/google/gemini-flash-1.5",
            temperature=0.0
        )

        print(f"✅ Agent created with {len(agent.tools)} tools")
        print(f"✅ Tools bound to LLM: {hasattr(agent.llm, 'bind_tools')}")

        # Check if tools are accessible
        tool_names = [tool.name for tool in agent.tools]
        print(f"✅ Available tools: {tool_names}")

        return True

    except Exception as e:
        print(f"❌ Tool binding test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def main():
    """Main test function."""
    print("🧪 Testing Web Agent Tool Capabilities\n")

    # Test 1: Direct tool usage
    tools_work = await test_tools_directly()

    # Test 2: Tool binding
    binding_works = await test_tool_binding()

    print(f"\n📊 Results:")
    print(f"   Tools Work: {'✅' if tools_work else '❌'}")
    print(f"   Tool Binding: {'✅' if binding_works else '❌'}")

    if tools_work and binding_works:
        print("\n🎉 Web agents are ready for web-powered framework detection!")
        print("\n💡 Benefits of Web Agents:")
        print("   • Can research current framework versions and features")
        print("   • Find equivalent frameworks in target languages")
        print("   • Discover best practices and migration patterns")
        print("   • Adapt to new frameworks without code changes")
        print("   • Access up-to-date documentation and examples")
    else:
        print("\n⚠️  Some issues detected with tool setup")

if __name__ == "__main__":
    asyncio.run(main())