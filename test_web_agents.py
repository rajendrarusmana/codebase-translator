#!/usr/bin/env python3
"""
Test script to demonstrate web agents with web browsing capabilities.
"""
import asyncio
import os
from src.agents.web_project_analyzer_agent import WebProjectAnalyzerAgent
from src.agents.web_architecture_translator_agent import WebArchitectureTranslatorAgent

async def test_web_project_analyzer():
    """Test the web project analyzer with web browsing."""
    print("🔍 Testing Web Project Analyzer with Web Browsing...")

    # Initialize agent with OpenRouter
    agent = WebProjectAnalyzerAgent(
        model_name="openrouter/meta-llama/llama-3.1-8b-instruct:free",
        temperature=0.0
    )

    # Create test state
    state = {
        'project_root': './demo_sidekiq_project',
        'errors': []
    }

    # Process with web research
    result_state = await agent.process(state)

    if 'project_spec' in result_state:
        spec = result_state['project_spec']
        print(f"✅ Project Type: {spec.project_type}")
        print(f"✅ Primary Language: {spec.primary_language}")
        print(f"✅ Technology Stack: {spec.technology_stack}")
        print(f"✅ Architecture: {spec.architecture}")
    else:
        print("❌ Failed to analyze project")
        print(f"Errors: {result_state.get('errors', [])}")

async def test_web_architecture_translator():
    """Test the web architecture translator with web research."""
    print("\n🔧 Testing Web Architecture Translator with Web Research...")

    # First run project analyzer to get spec
    analyzer = WebProjectAnalyzerAgent(
        model_name="openrouter/meta-llama/llama-3.1-8b-instruct:free",
        temperature=0.0
    )

    analyzer_state = {
        'project_root': './demo_sidekiq_project',
        'errors': []
    }

    analyzer_result = await analyzer.process(analyzer_state)

    if 'project_spec' not in analyzer_result:
        print("❌ Failed to get project specification")
        return

    # Now test architecture translator
    translator = WebArchitectureTranslatorAgent(
        model_name="openrouter/meta-llama/llama-3.1-8b-instruct:free",
        temperature=0.0
    )

    translator_state = {
        'project_spec': analyzer_result['project_spec'],
        'target_language': 'go',
        'errors': [],
        'output_path': './translated_enhanced'
    }

    result_state = await translator.process(translator_state)

    if 'architecture_translation' in result_state:
        translation = result_state['architecture_translation']
        print(f"✅ Source Framework: {translation['source_framework']}")
        print(f"✅ Target Framework: {translation['target_framework']}")
        print(f"✅ Research Summary: {translation.get('research_summary', 'N/A')}")
        print(f"✅ Generated {len(translation.get('scaffolding_files', {}))} scaffolding files")
        print(f"✅ Migration Notes: {len(translation.get('migration_notes', []))} notes")
    else:
        print("❌ Failed to translate architecture")
        print(f"Errors: {result_state.get('errors', [])}")

async def main():
    """Main test function."""
    print("🚀 Testing Web Agents with Web Browsing Capabilities\n")

    # Check for API key
    if not os.getenv('OPENROUTER_API_KEY'):
        print("❌ Please set OPENROUTER_API_KEY environment variable")
        return

    try:
        await test_web_project_analyzer()
        await test_web_architecture_translator()
        print("\n🎉 Web agents testing completed!")

    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())