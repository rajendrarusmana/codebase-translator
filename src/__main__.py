#!/usr/bin/env python3
"""
Codebase Translator - Main Entry Point
"""
import asyncio
import sys
import argparse
from pathlib import Path
import logging
import yaml
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from dotenv import load_dotenv

from .orchestrator.hierarchical_workflow import HierarchicalCodebaseTranslatorWorkflow

load_dotenv()

console = Console()
logger = logging.getLogger(__name__)

def setup_logging(level: str = "INFO"):
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

def load_config(config_path: str = None) -> dict:
    default_config = {
        'traverser': {
            'model_name': 'claude-3-5-sonnet-20241022',
            'temperature': 0.0
        },
        'documenter': {
            'model_name': 'claude-3-5-sonnet-20241022',
            'temperature': 0.0
        },
        'translator': {
            'model_name': 'claude-3-5-sonnet-20241022',
            'temperature': 0.1
        },
        'output_path': 'translated',
        'parallel_processing': True,
        # PostgreSQL Database Configuration
        'postgres': {
            'enabled': True,
            'url': 'postgresql://postgres:post@localhost:5432/codebase_translator',
            'min_connections': 5,
            'max_connections': 20,
            'initialize_schema': True,
            'schema_file': 'src/persistence/schema_simple.sql'
        },
        # Language-specific settings
        'language_settings': {
            'python': {
                'include_type_hints': True,
                'format_with_black': True
            },
            'javascript': {
                'use_es6': True,
                'include_jsdoc': True
            },
            'typescript': {
                'strict_mode': True,
                'include_interfaces': True
            },
            'java': {
                'package_structure': True,
                'include_javadoc': True
            },
            'go': {
                'format_with_gofmt': True,
                'include_godoc': True
            }
        }
    }
    
    if config_path and Path(config_path).exists():
        with open(config_path, 'r') as f:
            user_config = yaml.safe_load(f)
        default_config.update(user_config)
    
    return default_config

