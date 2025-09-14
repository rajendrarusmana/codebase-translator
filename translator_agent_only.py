#!/usr/bin/env python3
"""
Script to run just the translator agent directly, without the full workflow.
"""
import asyncio
import sys
import argparse
from pathlib import Path
import json
import logging
from dotenv import load_dotenv

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.agents.translator_agent import TranslatorAgent
from src.models.specification import ModuleSpecification
from src.orchestrator.hierarchical_workflow import HierarchicalCodebaseTranslatorWorkflow

load_dotenv()

def setup_logging(level: str = "INFO"):
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

async def run_translator_only(spec_file: str, target_language: str, output_path: str = "translated"):
    """Run only the translator agent on a specification file."""
    print(f"🔄 Running Translator Agent Only...")
    print(f"Specification File: {spec_file}")
    print(f"Target Language: {target_language}")
    print(f"Output Directory: {output_path}")
    
    # Load the specification
    try:
        with open(spec_file, 'r') as f:
            spec_data = json.load(f)
        
        # Create ModuleSpecification from JSON data
        if isinstance(spec_data, list):
            module_specs = [ModuleSpecification(**spec) for spec in spec_data]
        else:
            module_specs = [ModuleSpecification(**spec_data)]
            
        print(f"Loaded {len(module_specs)} module specifications")
    except Exception as e:
        print(f"❌ Error loading specification: {e}")
        return False
    
    # Initialize translator agent
    config = {
        'model_name': 'claude-3-5-sonnet-20241022',
        'temperature': 0.1
    }
    
    translator = TranslatorAgent(**config)
    
    # Create initial state
    state = {
        'target_language': target_language,
        'output_path': output_path,
        'translation_state': {
            'translated_modules': {},
            'errors': []
        },
        'errors': []
    }
    
    # Translate each module
    for i, module_spec in enumerate(module_specs):
        print(f"Translating module {i+1}/{len(module_specs)}: {module_spec.module_name}")
        
        # Set current module
        state['current_module'] = module_spec
        
        try:
            # Process with translator
            state = await translator.process(state)
            
            if state.get('errors'):
                print(f"⚠️  Errors encountered: {state['errors']}")
                
        except Exception as e:
            print(f"❌ Error translating module {module_spec.module_name}: {e}")
            state['errors'].append({"module": module_spec.module_name, "error": str(e)})
    
    # Save results
    translation_state = state.get('translation_state', {})
    translated_modules = translation_state.get('translated_modules', {})
    
    print(f"✅ Translation completed!")
    print(f"Translated {len(translated_modules)} modules")
    
    # Show results
    for module_path, translation_data in translated_modules.items():
        if isinstance(translation_data, dict) and 'code' in translation_data:
            print(f"\n📄 {module_path}:")
            print("-" * 40)
            print(translation_data['code'][:200] + "..." if len(translation_data['code']) > 200 else translation_data['code'])
    
    return True

def main():
    parser = argparse.ArgumentParser(
        description="Run only the translator agent on specification files",
        epilog="""
Examples:
  # Translate a specification file to JavaScript
  python translator_agent_only.py spec.json javascript

  # Translate with custom output location
  python translator_agent_only.py spec.json python --output custom_output
        """,
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "spec_file", 
        help="Path to specification JSON file"
    )
    parser.add_argument(
        "target_language", 
        help="Target programming language (python, javascript, java, go, rust, etc.)"
    )
    parser.add_argument("--output", "-o", help="Output directory for translated code", default="translated")
    parser.add_argument("--log-level", default="INFO", help="Logging level (DEBUG, INFO, WARNING, ERROR)")
    
    args = parser.parse_args()
    
    setup_logging(args.log_level)
    
    # Validate spec file
    spec_path = Path(args.spec_file).absolute()
    if not spec_path.exists():
        print(f"❌ Error: Specification file does not exist: {spec_path}")
        sys.exit(1)
    
    if not spec_path.is_file():
        print(f"❌ Error: Specification path must be a file: {spec_path}")
        sys.exit(1)
    
    # Run translator
    success = asyncio.run(run_translator_only(
        str(spec_path), 
        args.target_language, 
        args.output
    ))
    
    if not success:
        sys.exit(1)

if __name__ == "__main__":
    main()