"""
FileClassifier Agent - Categorizes files by type and determines processing strategy.
"""
import re
from typing import Dict, List, Any, Optional
from pathlib import Path
from langchain_core.prompts import ChatPromptTemplate
from .base_agent import BaseAgent
from ..models.hierarchical_spec import FileType, FileSpecification
from ..persistence.agent_checkpoint import CheckpointManager
import logging

logger = logging.getLogger(__name__)


class FileClassifierAgent(BaseAgent):
    """Classifies files into categories to determine processing strategy."""
    
    def __init__(self, checkpoint_manager: Optional[CheckpointManager] = None, **kwargs):
        # Extract batch_size before passing to parent
        self.batch_size = kwargs.pop('batch_size', 50)
        super().__init__(**kwargs)
        self.checkpoint_manager = checkpoint_manager
        
        # File classification patterns
        self.patterns = {
            FileType.TEST: [
                r'test_.*\.py$', r'.*_test\.py$', r'.*\.test\.\w+$', r'.*\.spec\.\w+$',
                r'.*/tests?/.*', r'.*/spec/.*', r'.*_spec\.rb$'
            ],
            FileType.CONFIG: [
                r'.*\.json$', r'.*\.yaml$', r'.*\.yml$', r'.*\.toml$', r'.*\.ini$',
                r'.*\.conf$', r'.*\.cfg$', r'.*\.env.*$', r'.*rc$', r'.*config.*'
            ],
            FileType.SCHEMA: [
                r'.*\.proto$', r'.*\.graphql$', r'.*\.sql$', r'.*/migrations/.*',
                r'.*schema.*', r'.*\.avsc$', r'.*\.xsd$'
            ],
            FileType.ENTRY: [
                r'main\.\w+$', r'index\.\w+$', r'app\.\w+$', r'server\.\w+$',
                r'__main__\.py$', r'cli\.\w+$', r'run\.\w+$', r'start\.\w+$'
            ],
            FileType.TEMPLATE: [
                r'.*\.html$', r'.*\.htm$', r'.*\.ejs$', r'.*\.jade$', r'.*\.pug$',
                r'.*\.hbs$', r'.*\.handlebars$', r'.*\.mustache$', r'.*\.jinja.*'
            ],
            FileType.STATIC: [
                r'.*\.css$', r'.*\.scss$', r'.*\.sass$', r'.*\.less$',
                r'.*\.jpg$', r'.*\.jpeg$', r'.*\.png$', r'.*\.gif$', r'.*\.svg$',
                r'.*\.ico$', r'.*\.woff.*$', r'.*\.ttf$', r'.*\.eot$'
            ],
            FileType.DATA: [
                r'.*constants.*', r'.*enums.*', r'.*types\..*', r'.*\.d\.ts$',
                r'.*/fixtures/.*', r'.*/data/.*'
            ]
        }
        
        # Language-specific logic file extensions
        self.logic_extensions = {
            '.py', '.js', '.ts', '.java', '.go', '.rs', '.cpp', '.c', '.cs',
            '.rb', '.php', '.swift', '.kt', '.scala', '.clj', '.cljs', '.cljc',
            '.ex', '.exs', '.lua', '.r', '.m', '.mm', '.h', '.hpp'
        }
    
    async def process(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Classify all files in the project."""
        file_paths = state.get('file_paths', [])
        root_path = Path(state.get('root_path', '.'))
        
        # Initialize or load checkpoint
        classified_files = {}
        start_index = 0
        
        if self.checkpoint_manager:
            checkpoint = self.checkpoint_manager.load_agent_state("file_classifier")
            if checkpoint:
                if checkpoint.agent_phase == "completed":
                    logger.info("File classification already completed")
                    state['file_classifications'] = checkpoint.state.get('classifications', {})
                    state['file_specs'] = [FileSpecification(**spec) for spec in checkpoint.state.get('file_specs', [])]
                    return state
                
                classified_files = checkpoint.state.get('classifications', {})
                start_index = checkpoint.progress.get('last_index', 0)
                logger.info(f"Resuming file classification from index {start_index}")
        
        self.log_action(f"Classifying {len(file_paths)} files (starting from {start_index})")
        
        try:
            # Process files in batches
            for i in range(start_index, len(file_paths), self.batch_size):
                batch = file_paths[i:min(i + self.batch_size, len(file_paths))]
                batch_classifications = await self._classify_batch(batch, root_path)
                classified_files.update(batch_classifications)
                
                # Checkpoint after each batch
                if self.checkpoint_manager:
                    self.checkpoint_manager.save_agent_state(
                        "file_classifier",
                        {"classified_files": classified_files},
                        {
                            "last_index": i + len(batch),
                            "total": len(file_paths),
                            "classified": len(classified_files)
                        },
                        phase="processing"
                    )
                
                self.log_action(f"Classified batch {i // self.batch_size + 1}: {len(batch)} files")
            
            # Create file specifications
            file_specs = self._create_file_specifications(classified_files, root_path)
            
            # Save to state
            state['file_classifications'] = classified_files
            state['file_specs'] = file_specs
            
            # Mark as completed
            if self.checkpoint_manager:
                self.checkpoint_manager.save_agent_state(
                    "file_classifier",
                    {
                        "classifications": classified_files,
                        "file_specs": [spec.dict() for spec in file_specs]
                    },
                    {"status": "completed", "total_classified": len(classified_files)},
                    phase="completed"
                )
            
            # Generate statistics
            stats = self._generate_classification_stats(classified_files)
            state['classification_stats'] = stats
            
            self.log_action(f"Classification complete: {stats}")
            
        except Exception as e:
            logger.error(f"Error during file classification: {e}")
            state['errors'].append({
                "agent": "file_classifier",
                "error": str(e)
            })
        
        return state
    
    async def _classify_batch(self, file_paths: List[str], root_path: Path) -> Dict[str, FileType]:
        """Classify a batch of files."""
        classifications = {}
        
        for file_path in file_paths:
            file_type = await self._classify_file(file_path, root_path)
            classifications[file_path] = file_type
        
        return classifications
    
    async def _classify_file(self, file_path: str, root_path: Path) -> FileType:
        """Classify a single file based on patterns and content."""
        full_path = root_path / file_path
        
        # Check against patterns
        for file_type, patterns in self.patterns.items():
            for pattern in patterns:
                if re.search(pattern, file_path, re.IGNORECASE):
                    return file_type
        
        # Check if it's a logic file by extension
        if full_path.suffix in self.logic_extensions:
            # Additional checks for specific cases
            if await self._is_empty_or_trivial(full_path):
                return FileType.DATA
            
            return FileType.LOGIC
        
        # Check file content for classification hints
        file_type = await self._classify_by_content(full_path)
        if file_type != FileType.UNKNOWN:
            return file_type
        
        # Default classification based on extension
        if full_path.suffix in ['.md', '.rst', '.txt', '.doc', '.pdf']:
            return FileType.DATA  # Documentation as data
        
        return FileType.UNKNOWN
    
    async def _is_empty_or_trivial(self, file_path: Path) -> bool:
        """Check if a file is empty or contains only trivial content."""
        try:
            if not file_path.exists():
                return True
            
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read(1000)  # Read first 1000 chars
            
            # Remove comments and whitespace
            lines = [line.strip() for line in content.split('\n')]
            code_lines = [
                line for line in lines 
                if line and not line.startswith('#') and not line.startswith('//')
            ]
            
            # If less than 5 lines of actual code, consider it trivial
            return len(code_lines) < 5
            
        except Exception:
            return True
    
    async def _classify_by_content(self, file_path: Path) -> FileType:
        """Classify file by examining its content."""
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read(500)  # Read first 500 chars
            
            content_lower = content.lower()
            
            # Check for test indicators
            if any(indicator in content_lower for indicator in ['describe(', 'it(', 'test(', 'assert', '@test']):
                return FileType.TEST
            
            # Check for schema indicators
            if any(indicator in content_lower for indicator in ['create table', 'alter table', 'type query', 'type mutation']):
                return FileType.SCHEMA
            
            # Check for config indicators
            if content.strip().startswith('{') or content.strip().startswith('['):
                # Likely JSON config
                return FileType.CONFIG
            
            # Check for entry point indicators
            if any(indicator in content for indicator in ['if __name__', 'func main(', 'def main(', 'public static void main']):
                return FileType.ENTRY
            
        except Exception:
            pass
        
        return FileType.UNKNOWN
    
    def _create_file_specifications(self, classifications: Dict[str, FileType], root_path: Path) -> List[FileSpecification]:
        """Create file specifications from classifications."""
        file_specs = []
        
        for file_path, file_type in classifications.items():
            full_path = root_path / file_path
            
            # Determine if file requires analysis
            requires_analysis = file_type in [FileType.LOGIC, FileType.ENTRY]
            
            # Get basic file info
            try:
                line_count = sum(1 for _ in open(full_path, 'r', encoding='utf-8', errors='ignore'))
            except:
                line_count = 0
            
            spec = FileSpecification(
                file_path=file_path,
                file_type=file_type,
                language=self._detect_language(full_path),
                line_count=line_count,
                requires_analysis=requires_analysis,
                metadata={
                    "size_bytes": full_path.stat().st_size if full_path.exists() else 0
                }
            )
            
            file_specs.append(spec)
        
        return file_specs
    
    def _detect_language(self, file_path: Path) -> str:
        """Detect programming language from file extension."""
        ext_to_lang = {
            '.py': 'python',
            '.js': 'javascript',
            '.ts': 'typescript',
            '.java': 'java',
            '.go': 'go',
            '.rs': 'rust',
            '.cpp': 'cpp',
            '.c': 'c',
            '.cs': 'csharp',
            '.rb': 'ruby',
            '.php': 'php',
            '.swift': 'swift',
            '.kt': 'kotlin',
            '.scala': 'scala',
            '.clj': 'clojure',
            '.cljs': 'clojurescript',
            '.cljc': 'clojure',
            '.ex': 'elixir',
            '.exs': 'elixir',
            '.lua': 'lua',
            '.r': 'r',
            '.m': 'objectivec',
            '.h': 'c',
            '.hpp': 'cpp'
        }
        
        return ext_to_lang.get(file_path.suffix, 'unknown')
    
    def _generate_classification_stats(self, classifications: Dict[str, FileType]) -> Dict[str, Any]:
        """Generate statistics about file classifications."""
        stats = {
            "total_files": len(classifications),
            "by_type": {},
            "requires_analysis": 0
        }
        
        for file_type in FileType:
            count = sum(1 for t in classifications.values() if t == file_type)
            if count > 0:
                stats["by_type"][file_type.value] = count
        
        stats["requires_analysis"] = sum(
            1 for t in classifications.values() 
            if t in [FileType.LOGIC, FileType.ENTRY]
        )
        
        return stats
    
    def get_prompt(self) -> ChatPromptTemplate:
        """Get prompt template for file classification."""
        return ChatPromptTemplate.from_messages([
            ("system", "You are a file classification agent. Classify files by type and purpose."),
            ("human", "Classify this file: {file_path}")
        ])