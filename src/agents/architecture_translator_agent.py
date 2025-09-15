"""
Architecture Translator Agent - Translates project architecture and generates framework scaffolding.
"""
import json
import logging
from typing import Dict, List, Any, Optional, Tuple
from pathlib import Path
from langchain_core.prompts import ChatPromptTemplate
from .base_agent import BaseAgent
from ..models.hierarchical_spec import ProjectSpecification, ProjectType
from ..persistence.agent_checkpoint import CheckpointManager

logger = logging.getLogger(__name__)


class ArchitectureTranslatorAgent(BaseAgent):
    """Translates project architecture patterns to target language equivalents."""

    def __init__(self, checkpoint_manager: Optional[CheckpointManager] = None, **kwargs):
        super().__init__(**kwargs)
        self.checkpoint_manager = checkpoint_manager
        self.framework_mappings = self._load_framework_mappings()

    def get_prompt(self) -> ChatPromptTemplate:
        return ChatPromptTemplate.from_messages([
            ("system", """You are an expert software architect specializing in framework migration and architectural translation.

            Your job is to translate project architecture from one framework/language to another, creating a complete,
            runnable project structure with proper framework setup.

            Return ONLY valid JSON with this structure:

            {{
              "target_framework": "framework_name",
              "target_framework_version": "version",
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

            CRITICAL: The scaffolding_files section should contain the ACTUAL file contents as strings, not templates.
            Generate complete, working code that follows the target framework's best practices.

            Framework Selection Principles:

            For Worker/Background Job Frameworks:
            - Identify the core messaging pattern (Redis queues, AMQP, etc.)
            - Match reliability features (retries, error handling, scheduling)
            - Consider scaling patterns (worker pools, concurrency)

            For Web Frameworks:
            - Match architectural style (full-stack vs API-only vs microservice)
            - Consider routing patterns (convention vs explicit)
            - Match middleware/plugin ecosystems

            For CLI Frameworks:
            - Match command structure complexity (simple vs nested subcommands)
            - Consider argument parsing sophistication
            - Match help/documentation generation needs

            Examples of good matches:
            - Redis-based job queues → Redis-based equivalents (sidekiq → asynq, bull → asynq)
            - Full-stack MVC → Full-stack MVC (rails → django, django → rails)
            - Lightweight API frameworks → Lightweight API frameworks (express → gin, fastapi → gin)
            - Enterprise frameworks → Enterprise frameworks (spring → go-kit/kratos)

            For each target framework, generate appropriate:
            1. Main entry point with framework initialization
            2. Configuration management
            3. Dependency management files
            4. Base worker/handler classes if applicable
            5. Directory structure following target language conventions

            """),

            ("human", """Translate this architecture to {target_language}:

            Source: {framework} ({project_type})
            Technology Stack: {tech_stack}
            Dependencies: {dependencies}
            Features: {features}

            Generate complete project scaffolding with working code.""")
        ])

    async def process(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Translate project architecture to target language/framework."""
        project_spec = state.get('project_spec')
        target_language = state.get('target_language')

        if not project_spec:
            logger.error("No project specification found")
            state['errors'].append({
                "agent": "architecture_translator",
                "error": "Missing project specification"
            })
            return state

        # Check for existing checkpoint
        if self.checkpoint_manager:
            resume_point = self.checkpoint_manager.get_resume_point("architecture_translator")
            if resume_point['status'] == 'completed':
                logger.info("Architecture translation already completed, using checkpoint")
                state['architecture_translation'] = resume_point['state'].get('architecture_translation')
                return state

        self.log_action(f"Translating architecture from {project_spec.primary_language} to {target_language}")

        try:
            # Detect source framework
            source_framework = self._detect_framework(project_spec, state)

            # Get architectural translation
            translation = await self._translate_architecture(
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
                'migration_notes': translation.get('migration_notes', [])
            }

            # Checkpoint the completed translation
            if self.checkpoint_manager:
                self.checkpoint_manager.save_agent_state(
                    "architecture_translator",
                    {"architecture_translation": state['architecture_translation']},
                    {"status": "completed"},
                    phase="completed"
                )

            self.log_action(f"Selected target framework: {translation['target_framework']}")

        except Exception as e:
            logger.error(f"Error translating architecture: {e}")
            state['errors'].append({
                "agent": "architecture_translator",
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

        # Check technology stack for framework indicators
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
        if project_spec.project_type == ProjectType.BACKGROUND_WORKER:
            if framework_info['name'] == 'unknown':
                # Infer worker framework based on language
                if project_spec.primary_language == 'ruby':
                    framework_info['name'] = 'sidekiq'
                elif project_spec.primary_language == 'python':
                    framework_info['name'] = 'celery'
                elif project_spec.primary_language == 'javascript':
                    framework_info['name'] = 'bull'

        return framework_info

    async def _translate_architecture(
        self,
        project_spec: ProjectSpecification,
        source_framework: Dict[str, Any],
        target_language: str,
        state: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Use LLM to determine target architecture."""
        prompt = self.get_prompt()
        chain = prompt | self.llm

        # Prepare input data
        features = source_framework.get('features', [])
        dependencies = self._extract_dependencies(project_spec, state)

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

    def _load_framework_mappings(self) -> Dict[str, Dict[str, str]]:
        """Load framework mapping database."""
        return {
            'worker_frameworks': {
                'sidekiq': {'go': 'asynq', 'python': 'celery', 'javascript': 'bull'},
                'celery': {'go': 'machinery', 'javascript': 'bull', 'ruby': 'sidekiq'},
                'bull': {'go': 'asynq', 'python': 'celery', 'ruby': 'sidekiq'},
            },
            'web_frameworks': {
                'rails': {'go': 'gin', 'python': 'django', 'javascript': 'express'},
                'django': {'go': 'fiber', 'javascript': 'express', 'ruby': 'rails'},
                'express': {'go': 'gin', 'python': 'fastapi', 'ruby': 'sinatra'},
                'spring': {'go': 'go-kit', 'python': 'fastapi', 'javascript': 'nestjs'},
            },
            'cli_frameworks': {
                'thor': {'go': 'cobra', 'python': 'click', 'javascript': 'commander'},
                'click': {'go': 'cobra', 'javascript': 'commander', 'ruby': 'thor'},
                'commander': {'go': 'cobra', 'python': 'click', 'ruby': 'thor'},
            }
        }