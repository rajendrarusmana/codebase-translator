import os
import asyncio
from pathlib import Path
from typing import Dict, List, Any, Set, Optional
from langchain_core.prompts import ChatPromptTemplate
from .base_agent import BaseAgent
from ..models.hierarchical_spec import FolderPurpose, FolderSpecification
from ..persistence.agent_checkpoint import CheckpointManager
import logging
import fnmatch
import json

logger = logging.getLogger(__name__)

class TraverserAgent(BaseAgent):
    def __init__(self, checkpoint_manager: Optional[CheckpointManager] = None, **kwargs):
        super().__init__(**kwargs)
        self.checkpoint_manager = checkpoint_manager
        self.supported_extensions = {
            '.py': 'python',
            '.js': 'javascript',
            '.ts': 'typescript',
            '.java': 'java',
            '.go': 'go',
            '.rs': 'rust',
            '.cpp': 'cpp',
            '.c': 'c',
            '.rb': 'ruby',
            '.php': 'php',
            '.clj': 'clojure',
            '.cljs': 'clojurescript',
            '.cljc': 'clojure'
        }
        self.ignore_patterns = [
            '__pycache__', '.git', 'node_modules', '.venv', 'venv',
            'dist', 'build', '.pytest_cache', '.mypy_cache',
            '*.pyc', '*.pyo', '*.pyd', '.DS_Store', '*.egg-info'
        ]
        
    def get_prompt(self) -> ChatPromptTemplate:
        return ChatPromptTemplate.from_messages([
            ("system", """You are a code analysis agent that identifies module boundaries and dependencies.
            Given a list of files, determine:
            1. The primary programming language
            2. Module boundaries and organization
            3. Entry points and main files
            4. High-level dependency relationships"""),
            ("human", "Analyze these files and provide module organization: {files}")
        ])
    
    def get_folder_analysis_prompt(self) -> ChatPromptTemplate:
        return ChatPromptTemplate.from_messages([
            ("system", """You are analyzing a folder structure to determine semantic purposes.

            Return ONLY valid JSON with this structure:
            {{
              "folders": [
                {{
                  "path": "relative/path/to/folder",
                  "purpose": "controllers|handlers|services|models|repositories|utils|config|tests|docs|views|middleware|routes|schemas|commands|events|jobs|components|templates|static|unknown",
                  "description": "Brief description of what this folder contains",
                  "confidence": 0.9
                }}
              ]
            }}

            FOLDER PURPOSE RULES:
            - controllers/handlers: HTTP request handlers, API endpoints
            - services: Business logic, application services
            - models: Data models, entities, domain objects
            - repositories: Data access layer, database queries
            - utils: Utility functions, helpers, common code
            - config: Configuration files and settings
            - tests: Test files and test utilities
            - views: UI components, templates, frontend views
            - middleware: Request/response processing middleware
            - routes: Route definitions and routing logic
            - schemas: Database schemas, API schemas, validation
            - components: Reusable UI components
            - static: Static assets (CSS, images, fonts)
            - templates: Template files (HTML, email templates)
            - docs: Documentation files
            - commands: CLI commands, scripts
            - events: Event handlers, event definitions
            - jobs: Background jobs, scheduled tasks

            Consider:
            - Folder names and their semantic meaning
            - File types and patterns within folders
            - Common architectural patterns (MVC, layered, etc.)
            - Technology-specific conventions

            JSON RULES: Double quotes only, no trailing commas."""),
            
            ("human", """Analyze this folder structure:

            Project Type: {project_type}
            Architecture: {architecture}
            Primary Language: {language}

            Folder Structure:
            {folder_structure}

            File Distribution:
            {file_distribution}

            Return ONLY the JSON analysis.""")
        ])
    
    async def process(self, state: Dict[str, Any]) -> Dict[str, Any]:
        root_path = state.get('root_path', '.')
        
        # Check for checkpoint
        if self.checkpoint_manager:
            resume_point = self.checkpoint_manager.get_resume_point("traverser")
            if resume_point['status'] == 'completed':
                logger.info("Traversal already completed, using checkpoint")
                # Merge checkpoint state with current state (don't overwrite workflow state)
                checkpoint_state = resume_point['state']
                state.update({
                    'file_paths': checkpoint_state.get('file_paths', []),
                    'source_language': checkpoint_state.get('source_language'),
                    'modules': checkpoint_state.get('modules', {}),
                    'entry_points': checkpoint_state.get('entry_points', []),
                    'folder_structure': checkpoint_state.get('folder_structure'),
                    'project_spec': checkpoint_state.get('project_spec')
                })
                return state
        
        self.log_action(f"Traversing codebase at: {root_path}")
        
        try:
            # Basic file discovery
            files = await self._discover_files(root_path)
            language = self._detect_primary_language(files)
            modules = await self._identify_modules(files, root_path)
            entry_points = self._find_entry_points(files, language)
            
            # Enhanced folder analysis
            project_spec = state.get('project_spec')
            if project_spec:
                folder_structure = await self._analyze_folder_structure(
                    root_path, files, project_spec
                )
                state['folder_structure'] = folder_structure
            
            # Update state
            state['file_paths'] = files
            state['source_language'] = language
            state['modules'] = modules
            state['entry_points'] = entry_points
            
            # Update project spec if available
            if project_spec:
                project_spec.primary_language = language
                project_spec.languages_used = list(set(
                    self.supported_extensions.get(Path(f).suffix, 'unknown') 
                    for f in files
                ))
                project_spec.total_files = len(files)
                state['project_spec'] = project_spec
            
            # Checkpoint the results
            if self.checkpoint_manager:
                self.checkpoint_manager.save_agent_state(
                    "traverser",
                    {
                        "file_paths": files,
                        "source_language": language,
                        "modules": modules,
                        "entry_points": entry_points,
                        "folder_structure": state.get('folder_structure'),
                        "project_spec": (
                            project_spec.model_dump(mode='json') if hasattr(project_spec, 'model_dump') 
                            else project_spec.dict() if project_spec else None
                        )
                    },
                    {"status": "completed", "files_discovered": len(files)},
                    phase="completed"
                )
            
            state['messages'].append(f"Discovered {len(files)} files in {language}")
            self.log_action(f"Traversal complete: {len(files)} files, {len(modules)} modules")
            
        except Exception as e:
            logger.error(f"Error during traversal: {e}")
            state['errors'].append({
                "agent": "traverser",
                "error": str(e)
            })
        
        return state
    
    async def _discover_files(self, root_path: str) -> List[str]:
        files = []
        root = Path(root_path)
        
        for path in root.rglob('*'):
            if path.is_file() and self._should_include_file(path):
                files.append(str(path.relative_to(root)))
        
        return sorted(files)
    
    def _should_include_file(self, path: Path) -> bool:
        if path.suffix not in self.supported_extensions:
            return False
        
        for pattern in self.ignore_patterns:
            if any(fnmatch.fnmatch(part, pattern) for part in path.parts):
                return False
        
        return True
    
    def _detect_primary_language(self, files: List[str]) -> str:
        language_counts = {}
        
        for file in files:
            ext = Path(file).suffix
            if ext in self.supported_extensions:
                lang = self.supported_extensions[ext]
                language_counts[lang] = language_counts.get(lang, 0) + 1
        
        if not language_counts:
            return "unknown"
        
        return max(language_counts, key=language_counts.get)
    
    async def _identify_modules(self, files: List[str], root_path: str) -> Dict[str, List[str]]:
        modules = {}
        
        for file in files:
            parts = Path(file).parts
            if len(parts) > 1:
                module_name = parts[0]
            else:
                module_name = "root"
            
            if module_name not in modules:
                modules[module_name] = []
            modules[module_name].append(file)
        
        return modules
    
    def _find_entry_points(self, files: List[str], language: str) -> List[str]:
        entry_points = []
        entry_patterns = {
            'python': ['main.py', '__main__.py', 'app.py', 'run.py'],
            'javascript': ['index.js', 'main.js', 'app.js', 'server.js'],
            'typescript': ['index.ts', 'main.ts', 'app.ts', 'server.ts'],
            'java': ['Main.java', 'Application.java'],
            'go': ['main.go'],
            'rust': ['main.rs'],
            'cpp': ['main.cpp', 'main.cc'],
            'c': ['main.c']
        }
        
        patterns = entry_patterns.get(language, [])
        
        for file in files:
            filename = Path(file).name
            if filename in patterns or 'main' in filename.lower():
                entry_points.append(file)
        
        return entry_points
    
    async def _analyze_folder_structure(
        self, 
        root_path: str, 
        files: List[str], 
        project_spec
    ) -> FolderSpecification:
        """Analyze folder structure with semantic understanding."""
        root = Path(root_path)
        
        # Build directory tree
        folders = set()
        for file_path in files:
            path = Path(file_path)
            while path.parent != Path('.'):
                folders.add(str(path.parent))
                path = path.parent
        
        # Get folder information
        folder_info = self._get_folder_info(root, folders, files)
        
        try:
            # Use LLM to analyze folder purposes
            prompt = self.get_folder_analysis_prompt()
            chain = prompt | self.llm
            
            response = await chain.ainvoke({
                "project_type": project_spec.project_type.value if project_spec else "unknown",
                "architecture": project_spec.architecture.value if project_spec else "unknown", 
                "language": project_spec.primary_language if project_spec else "unknown",
                "folder_structure": self._format_folder_tree(root, folders),
                "file_distribution": json.dumps(folder_info, indent=2)[:2000]
            })
            
            # Parse response
            content = response.content.strip()
            if content.startswith('```json'):
                content = content[7:]
            if content.startswith('```'):
                content = content[3:]
            if content.endswith('```'):
                content = content[:-3]
            
            analysis = json.loads(content.strip())
            
            # Create folder specifications
            return self._create_folder_specs(analysis.get('folders', []), root, files)
            
        except Exception as e:
            logger.error(f"Error analyzing folder structure: {e}")
            # Fallback to simple directory-based structure
            return self._create_simple_folder_spec(root, folders, files)
    
    def _get_folder_info(self, root: Path, folders: Set[str], files: List[str]) -> Dict[str, Any]:
        """Get information about each folder."""
        folder_info = {}
        
        for folder in folders:
            folder_files = [f for f in files if f.startswith(folder + '/')]
            file_types = {}
            
            for file_path in folder_files:
                ext = Path(file_path).suffix
                file_types[ext] = file_types.get(ext, 0) + 1
            
            folder_info[folder] = {
                "file_count": len(folder_files),
                "file_types": file_types,
                "sample_files": folder_files[:5]  # First 5 files as examples
            }
        
        return folder_info
    
    def _format_folder_tree(self, root: Path, folders: Set[str]) -> str:
        """Format folder structure as a tree."""
        lines = []
        sorted_folders = sorted(folders)
        
        for i, folder in enumerate(sorted_folders[:20]):  # Limit to 20 folders
            depth = len(Path(folder).parts) - 1
            indent = "  " * depth
            folder_name = Path(folder).name
            lines.append(f"{indent}├── {folder_name}/")
        
        return "\n".join(lines)
    
    def _create_folder_specs(
        self, 
        folder_analysis: List[Dict], 
        root: Path, 
        files: List[str]
    ) -> FolderSpecification:
        """Create folder specifications from LLM analysis."""
        # Create a mapping of paths to purposes
        folder_purposes = {}
        for folder_data in folder_analysis:
            path = folder_data.get('path', '')
            try:
                purpose = FolderPurpose(folder_data.get('purpose', 'unknown'))
            except ValueError:
                purpose = FolderPurpose.UNKNOWN
            folder_purposes[path] = {
                'purpose': purpose,
                'description': folder_data.get('description', ''),
                'confidence': folder_data.get('confidence', 0.5)
            }
        
        # Build hierarchical structure
        return self._build_folder_hierarchy(".", folder_purposes, files)
    
    def _build_folder_hierarchy(
        self, 
        current_path: str, 
        folder_purposes: Dict[str, Dict], 
        files: List[str]
    ) -> FolderSpecification:
        """Recursively build folder hierarchy."""
        # Get files in current directory
        current_files = [
            f for f in files 
            if Path(f).parent == Path(current_path) or (current_path == "." and '/' not in f)
        ]
        
        # Get subfolders
        subfolders = set()
        for file_path in files:
            if file_path.startswith(current_path + '/') or current_path == ".":
                relative_path = file_path[len(current_path):].lstrip('/')
                if '/' in relative_path:
                    first_dir = relative_path.split('/')[0]
                    if current_path == ".":
                        subfolders.add(first_dir)
                    else:
                        subfolders.add(f"{current_path}/{first_dir}")
        
        # Get folder info
        folder_info = folder_purposes.get(current_path, {})
        purpose = folder_info.get('purpose', FolderPurpose.UNKNOWN)
        description = folder_info.get('description', f"Directory: {Path(current_path).name}")
        
        # Create subfolder specs
        subfolder_specs = []
        for subfolder_path in sorted(subfolders):
            subfolder_spec = self._build_folder_hierarchy(subfolder_path, folder_purposes, files)
            subfolder_specs.append(subfolder_spec)
        
        return FolderSpecification(
            path=current_path,
            name=Path(current_path).name or "root",
            purpose=purpose,
            description=description,
            files=[],  # Will be populated later with FileSpecification objects
            subfolders=subfolder_specs,
            file_count=len(current_files),
            total_lines=0  # Will be calculated later
        )
    
    def _create_simple_folder_spec(
        self, 
        root: Path, 
        folders: Set[str], 
        files: List[str]
    ) -> FolderSpecification:
        """Fallback method to create simple folder structure."""
        return FolderSpecification(
            path=".",
            name=root.name,
            purpose=FolderPurpose.UNKNOWN,
            description="Project root directory",
            files=[],
            subfolders=[],
            file_count=len(files),
            total_lines=0
        )