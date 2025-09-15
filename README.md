# Codebase Translator

An advanced LangGraph-based multi-agent framework that performs hierarchical codebase analysis, creates comprehensive language-agnostic specifications, and translates codebases between programming languages while preserving functional equivalence. Features PostgreSQL persistence, intelligent gap filling, and sophisticated project architecture detection.

## 🚀 Features

- **Hierarchical Multi-Agent Architecture**: Specialized agents for project analysis, file classification, function extraction, documentation, and translation
- **Advanced Project Analysis**: Detects application type (web API, CLI, microservice, etc.) and architecture patterns (MVC, layered, DDD, etc.)
- **Intelligent Gap Filling**: Automatically identifies and implements missing functionality in translated code
- **PostgreSQL Persistence**: Comprehensive database schema for storing project documentation, function analysis, and translation history
- **Language Agnostic Specifications**: Creates universal specifications that capture program semantics, data flow, and side effects
- **Functional Preservation**: Maintains identical behavior across language translations with comprehensive testing support
- **Context-Aware Analysis**: Identifies function contexts (handlers, repositories, services, utilities, tests) with specialized field tracking
- **LangGraph Orchestration**: Sophisticated workflow management with checkpointing and resume capabilities
- **Rate Limiting & Retry Logic**: Built-in API rate limiting with exponential backoff for reliable large-scale translations
- **Extensible**: Easy to add support for new programming languages and analysis agents

## 📋 Architecture

The framework implements a hierarchical multi-agent architecture with specialized agents for comprehensive codebase analysis:

### Core Analysis Agents

#### 1. Project Analyzer Agent
- Determines application type (web API, CLI, background worker, library, desktop app, mobile app, microservice, monolith)
- Identifies architecture patterns (MVC, layered, domain-driven, microservices, event-driven, hexagonal, serverless)
- Analyzes technology stack and entry points
- Maps key directories and their purposes

#### 2. Traverser Agent
- Discovers and catalogs all source files with intelligent filtering
- Identifies module boundaries and dependencies
- Detects primary programming language and entry points
- Handles complex project structures with nested directories

#### 3. File Classifier Agent
- Categorizes files by type (logic, data, test, configuration, documentation, etc.)
- Determines file purposes with confidence scoring
- Identifies test files and their frameworks
- Maps configuration and documentation files

#### 4. Function Extractor Agent
- Parses source code using AST when available
- Extracts function signatures, parameters, and return types
- Identifies function contexts (handler, repository, service, utility, component, test)
- Tracks specialized fields like HTTP methods, SQL operations, business domains

#### 5. Documenter Agent
- Creates comprehensive language-agnostic specifications including:
  - Input/output parameters with semantic types
  - Step-by-step operations with data flow analysis
  - Side effects (file I/O, network, database, console, etc.)
  - Dependencies and algorithms with call graphs
  - Control flow conditions and error handling
  - Test case descriptions and assertion types

#### 6. Translator Agent
- Converts specifications to idiomatic target language code
- Maps data types and operations appropriately
- Generates code following language best practices
- Preserves functional equivalence with comprehensive error handling

#### 7. Gap Filler Agent
- Analyzes translated code for missing functionality
- Identifies incomplete implementations and missing components
- Automatically generates missing functions, classes, and endpoints
- Ensures seamless integration with existing code

## 🛠️ Installation

### Basic Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd codebase-translator
```

2. Install core dependencies:
```bash
pip install -r requirements.txt
```

3. Set up API keys:
```bash
export OPENAI_API_KEY="your-openai-key"
# or
export ANTHROPIC_API_KEY="your-anthropic-key"
# or
export OPENROUTER_API_KEY="your-openrouter-key"
```

### PostgreSQL Setup (Optional but Recommended)

For full functionality including persistence and collaboration features:

1. Install PostgreSQL dependencies:
```bash
pip install -r requirements-postgres.txt
```

2. Set up PostgreSQL database:
```bash
# Create database
createdb codebase_translator

# Configure connection in config.yaml or environment:
export DATABASE_URL="postgresql://user:password@localhost:5432/codebase_translator"
```

3. Initialize database schema (automatic on first run with postgres.enabled: true)

## 📖 Usage

### Command Line Interface

```bash
# Basic translation
python -m src PROJECT_ROOT TARGET_LANGUAGE [options]

# With PostgreSQL persistence and resume capability
python -m src PROJECT_ROOT TARGET_LANGUAGE --config config.yaml --resume

# Analysis only with detailed logging
python -m src PROJECT_ROOT TARGET_LANGUAGE --dry-run --log-level DEBUG
```

**Arguments:**
- `PROJECT_ROOT`: Path to project root directory (where your codebase is located)
- `TARGET_LANGUAGE`: Target programming language (python, javascript, typescript, java, go, rust, etc.)

**Options:**
- `--config, -c`: Configuration file path (recommended for advanced features)
- `--output, -o`: Output directory for translated code (default: "translated")  
- `--review`: Enable human review before translation
- `--log-level`: Logging level (DEBUG, INFO, WARNING, ERROR)
- `--dry-run`: Analyze only, don't translate (useful for testing)
- `--source-language`: Force source language detection (auto-detected if not specified)
- `--resume`: Resume from previous checkpoint (requires PostgreSQL)

### Examples

```bash
# Translate a Python web app to JavaScript
python -m src /path/to/my-web-app javascript

