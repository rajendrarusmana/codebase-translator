# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a sophisticated LangGraph-based multi-agent framework for translating codebases between programming languages. The system performs hierarchical analysis, creates language-agnostic specifications, and preserves functional equivalence during translation.

## Commands

### Setup and Installation
```bash
# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Optional: Install PostgreSQL dependencies for persistence
pip install -r requirements-postgres.txt
```

### Running the Translator
```bash
# Basic translation
source venv/bin/activate && python -m src PROJECT_ROOT TARGET_LANGUAGE

# With configuration file
source venv/bin/activate && python -m src PROJECT_ROOT TARGET_LANGUAGE --config config.yaml

# Analyze only (no translation)
source venv/bin/activate && python -m src PROJECT_ROOT TARGET_LANGUAGE --dry-run

# Resume from checkpoint (requires PostgreSQL)
source venv/bin/activate && python -m src PROJECT_ROOT TARGET_LANGUAGE --resume

# Run example translation
source venv/bin/activate && python examples/run_example.py
```

## Architecture

### Multi-Agent System
The framework uses a hierarchical multi-agent architecture orchestrated by LangGraph:

1. **ProjectAnalyzerAgent** (`src/agents/project_analyzer_agent.py`): Determines application type and architecture patterns
2. **TraverserAgent** (`src/agents/traverser_agent.py`): Discovers and catalogs source files
3. **FileClassifierAgent** (`src/agents/file_classifier_agent.py`): Categorizes files by purpose
4. **FunctionExtractorAgent** (`src/agents/function_extractor_agent.py`): Extracts function signatures using AST
5. **DocumenterAgent** (`src/agents/documenter_agent.py`): Creates language-agnostic specifications
6. **TranslatorAgent** (`src/agents/translator_agent.py`): Converts specifications to target language
7. **GapFillerAgent** (`src/agents/gap_filler_agent.py`): Identifies and fills missing functionality

### Workflow Orchestration
- **HierarchicalCodebaseTranslatorWorkflow** (`src/orchestrator/hierarchical_workflow.py`): Main workflow coordinator
- Uses LangGraph StateGraph for managing agent execution flow
- Supports checkpointing and resume capabilities via PostgreSQL

### Data Models
- **OrchestratorState** (`src/models/graph_state.py`): Central state management
- **ModuleSpecification** (`src/models/specification.py`): Language-agnostic module specs
- **EnhancedSpecification** (`src/models/enhanced_specification.py`): Extended specs with patterns
- **HierarchicalSpec** (`src/models/hierarchical_spec.py`): Hierarchical module organization

### Persistence Layer
- Optional PostgreSQL integration for checkpointing and collaboration
- **CheckpointManager** (`src/persistence/agent_checkpoint.py`): Agent-level checkpointing
- **Repositories** (`src/persistence/repositories.py`): Database access patterns

## Key Configuration

The system uses `config.yaml` for configuration:
- Model selection (Claude, GPT-4, OpenRouter models)
- Rate limiting settings
- PostgreSQL connection details
- Language-specific translation settings
- Output path configuration

## Language Support

**Source Languages**: Python, JavaScript, TypeScript, Java, Go, Rust, C++, C, Clojure
**Target Languages**: Python, JavaScript, TypeScript, Java, Go, Rust

## Important Implementation Details

- All agents inherit from **BaseAgent** (`src/agents/base_agent.py`) which provides checkpoint management
- The system uses tree-sitter for AST parsing when available
- Rate limiting is built-in with exponential backoff for API reliability
- PostgreSQL persistence enables resume capability for large projects
- Output is organized deterministically based on project identifiers