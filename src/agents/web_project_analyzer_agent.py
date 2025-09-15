"""
Web Project Analyzer Agent with web browsing capabilities for framework detection.
"""
import json
import logging
from typing import Dict, Any, Optional, List
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.tools import tool
from .base_agent import BaseAgent
from ..models.hierarchical_spec import ProjectSpecification, ProjectType, ArchitecturePattern
from ..persistence.agent_checkpoint import CheckpointManager

logger = logging.getLogger(__name__)

# Define tools for web research
@tool
def search_framework_info(query: str) -> str:
    """Search for information about software frameworks, their features, and current best practices.

    Args:
        query: Search query for framework information (e.g., "Sidekiq Redis background jobs Ruby")

    Returns:
        Search results with framework information
    """
    try:
        # Use DuckDuckGo for privacy-friendly search
        from langchain_community.tools import DuckDuckGoSearchRun
        search = DuckDuckGoSearchRun()
        results = search.run(query)
        return f"Search results for '{query}':\n{results}"
    except ImportError:
        return f"Web search unavailable. Install langchain-community: pip install langchain-community"
    except Exception as e:
        return f"Search failed for '{query}': {str(e)}"

@tool
def get_framework_documentation(framework_name: str) -> str:
    """Get official documentation or GitHub information for a specific framework.

    Args:
        framework_name: Name of the framework (e.g., "asynq", "celery", "sidekiq")

    Returns:
        Documentation summary and key features
    """
    try:
        from langchain_community.tools import DuckDuckGoSearchRun
        search = DuckDuckGoSearchRun()

        # Search for official docs
        docs_query = f"{framework_name} official documentation features API"
        docs_results = search.run(docs_query)

        # Search for GitHub/source
        github_query = f"{framework_name} github repository"
        github_results = search.run(github_query)

        return f"Documentation for {framework_name}:\n\nOfficial Docs:\n{docs_results}\n\nRepository Info:\n{github_results}"
    except ImportError:
        return f"Web search unavailable. Install langchain-community: pip install langchain-community"
    except Exception as e:
        return f"Documentation search failed for '{framework_name}': {str(e)}"

@tool
def check_framework_versions(framework_name: str, language: str) -> str:
    """Check current versions and compatibility for a framework in a specific language.

    Args:
        framework_name: Framework to check (e.g., "rails", "django", "express")
        language: Programming language (e.g., "ruby", "python", "javascript")

    Returns:
        Version information and compatibility notes
    """
    try:
        from langchain_community.tools import DuckDuckGoSearchRun
        search = DuckDuckGoSearchRun()

        version_query = f"{framework_name} {language} latest version 2024 current"
        results = search.run(version_query)

        return f"Version info for {framework_name} ({language}):\n{results}"
    except ImportError:
        return f"Web search unavailable. Install langchain-community: pip install langchain-community"
    except Exception as e:
        return f"Version check failed for '{framework_name}': {str(e)}"