# Analyze a Java project without translating
python -m src /path/to/java-project python --dry-run

# Translate with human review and custom output location
python -m src /path/to/project java --review --output /path/to/translated-code

# Force source language detection and use custom config
python -m src /path/to/project python --source-language javascript --config myconfig.yaml
```

### Programmatic Usage

```python
import asyncio
from src.orchestrator.hierarchical_workflow import HierarchicalCodebaseTranslatorWorkflow

async def translate_codebase():
    config = {
        'human_review': False,
        'output_path': 'translated',
        'documenter': {'model_name': 'claude-3-5-sonnet-20241022'},
        'translator': {'model_name': 'claude-3-5-sonnet-20241022'}
    }
    
    workflow = HierarchicalCodebaseTranslatorWorkflow(config)
    result = await workflow.run(
        root_path="./source_code",
        target_language="javascript"
    )
    
    if result['success']:
        print("Translation completed!")
    else:
        print(f"Error: {result['error']}")

asyncio.run(translate_codebase())
```

## 📊 Specification Schema

The framework creates detailed specifications for each module:

```json
{
  "module_name": "calculator",
  "file_path": "src/calculator.py",
  "original_language": "python",
  "description": "A calculator module with basic operations",
  "inputs": [
    {"name": "a", "type": "float", "description": "First operand"},
    {"name": "b", "type": "float", "description": "Second operand"}
  ],
  "outputs": [
    {"name": "result", "type": "float", "description": "Calculation result"}
  ],
  "operations": [
    {
      "step": 1,
      "operation": "validate_inputs",
      "description": "Check if inputs are valid numbers",
      "control_flow": "conditional"
    },
    {
      "step": 2,
      "operation": "perform_calculation",
      "description": "Execute arithmetic operation",
      "data_flow": "transform"
    }
  ],
  "side_effects": [
    {
      "type": "console",
      "description": "Print calculation history",
      "scope": "local"
    }
  ],
  "dependencies": [
    {"module": "math", "usage": "import", "import_type": "standard"}
  ]
}
```

## 🔧 Configuration

Create a `config.yaml` file to customize the translation:

```yaml
# Agent configurations
# OpenRouter models can be specified as:
# - "openrouter/meta-llama/llama-3.1-8b-instruct" 
# - "or:meta-llama/llama-3.1-70b-instruct"
# - Any model identifier from https://openrouter.ai/models

traverser:
  model_name: "claude-3-5-sonnet-20241022"  # Working Claude 3.5 Sonnet
  temperature: 0.0

documenter:
  model_name: "claude-3-5-sonnet-20241022"  # Best available for semantic analysis
  temperature: 0.0

translator:
  model_name: "claude-3-5-sonnet-20241022" 
  temperature: 0.1

# Alternative OpenRouter configuration:
# traverser:
#   model_name: "openrouter/meta-llama/llama-3.1-70b-instruct"
#   temperature: 0.0
#
# documenter:
#   model_name: "openrouter/meta-llama/llama-3.1-70b-instruct"
#   temperature: 0.0
#
# translator:
#   model_name: "openrouter/meta-llama/llama-3.1-70b-instruct"
#   temperature: 0.1

# Workflow settings
human_review: false
parallel_processing: true
output_path: "translated"

## 🎯 Supported Languages

**Source Languages:**
- Python (.py)
- JavaScript (.js)
- TypeScript (.ts)
- Java (.java)
- Go (.go)
- Rust (.rs)
- C++ (.cpp)
- C (.c)
- Clojure (.clj, .cljs, .cljc)

**Target Languages:**
- Python
- JavaScript
- TypeScript  
- Java
- Go
- Rust

## 🔄 Workflow

1. **Traverse**: Discover and catalog source files
2. **Document**: Create language-agnostic specifications
3. **Review** (optional): Human validation of specifications
4. **Translate**: Generate target language code
5. **Output**: Save translated files with proper structure

## 🧪 Testing

Run the example translation:

```bash
python examples/run_example.py
```

This will translate the sample Python code to JavaScript and show the complete workflow.

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Add support for new languages in the appropriate agent
4. Update language mappings and requirements
5. Submit a pull request

## 📜 License

MIT License - see LICENSE file for details

## 🔗 Dependencies

- LangGraph: Multi-agent workflow orchestration
- LangChain: LLM integration and prompting
- Pydantic: Data validation and settings
- Tree-sitter: Code parsing (when available)
- Rich: Beautiful terminal output
- PyYAML: Configuration management
- AsyncPG: PostgreSQL database connectivity (optional)

## 🚨 Known Limitations

- Complex metaprogramming may not translate perfectly
- Some language-specific features may need manual adjustment
- Large codebases may require API rate limiting considerations
- Translation quality depends on LLM capability and prompt engineering

## 📞 Support

For issues and feature requests, please use the GitHub issue tracker.