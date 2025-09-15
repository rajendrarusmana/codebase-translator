"""
Web Architecture Translator Agent with web research for current framework information.
"""
import json
import logging
from typing import Dict, List, Any, Optional
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.tools import tool
from .base_agent import BaseAgent
from ..models.hierarchical_spec import ProjectSpecification
from ..persistence.agent_checkpoint import CheckpointManager

logger = logging.getLogger(__name__)

# Define tools for architecture research
@tool
def research_target_frameworks(source_framework: str, target_language: str) -> str:
    """Research equivalent frameworks in the target language for a given source framework.

    Args:
        source_framework: Source framework name (e.g., "sidekiq", "django", "express")
        target_language: Target programming language (e.g., "go", "python", "javascript")

    Returns:
        Information about equivalent frameworks in the target language
    """
    try:
        from langchain_community.tools import DuckDuckGoSearchRun
        search = DuckDuckGoSearchRun()

        query = f"{source_framework} equivalent {target_language} alternative framework migration"
        results = search.run(query)

        return f"Equivalent frameworks for {source_framework} in {target_language}:\n{results}"
    except ImportError:
        return f"Web search unavailable. Install langchain-community: pip install langchain-community"
    except Exception as e:
        return f"Framework research failed: {str(e)}"

@tool
def get_framework_best_practices(framework_name: str, language: str) -> str:
    """Get current best practices and patterns for a specific framework.

    Args:
        framework_name: Framework to research (e.g., "asynq", "gin", "fastapi")
        language: Programming language (e.g., "go", "python", "javascript")

    Returns:
        Best practices, patterns, and setup recommendations
    """
    try:
        from langchain_community.tools import DuckDuckGoSearchRun
        search = DuckDuckGoSearchRun()

        query = f"{framework_name} {language} best practices setup patterns 2024"
        results = search.run(query)

        return f"Best practices for {framework_name} ({language}):\n{results}"
    except ImportError:
        return f"Web search unavailable. Install langchain-community: pip install langchain-community"
    except Exception as e:
        return f"Best practices research failed: {str(e)}"

@tool
def check_framework_compatibility(framework_name: str, language: str) -> str:
    """Check compatibility, current versions, and dependencies for a framework.

    Args:
        framework_name: Framework to check (e.g., "asynq", "machinery", "celery")
        language: Programming language (e.g., "go", "python")

    Returns:
        Compatibility information, versions, and dependencies
    """
    try:
        from langchain_community.tools import DuckDuckGoSearchRun
        search = DuckDuckGoSearchRun()

        query = f"{framework_name} {language} latest version dependencies compatibility requirements"
        results = search.run(query)

        return f"Compatibility info for {framework_name} ({language}):\n{results}"
    except ImportError:
        return f"Web search unavailable. Install langchain-community: pip install langchain-community"
    except Exception as e:
        return f"Compatibility check failed: {str(e)}"

@tool
def research_migration_patterns(source_framework: str, target_framework: str) -> str:
    """Research migration patterns and examples from source to target framework.

    Args:
        source_framework: Source framework (e.g., "sidekiq", "rails")
        target_framework: Target framework (e.g., "asynq", "gin")

    Returns:
        Migration patterns, examples, and common mappings
    """
    try:
        from langchain_community.tools import DuckDuckGoSearchRun
        search = DuckDuckGoSearchRun()

        query = f"migrate {source_framework} to {target_framework} examples patterns guide"
        results = search.run(query)

        return f"Migration patterns from {source_framework} to {target_framework}:\n{results}"
    except ImportError:
        return f"Web search unavailable. Install langchain-community: pip install langchain-community"
    except Exception as e:
        return f"Migration research failed: {str(e)}"