class WebProjectAnalyzerAgent(BaseAgent):
    """Enhanced Project Analyzer with web browsing for current framework information."""

    def __init__(self, checkpoint_manager: Optional[CheckpointManager] = None, **kwargs):
        # Set up tools
        tools = [search_framework_info, get_framework_documentation, check_framework_versions]

        # Initialize parent with tools
        super().__init__(tools=tools, **kwargs)
        self.checkpoint_manager = checkpoint_manager

    def get_prompt(self) -> ChatPromptTemplate:
        return ChatPromptTemplate.from_messages([
            ("system", """You are a software architecture expert with web browsing capabilities to research current frameworks.

            You can use these tools to gather up-to-date information:
            - search_framework_info: Search for framework information and best practices
            - get_framework_documentation: Get official documentation for specific frameworks
            - check_framework_versions: Check current versions and compatibility

            Use these tools BEFORE making your analysis to ensure you have current information about:
            - Framework names and categories
            - Current versions and features
            - Best practices and patterns
            - Compatibility and dependencies

            After gathering information, analyze the project and return ONLY valid JSON:

            {{
              "project_type": "web_api|cli|background_worker|library|desktop_app|mobile_app|microservice|monolith|unknown",
              "architecture": "mvc|layered|domain_driven|microservices|event_driven|hexagonal|serverless|monolithic|unknown",
              "description": "Brief description of what this application does",
              "technology_stack": ["framework1", "database1", "tool1"],
              "primary_framework": {{
                "name": "detected_framework_name",
                "version": "detected_version_or_null",
                "category": "worker|web_api|web_full|cli|orm|testing|microservice|unknown",
                "confidence": 0.0_to_1.0,
                "source": "file_analysis|web_research|both"
              }},
              "frameworks_detected": [
                {{"name": "framework_name", "category": "category", "confidence": 0.0_to_1.0, "evidence": "what indicated this framework"}}
              ],
              "entry_points": ["main.py", "server.js", "index.ts"],
              "key_directories": {{
                "handlers": "path/to/handlers",
                "services": "path/to/services",
                "models": "path/to/models",
                "config": "path/to/config"
              }},
              "indicators": {{
                "has_web_server": true/false,
                "has_cli_interface": true/false,
                "has_database": true/false,
                "has_api_routes": true/false,
                "has_background_jobs": true/false,
                "has_message_queue": true/false,
                "has_ui_components": true/false
              }},
              "web_research_summary": "Summary of findings from web research tools"
            }}

            PROCESS:
            1. First analyze the provided files to identify potential frameworks
            2. Use web tools to research any frameworks you identify
            3. Cross-reference file patterns with current framework information
            4. Provide final analysis with high confidence based on both sources

            """),

            ("human", """Analyze this project structure with web research:

            Root Path: {root_path}

            Files Found:
            {file_list}

            Key File Contents:
            {file_contents}

            Please research any frameworks you identify and provide a comprehensive analysis.""")
        ])

    async def process(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Process project analysis with web research capabilities."""
        project_root = state.get('project_root')
        if not project_root:
            logger.error("No project root provided")
            state['errors'].append({
                "agent": "enhanced_project_analyzer",
                "error": "Missing project root"
            })
            return state

        # Check for existing checkpoint
        if self.checkpoint_manager:
            resume_point = self.checkpoint_manager.get_resume_point("enhanced_project_analyzer")
            if resume_point['status'] == 'completed':
                logger.info("Enhanced project analysis already completed, using checkpoint")
                state['project_spec'] = resume_point['state'].get('project_spec')
                return state

        self.log_action(f"Analyzing project structure at: {project_root}")

        try:
            # Gather file information
            file_list, file_contents = self._gather_project_info(project_root)

            # Create prompt with project information
            prompt = self.get_prompt()
            chain = prompt | self.llm

            # Note: The LLM will automatically have access to tools and can use them during analysis
            response = await chain.ainvoke({
                "root_path": project_root,
                "file_list": file_list,
                "file_contents": file_contents
            })

            # Parse the response
            analysis = self._parse_analysis_response(response.content)

            # Create project specification
            project_spec = self._create_project_specification(analysis, project_root)

            # Store in state
            state['project_spec'] = project_spec
            state['project_type'] = project_spec.project_type
            state['architecture'] = project_spec.architecture

            # Checkpoint the completed analysis
            if self.checkpoint_manager:
                self.checkpoint_manager.save_agent_state(
                    "enhanced_project_analyzer",
                    {"project_spec": project_spec},
                    {"status": "completed"},
                    phase="completed"
                )

            self.log_action(f"Identified project type: {project_spec.project_type}, Architecture: {project_spec.architecture}")

        except Exception as e:
            logger.error(f"Error analyzing project: {e}")
            state['errors'].append({
                "agent": "enhanced_project_analyzer",
                "error": str(e)
            })

        return state

    def _gather_project_info(self, project_root: str) -> tuple[str, str]:
        """Gather file list and key file contents for analysis."""
        import os
        from pathlib import Path

        project_path = Path(project_root)
        files = []
        file_contents = {}

        # Key files to examine
        key_files = [
            'Gemfile', 'package.json', 'requirements.txt', 'go.mod', 'pom.xml',
            'Cargo.toml', 'composer.json', 'build.gradle', 'setup.py',
            'config/application.rb', 'manage.py', 'app.js', 'main.go',
            'src/main/java', 'server.js', 'index.js', 'main.py'
        ]

        # Collect all files
        for root, dirs, file_names in os.walk(project_path):
            # Skip hidden and build directories
            dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ['node_modules', 'target', 'build', '__pycache__']]

            for file_name in file_names:
                if not file_name.startswith('.'):
                    rel_path = os.path.relpath(os.path.join(root, file_name), project_path)
                    files.append(rel_path)

        file_list = "\n".join(files[:50])  # Limit to first 50 files

        # Read key files
        for key_file in key_files:
            file_path = project_path / key_file
            if file_path.exists() and file_path.is_file():
                try:
                    content = file_path.read_text(encoding='utf-8')[:2000]  # First 2KB
                    file_contents[key_file] = content
                except Exception as e:
                    file_contents[key_file] = f"Error reading file: {e}"

        # Also check some source files for patterns
        for file_rel_path in files[:20]:  # Check first 20 files
            if any(file_rel_path.endswith(ext) for ext in ['.rb', '.py', '.js', '.go', '.java']):
                file_path = project_path / file_rel_path
                try:
                    content = file_path.read_text(encoding='utf-8')[:1000]  # First 1KB
                    file_contents[file_rel_path] = content
                except Exception:
                    continue

        contents_str = "\n\n".join([f"=== {path} ===\n{content}" for path, content in file_contents.items()])

        return file_list, contents_str

    def _parse_analysis_response(self, response_content: str) -> Dict[str, Any]:
        """Parse the LLM response into structured data."""
        # Remove code block markers if present
        content = response_content.strip()
        if content.startswith('```json'):
            content = content[7:]
        if content.startswith('```'):
            content = content[3:]
        if content.endswith('```'):
            content = content[:-3]

        try:
            return json.loads(content.strip())
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {e}")
            logger.error(f"Response content: {content}")
            raise ValueError(f"Invalid JSON response from LLM: {e}")

    def _create_project_specification(self, analysis: Dict[str, Any], project_root: str) -> ProjectSpecification:
        """Create ProjectSpecification from analysis results."""
        try:
            project_type = ProjectType(analysis.get('project_type', 'unknown'))
        except ValueError:
            project_type = ProjectType.UNKNOWN

        try:
            architecture = ArchitecturePattern(analysis.get('architecture', 'unknown'))
        except ValueError:
            architecture = ArchitecturePattern.UNKNOWN

        return ProjectSpecification(
            project_name=Path(project_root).name,
            project_root=project_root,
            project_type=project_type,
            architecture=architecture,
            primary_language=self._detect_primary_language(analysis),
            technology_stack=analysis.get('technology_stack', []),
            description=analysis.get('description', ''),
            entry_points=analysis.get('entry_points', []),
            folder_structure=analysis.get('key_directories', {}),
            external_dependencies=self._extract_external_deps(analysis)
        )

    def _detect_primary_language(self, analysis: Dict[str, Any]) -> str:
        """Detect primary programming language from analysis."""
        tech_stack = analysis.get('technology_stack', [])

        # Language indicators
        if any('ruby' in tech.lower() or 'rails' in tech.lower() or 'sidekiq' in tech.lower() for tech in tech_stack):
            return 'ruby'
        elif any('python' in tech.lower() or 'django' in tech.lower() or 'flask' in tech.lower() for tech in tech_stack):
            return 'python'
        elif any('javascript' in tech.lower() or 'node' in tech.lower() or 'express' in tech.lower() for tech in tech_stack):
            return 'javascript'
        elif any('go' in tech.lower() or 'golang' in tech.lower() for tech in tech_stack):
            return 'go'
        elif any('java' in tech.lower() or 'spring' in tech.lower() for tech in tech_stack):
            return 'java'
        else:
            return 'unknown'

    def _extract_external_deps(self, analysis: Dict[str, Any]) -> List[str]:
        """Extract external dependencies from analysis."""
        deps = []
        tech_stack = analysis.get('technology_stack', [])

        for tech in tech_stack:
            tech_lower = tech.lower()
            if any(db in tech_lower for db in ['redis', 'postgres', 'mysql', 'mongodb']):
                deps.append(tech)

        return deps