async def main():
    parser = argparse.ArgumentParser(
        description="Translate codebase from one language to another using AI agents",
        epilog="""
Examples:
  # Translate a web app project
  translator /path/to/my-web-app javascript python

  # Analyze only (no translation)
  translator /path/to/project python --dry-run

  # Translate with custom output location  
  translator /path/to/project java python --output /path/to/output
        """,
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "project_root", 
        help="Path to project root directory (where the codebase to analyze is located)"
    )
    parser.add_argument(
        "target_language", 
        help="Target programming language (python, javascript, java, go, rust, etc.)"
    )
    parser.add_argument("--config", "-c", help="Path to configuration file")
    parser.add_argument("--output", "-o", help="Direct output directory for translated code")
    parser.add_argument("--output-root", help="Root directory for organized project translations (default: ./translated)")
    parser.add_argument("--log-level", default="INFO", help="Logging level (DEBUG, INFO, WARNING, ERROR)")
    parser.add_argument("--dry-run", action="store_true", help="Analyze only, don't translate (useful for testing)")
    parser.add_argument("--source-language", help="Force source language detection (auto-detected if not specified)")
    parser.add_argument("--resume", action="store_true", help="Resume from previous checkpoint if available")
    parser.add_argument("--translator-only", action="store_true", help="Run only the translator agent on a specification file (skip documentation and analysis)")
    
    args = parser.parse_args()
    
    setup_logging(args.log_level)
    
    # Handle translator-only mode (before directory validation)
    if args.translator_only:
        from .agents.translator_agent import TranslatorAgent
        from .models.specification import ModuleSpecification
        import json
        
        project_root = Path(args.project_root).absolute()
        
        console.print(f"[bold blue]🔄 Running Translator Agent Only...[/bold blue]")
        console.print(f"Specification File: {project_root}")
        console.print(f"Target Language: {args.target_language}")
        
        # Load the specification
        try:
            with open(project_root, 'r') as f:
                spec_data = json.load(f)
            
            # Create ModuleSpecification from JSON data
            if isinstance(spec_data, list):
                module_specs = [ModuleSpecification(**spec) for spec in spec_data]
            else:
                module_specs = [ModuleSpecification(**spec_data)]
                
            console.print(f"Loaded {len(module_specs)} module specifications")
        except Exception as e:
            console.print(f"[red]❌ Error loading specification: {e}[/red]")
            sys.exit(1)
        
        # Initialize translator agent
        config = load_config(args.config)
        config.update({
            'output_path': args.output or args.output_root or 'translated',
            'dry_run': args.dry_run
        })
        
        translator = TranslatorAgent(**config.get('translator', {
            'model_name': 'claude-3-5-sonnet-20241022',
            'temperature': 0.1
        }))
        
        # Create initial state
        state = {
            'target_language': args.target_language,
            'output_path': args.output or args.output_root or 'translated',
            'translation_state': {
                'translated_modules': {},
                'errors': []
            },
            'errors': []
        }
        
        # Translate each module
        for i, module_spec in enumerate(module_specs):
            console.print(f"Translating module {i+1}/{len(module_specs)}: {module_spec.module_name}")
            
            # Set current module
            state['current_module'] = module_spec
            
            try:
                # Process with translator
                state = await translator.process(state)
                
                if state.get('errors'):
                    console.print(f"[yellow]⚠️  Errors encountered: {state['errors']}[/yellow]")
                    
            except Exception as e:
                console.print(f"[red]❌ Error translating module {module_spec.module_name}: {e}[/red]")
                state['errors'].append({"module": module_spec.module_name, "error": str(e)})
        
        # Save results
        translation_state = state.get('translation_state', {})
        translated_modules = translation_state.get('translated_modules', {})
        
        console.print("[bold green]✅ Translation completed![/bold green]")
        console.print(f"Translated {len(translated_modules)} modules")
        
        # Show results
        for module_path, translation_data in translated_modules.items():
            if isinstance(translation_data, dict) and 'code' in translation_data:
                console.print(f"\n[blue]📄 {module_path}:[/blue]")
                console.print("-" * 40)
                code_preview = translation_data['code'][:200] + "..." if len(translation_data['code']) > 200 else translation_data['code']
                console.print(code_preview)
        
        return
    
    # Validate project root directory (only for full workflow)
    project_root = Path(args.project_root).absolute()
    if not project_root.exists():
        console.print(f"[red]Error: Project root directory does not exist: {project_root}[/red]")
        sys.exit(1)
    
    if not project_root.is_dir():
        console.print(f"[red]Error: Project root must be a directory, not a file: {project_root}[/red]")
        sys.exit(1)
    
    config = load_config(args.config)
    
    # Handle output path configuration
    if args.output:
        # Direct output path (backward compatibility)
        config.update({'output_path': args.output})
    elif args.output_root:
        # Use output root with deterministic folder structure
        config.update({'output_path': args.output_root})
    else:
        # Use default output root
        config.update({'output_path': './translated'})
    
    config.update({
        'dry_run': args.dry_run
    })
    
    console.print(f"[bold blue]🔄 Codebase Translator Starting...[/bold blue]")
    console.print(f"Project Root: {project_root}")
    console.print(f"Target Language: {args.target_language}")
    
    if args.output:
        console.print(f"Output Directory: {args.output} (direct)")
    elif args.output_root:
        from .utils.project_management import generate_project_identifier
        project_id = generate_project_identifier(project_root, args.target_language)
        console.print(f"Output Root: {args.output_root}")
        console.print(f"Project Output: {args.output_root}/{project_id}")
    else:
        from .utils.project_management import generate_project_identifier
        project_id = generate_project_identifier(project_root, args.target_language)
        console.print(f"Output Directory: ./translated/{project_id} (organized)")
    
    if args.source_language:
        console.print(f"Source Language: {args.source_language} (forced)")
    else:
        console.print(f"Source Language: [dim]auto-detecting...[/dim]")
    
    workflow = HierarchicalCodebaseTranslatorWorkflow(config)
    
    # Check for existing checkpoint
    if args.resume:
        workflow_status = workflow.get_workflow_status()
        if workflow_status.get('status') != 'not_started':
            console.print(f"[yellow]Found checkpoint at phase: {workflow_status.get('phase')}[/yellow]")
            completed_agents = workflow_status.get('completed_agents', [])
            if completed_agents:
                console.print(f"[yellow]Completed agents: {', '.join(completed_agents)}[/yellow]")
        else:
            console.print(f"[yellow]No checkpoint found, starting fresh analysis[/yellow]")
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console
    ) as progress:
        task = progress.add_task("Initializing...", total=None)
        
        try:
            result = await workflow.run(
                root_path=str(project_root),
                target_language=args.target_language,
                source_language=args.source_language,
                resume=args.resume,
                **config
            )
            
            progress.update(task, description="Complete!")
            
            if result['success']:
                console.print("[bold green]✅ Translation completed successfully![/bold green]")
                
                final_state = result['final_state']
                if 'analysis_state' in final_state and final_state['analysis_state']:
                    analysis = final_state['analysis_state']
                    console.print(f"📊 Analyzed {len(analysis.get('file_paths', []))} files")
                    console.print(f"📄 Created {len(analysis.get('module_specs', []))} module specifications")
                
                if 'translation_state' in final_state and final_state['translation_state']:
                    translation = final_state['translation_state']
                    console.print(f"🔄 Translated {len(translation.get('translated_modules', {}))} modules")
                
                if result.get('errors'):
                    console.print(f"[yellow]⚠️  {len(result['errors'])} warnings/errors encountered[/yellow]")
                    for error in result['errors'][:3]:
                        console.print(f"  - {error.get('message', error)}")
            
            else:
                console.print(f"[red]❌ Translation failed: {result.get('error', 'Unknown error')}[/red]")
                sys.exit(1)
        
        except KeyboardInterrupt:
            console.print("\n[yellow]Translation interrupted by user[/yellow]")
            sys.exit(1)
        except Exception as e:
            console.print(f"[red]❌ Unexpected error: {e}[/red]")
            logger.exception("Unexpected error during translation")
            sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())