"""
ProjectAnalyzer Agent - Determines application type, architecture, and overall structure.
"""
import json
from typing import Dict, List, Any, Optional
from pathlib import Path
from langchain_core.prompts import ChatPromptTemplate
from .base_agent import BaseAgent
from ..models.hierarchical_spec import (
    ProjectSpecification, ProjectType, ArchitecturePattern,
    FolderSpecification, FolderPurpose
)
from ..persistence.agent_checkpoint import CheckpointManager
import logging

logger = logging.getLogger(__name__)


class ProjectAnalyzerAgent(BaseAgent):
    """Analyzes project structure to determine application type and architecture."""
    
    def __init__(self, checkpoint_manager: Optional[CheckpointManager] = None, **kwargs):
        super().__init__(**kwargs)
        self.checkpoint_manager = checkpoint_manager
    
    def get_prompt(self) -> ChatPromptTemplate:
        return ChatPromptTemplate.from_messages([
            ("system", """You are a software architecture expert analyzing a codebase to determine its type, structure, and frameworks.

            Analyze the provided project information and return ONLY valid JSON:

            {{
              "project_type": "web_api|cli|background_worker|library|desktop_app|mobile_app|microservice|monolith|unknown",
              "architecture": "mvc|layered|domain_driven|microservices|event_driven|hexagonal|serverless|monolithic|unknown",
              "description": "Brief description of what this application does",
              "technology_stack": ["framework1", "database1", "tool1"],
              "primary_framework": {{
                "name": "detected_framework_name",
                "version": "detected_version_or_null",
                "category": "worker|web_api|web_full|cli|orm|testing|microservice|unknown"
              }},
              "frameworks_detected": [
                {{"name": "framework_name", "category": "category", "confidence": 0.0_to_1.0}},
                {{"name": "another_framework", "category": "category", "confidence": 0.0_to_1.0}}
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
              }}
            }}

            FRAMEWORK DETECTION PATTERNS:

            Look for these patterns to identify frameworks and their categories:

            Worker/Background Job Patterns:
            - Job queue libraries in dependencies (sidekiq, celery, bull, resque, etc.)
            - Worker classes that inherit from framework base classes
            - Job/task decorators (@app.task, include Sidekiq::Worker, etc.)
            - Queue-related imports and Redis/message broker usage

            Web Framework Patterns:
            - HTTP routing libraries and route definitions
            - Controller/handler classes and REST endpoint patterns
            - Web server startup code and middleware configuration
            - Template engines and static file serving

            CLI Framework Patterns:
            - Command-line parsing libraries (cobra, click, thor, commander, etc.)
            - Argument parsing and subcommand definitions
            - Console applications without web servers

            ORM/Database Patterns:
            - Database model definitions and schema files
            - Migration files and database configuration
            - ORM imports (ActiveRecord, SQLAlchemy, Mongoose, GORM, etc.)

            Testing Framework Patterns:
            - Test file naming conventions (*_test.*, test_*.*, *.spec.*)
            - Testing library imports (RSpec, pytest, Jest, etc.)
            - Test configuration and setup files

            PROJECT TYPE DETECTION RULES:
            - web_api: Has HTTP routes, controllers, REST/GraphQL endpoints
            - cli: Has command parsers, console interface, no web server
            - background_worker: Has job queues, scheduled tasks, workers
            - library: No main entry point, meant to be imported
            - microservice: Small, focused service with API
            - monolith: Large application with many features

            ARCHITECTURE DETECTION RULES:
            - mvc: Separate models, views, controllers directories
            - layered: Controllers → Services → Repositories pattern
            - domain_driven: Domain models, aggregates, repositories
            - event_driven: Event handlers, message bus, pub/sub
            - hexagonal: Ports and adapters pattern

            CRITICAL: Analyze file contents, not just names. Look for import statements, class inheritance,
            and framework-specific patterns to determine frameworks with high confidence."""),
            
            ("human", """Analyze this project structure:

            Root Path: {root_path}
            
            Configuration Files Found:
            {config_files}
            
            Directory Structure (top 2 levels):
            {directory_structure}
            
            Sample Entry Files:
            {entry_files}
            
            File Statistics:
            {file_stats}
            
            Return ONLY the JSON analysis.""")
        ])
    
    async def process(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze project to determine type and architecture."""
        root_path = Path(state.get('root_path', '.'))
        
        # Check for existing checkpoint
        if self.checkpoint_manager:
            resume_point = self.checkpoint_manager.get_resume_point("project_analyzer")
            if resume_point['status'] == 'completed':
                logger.info("Project analysis already completed, using checkpoint")
                state['project_spec'] = resume_point['state'].get('project_spec')
                return state
        
        self.log_action(f"Analyzing project structure at: {root_path}")
        
        try:
            # Gather project information
            config_files = self._find_config_files(root_path)
            directory_structure = self._get_directory_structure(root_path)
            entry_files = self._find_entry_points(root_path)
            file_stats = self._calculate_file_stats(root_path)
            
            # Analyze with LLM
            project_analysis = await self._analyze_project(
                root_path,
                config_files,
                directory_structure,
                entry_files,
                file_stats
            )
            
            # Create project specification
            project_spec = self._create_project_spec(root_path, project_analysis)
            
            # Save to state
            state['project_spec'] = project_spec
            state['project_type'] = project_spec.project_type
            state['architecture'] = project_spec.architecture
            
            # Checkpoint the completed analysis
            if self.checkpoint_manager:
                self.checkpoint_manager.save_agent_state(
                    "project_analyzer",
                    {"project_spec": project_spec.dict()},
                    {"status": "completed"},
                    phase="completed"
                )
            
            self.log_action(f"Identified project type: {project_spec.project_type}, Architecture: {project_spec.architecture}")
            
        except Exception as e:
            logger.error(f"Error analyzing project: {e}")
            state['errors'].append({
                "agent": "project_analyzer",
                "error": str(e)
            })
        
        return state
    
    def _find_config_files(self, root_path: Path) -> List[Dict[str, str]]:
        """Find configuration files that indicate project type."""
        config_patterns = [
            "package.json", "pom.xml", "build.gradle", "project.clj",
            "Cargo.toml", "go.mod", "requirements.txt", "Gemfile",
            "composer.json", "*.csproj", "Makefile", "Dockerfile",
            "docker-compose.yml", ".env", "config.yaml", "settings.py"
        ]
        
        config_files = []
        for pattern in config_patterns:
            for file in root_path.glob(pattern):
                if file.is_file():
                    # Read first few lines for context
                    try:
                        with open(file, 'r', encoding='utf-8', errors='ignore') as f:
                            content = f.read(500)  # First 500 chars
                        config_files.append({
                            "name": file.name,
                            "path": str(file.relative_to(root_path)),
                            "preview": content[:200]
                        })
                    except Exception:
                        config_files.append({
                            "name": file.name,
                            "path": str(file.relative_to(root_path)),
                            "preview": ""
                        })
        
        return config_files
    
    def _get_directory_structure(self, root_path: Path, max_depth: int = 2) -> str:
        """Get directory structure up to specified depth."""
        def build_tree(path: Path, prefix: str = "", depth: int = 0) -> List[str]:
            if depth >= max_depth:
                return []
            
            lines = []
            try:
                items = sorted(path.iterdir(), key=lambda p: (not p.is_dir(), p.name))
                for i, item in enumerate(items[:20]):  # Limit to 20 items per level
                    if item.name.startswith('.'):
                        continue
                    
                    is_last = i == len(items) - 1
                    current = "└── " if is_last else "├── "
                    
                    if item.is_dir():
                        lines.append(f"{prefix}{current}{item.name}/")
                        if depth < max_depth - 1:
                            extension = "    " if is_last else "│   "
                            lines.extend(build_tree(item, prefix + extension, depth + 1))
                    else:
                        lines.append(f"{prefix}{current}{item.name}")
            except PermissionError:
                pass
            
            return lines
        
        tree_lines = build_tree(root_path)
        return "\n".join(tree_lines[:50])  # Limit total lines
    
    def _find_entry_points(self, root_path: Path) -> List[Dict[str, str]]:
        """Find potential entry point files."""
        entry_patterns = [
            "main.*", "index.*", "app.*", "server.*", "cli.*",
            "run.*", "start.*", "__main__.py", "cmd/*"
        ]
        
        entry_files = []
        for pattern in entry_patterns:
            for file in root_path.rglob(pattern):
                if file.is_file() and not any(skip in str(file) for skip in ['node_modules', '.git', '__pycache__']):
                    try:
                        with open(file, 'r', encoding='utf-8', errors='ignore') as f:
                            # Read first few lines
                            lines = f.readlines()[:10]
                            content = "".join(lines)
                        
                        entry_files.append({
                            "name": file.name,
                            "path": str(file.relative_to(root_path)),
                            "preview": content[:200]
                        })
                    except Exception:
                        pass
        
        return entry_files[:10]  # Limit to 10 entries
    
    def _calculate_file_stats(self, root_path: Path) -> Dict[str, Any]:
        """Calculate file statistics for the project."""
        stats = {
            "total_files": 0,
            "by_extension": {},
            "by_directory": {}
        }
        
        for file in root_path.rglob('*'):
            if file.is_file() and not any(skip in str(file) for skip in ['node_modules', '.git', '__pycache__']):
                stats["total_files"] += 1
                
                ext = file.suffix
                stats["by_extension"][ext] = stats["by_extension"].get(ext, 0) + 1
                
                dir_name = file.parent.name
                if dir_name:
                    stats["by_directory"][dir_name] = stats["by_directory"].get(dir_name, 0) + 1
        
        # Sort and limit
        stats["by_extension"] = dict(sorted(stats["by_extension"].items(), key=lambda x: x[1], reverse=True)[:10])
        stats["by_directory"] = dict(sorted(stats["by_directory"].items(), key=lambda x: x[1], reverse=True)[:10])
        
        return stats
    
    async def _analyze_project(
        self,
        root_path: Path,
        config_files: List[Dict],
        directory_structure: str,
        entry_files: List[Dict],
        file_stats: Dict
    ) -> Dict[str, Any]:
        """Use LLM to analyze project structure."""
        prompt = self.get_prompt()
        chain = prompt | self.llm
        
        # Format inputs
        config_str = json.dumps(config_files, indent=2)[:1000]
        entry_str = json.dumps(entry_files, indent=2)[:1000]
        stats_str = json.dumps(file_stats, indent=2)
        
        response = await chain.ainvoke({
            "root_path": str(root_path),
            "config_files": config_str,
            "directory_structure": directory_structure,
            "entry_files": entry_str,
            "file_stats": stats_str
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
    
    def _create_project_spec(self, root_path: Path, analysis: Dict[str, Any]) -> ProjectSpecification:
        """Create project specification from analysis."""
        from datetime import datetime
        
        # Create root folder spec (will be enhanced by TraverserAgent)
        root_folder = FolderSpecification(
            path=".",
            name=root_path.name,
            purpose=FolderPurpose.UNKNOWN,
            description="Project root directory"
        )
        
        return ProjectSpecification(
            project_name=root_path.name,
            project_root=str(root_path),
            project_type=ProjectType(analysis.get('project_type', 'unknown')),
            architecture=ArchitecturePattern(analysis.get('architecture', 'unknown')),
            description=analysis.get('description', ''),
            primary_language="",  # Will be set by TraverserAgent
            technology_stack=analysis.get('technology_stack', []),
            entry_points=analysis.get('entry_points', []),
            folder_structure=root_folder,
            handlers_path=analysis.get('key_directories', {}).get('handlers'),
            services_path=analysis.get('key_directories', {}).get('services'),
            models_path=analysis.get('key_directories', {}).get('models'),
            config_path=analysis.get('key_directories', {}).get('config'),
            analysis_timestamp=datetime.now().isoformat()
        )