class WebArchitectureTranslatorAgent(BaseAgent):
    """Web Architecture Translator with web research capabilities."""

    def __init__(self, checkpoint_manager: Optional[CheckpointManager] = None, **kwargs):
        # Set up tools
        tools = [
            research_target_frameworks,
            get_framework_best_practices,
            check_framework_compatibility,
            research_migration_patterns
        ]

        # Initialize parent with tools
        super().__init__(tools=tools, **kwargs)
        self.checkpoint_manager = checkpoint_manager

    def get_prompt(self) -> ChatPromptTemplate:
        return ChatPromptTemplate.from_messages([
            ("system", """You are an expert software architect with web research capabilities for framework migration.

            You have access to these research tools:
            - research_target_frameworks: Find equivalent frameworks in target language
            - get_framework_best_practices: Get current best practices for frameworks
            - check_framework_compatibility: Check versions and compatibility requirements
            - research_migration_patterns: Find migration examples and patterns

            PROCESS:
            1. Research equivalent frameworks for the source framework in the target language
            2. Check best practices and current patterns for top candidates
            3. Verify compatibility and version requirements
            4. Research specific migration patterns if available
            5. Generate complete project scaffolding based on research

            Return ONLY valid JSON with this structure:

            {{
              "target_framework": "framework_name",
              "target_framework_version": "version",
              "framework_research_summary": "Summary of web research findings",
              "dependencies": [
                {{"name": "dependency", "version": "version", "purpose": "description"}}
              ],
              "project_structure": {{
                "directories": ["path1", "path2"],
                "files": [
                  {{"path": "file.ext", "purpose": "description", "generate": true}}
                ]
              }},
              "scaffolding_files": {{
                "go.mod": "module worker\\n\\ngo 1.21\\n\\nrequire (\\n\\tgithub.com/hibiken/asynq v0.24.1\\n)",
                "main.go": "package main\\n\\nimport (\\n\\t\"log\"\\n\\t\"github.com/hibiken/asynq\"\\n)\\n\\nfunc main() {{\\n\\t// Setup code here\\n}}",
                "config.go": "package config\\n\\ntype Config struct {{\\n\\tRedisAddr string\\n}}"
              }},
              "architectural_mappings": {{
                "sidekiq_worker": "asynq_handler",
                "perform": "ProcessTask"
              }},
              "migration_notes": ["note1", "note2"]
            }}

            CRITICAL:
            - Use web research to ensure you select the BEST current framework
            - Generate scaffolding that follows CURRENT best practices
            - Include actual working code based on latest patterns
            - Consider framework popularity, maintenance, and community support

            """),

            ("human", """Research and translate this architecture to {target_language}:

            Source: {framework} ({project_type})
            Technology Stack: {tech_stack}
            Dependencies: {dependencies}
            Features: {features}

            Use web research to find the best target framework and generate current scaffolding.""")
        ])

    async def process(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Translate project architecture with web research capabilities."""
        project_spec = state.get('project_spec')
        target_language = state.get('target_language')

        if not project_spec:
            logger.error("No project specification found")
            state['errors'].append({
                "agent": "enhanced_architecture_translator",
                "error": "Missing project specification"
            })
            return state

        # Check for existing checkpoint
        if self.checkpoint_manager:
            resume_point = self.checkpoint_manager.get_resume_point("enhanced_architecture_translator")
            if resume_point['status'] == 'completed':
                logger.info("Enhanced architecture translation already completed, using checkpoint")
                state['architecture_translation'] = resume_point['state'].get('architecture_translation')
                return state

        self.log_action(f"Translating architecture with web research from {project_spec.primary_language} to {target_language}")

        try:
            # Detect source framework
            source_framework = self._detect_framework(project_spec, state)

            # Get architectural translation using web research
            translation = await self._translate_architecture_with_research(
                project_spec,
                source_framework,
                target_language,
                state
            )

            # Store in state - scaffolding files come directly from LLM response
            state['architecture_translation'] = {
                'source_framework': source_framework,
                'target_framework': translation['target_framework'],
                'dependencies': translation['dependencies'],
                'project_structure': translation['project_structure'],
                'architectural_mappings': translation['architectural_mappings'],
                'scaffolding_files': translation.get('scaffolding_files', {}),
                'migration_notes': translation.get('migration_notes', []),
                'research_summary': translation.get('framework_research_summary', '')
            }

            # Write scaffolding files to output directory
            scaffolding_files = translation.get('scaffolding_files', {})
            if scaffolding_files:
                from pathlib import Path
                output_path = Path(state.get('target_output_path', state.get('output_path', 'translated')))
                output_path.mkdir(parents=True, exist_ok=True)

                files_written = 0
                for file_path, content in scaffolding_files.items():
                    full_path = output_path / file_path
                    full_path.parent.mkdir(parents=True, exist_ok=True)
                    with open(full_path, 'w', encoding='utf-8') as f:
                        f.write(content)
                    files_written += 1

                logger.info(f"Generated {files_written} research-based scaffolding files in {output_path}")

            # Checkpoint the completed translation
            if self.checkpoint_manager:
                self.checkpoint_manager.save_agent_state(
                    "enhanced_architecture_translator",
                    {"architecture_translation": state['architecture_translation']},
                    {"status": "completed"},
                    phase="completed"
                )

            self.log_action(f"Selected target framework: {translation['target_framework']} (research-based)")

        except Exception as e:
            logger.error(f"Error translating architecture: {e}")
            state['errors'].append({
                "agent": "enhanced_architecture_translator",
                "error": str(e)
            })

        return state

    def _detect_framework(self, project_spec: ProjectSpecification, state: Dict[str, Any]) -> Dict[str, Any]:
        """Detect the source project's framework."""
        framework_info = {
            'name': 'unknown',
            'version': None,
            'features': []
        }

        # Check if enhanced project analyzer provided framework info
        if hasattr(project_spec, 'primary_framework'):
            primary_fw = getattr(project_spec, 'primary_framework', {})
            if isinstance(primary_fw, dict):
                framework_info['name'] = primary_fw.get('name', 'unknown')
                framework_info['version'] = primary_fw.get('version')
                return framework_info

        # Fallback to technology stack analysis
        tech_stack = project_spec.technology_stack

        # Ruby frameworks
        if 'sidekiq' in [t.lower() for t in tech_stack]:
            framework_info['name'] = 'sidekiq'
            framework_info['features'] = ['background_jobs', 'redis_queue', 'worker_pools']
        elif 'rails' in [t.lower() for t in tech_stack]:
            framework_info['name'] = 'rails'
            framework_info['features'] = ['mvc', 'active_record', 'action_controller']

        # Python frameworks
        elif 'django' in [t.lower() for t in tech_stack]:
            framework_info['name'] = 'django'
            framework_info['features'] = ['mvc', 'orm', 'admin_interface']
        elif 'celery' in [t.lower() for t in tech_stack]:
            framework_info['name'] = 'celery'
            framework_info['features'] = ['distributed_tasks', 'message_broker']
        elif 'fastapi' in [t.lower() for t in tech_stack]:
            framework_info['name'] = 'fastapi'
            framework_info['features'] = ['async', 'openapi', 'pydantic']

        # Node.js frameworks
        elif 'express' in [t.lower() for t in tech_stack]:
            framework_info['name'] = 'express'
            framework_info['features'] = ['middleware', 'routing']
        elif 'bull' in [t.lower() for t in tech_stack]:
            framework_info['name'] = 'bull'
            framework_info['features'] = ['redis_queue', 'job_processing']

        # Java frameworks
        elif 'spring' in [t.lower() for t in tech_stack]:
            framework_info['name'] = 'spring'
            framework_info['features'] = ['dependency_injection', 'mvc', 'boot']

        # Check project type for additional hints
        if project_spec.project_type.value == 'background_worker':
            if framework_info['name'] == 'unknown':
                # Infer worker framework based on language
                if project_spec.primary_language == 'ruby':
                    framework_info['name'] = 'sidekiq'
                elif project_spec.primary_language == 'python':
                    framework_info['name'] = 'celery'
                elif project_spec.primary_language == 'javascript':
                    framework_info['name'] = 'bull'

        return framework_info

    async def _translate_architecture_with_research(
        self,
        project_spec: ProjectSpecification,
        source_framework: Dict[str, Any],
        target_language: str,
        state: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Use LLM with web research tools to determine target architecture."""
        prompt = self.get_prompt()
        chain = prompt | self.llm

        # Prepare input data
        features = source_framework.get('features', [])
        dependencies = self._extract_dependencies(project_spec, state)

        # The LLM will automatically use the research tools during processing
        response = await chain.ainvoke({
            "target_language": target_language,
            "project_type": project_spec.project_type.value,
            "framework": source_framework['name'],
            "tech_stack": ", ".join(project_spec.technology_stack),
            "dependencies": ", ".join(dependencies),
            "features": ", ".join(features)
        })

        # Parse response
        content = response.content.strip()
        if content.startswith('```json'):
            content = content[7:]
        if content.startswith('```'):
            content = content[3:]
        if content.endswith('```'):
            content = content[:-3]

        return json.loads(content.strip())

    def _extract_dependencies(self, project_spec: ProjectSpecification, state: Dict[str, Any]) -> List[str]:
        """Extract external dependencies from project."""
        deps = []

        # Check technology stack for databases, caches, etc.
        for tech in project_spec.technology_stack:
            tech_lower = tech.lower()
            if 'redis' in tech_lower:
                deps.append('redis')
            elif 'postgres' in tech_lower or 'postgresql' in tech_lower:
                deps.append('postgresql')
            elif 'mysql' in tech_lower:
                deps.append('mysql')
            elif 'mongodb' in tech_lower:
                deps.append('mongodb')
            elif 'rabbitmq' in tech_lower:
                deps.append('rabbitmq')
            elif 'kafka' in tech_lower:
                deps.append('kafka')

        return deps