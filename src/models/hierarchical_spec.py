"""
Hierarchical specification models for multi-level codebase analysis.
"""
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from enum import Enum


class ProjectType(str, Enum):
    WEB_API = "web_api"
    CLI = "cli"
    BACKGROUND_WORKER = "background_worker"
    LIBRARY = "library"
    DESKTOP_APP = "desktop_app"
    MOBILE_APP = "mobile_app"
    MICROSERVICE = "microservice"
    MONOLITH = "monolith"
    UNKNOWN = "unknown"


class ArchitecturePattern(str, Enum):
    MVC = "mvc"
    LAYERED = "layered"
    DOMAIN_DRIVEN = "domain_driven"
    MICROSERVICES = "microservices"
    EVENT_DRIVEN = "event_driven"
    HEXAGONAL = "hexagonal"
    SERVERLESS = "serverless"
    MONOLITHIC = "monolithic"
    UNKNOWN = "unknown"


class FolderPurpose(str, Enum):
    CONTROLLERS = "controllers"
    HANDLERS = "handlers"
    SERVICES = "services"
    MODELS = "models"
    REPOSITORIES = "repositories"
    UTILS = "utils"
    CONFIG = "config"
    TESTS = "tests"
    DOCS = "docs"
    MIGRATIONS = "migrations"
    STATIC = "static"
    TEMPLATES = "templates"
    COMPONENTS = "components"
    VIEWS = "views"
    MIDDLEWARE = "middleware"
    ROUTES = "routes"
    SCHEMAS = "schemas"
    COMMANDS = "commands"
    EVENTS = "events"
    JOBS = "jobs"
    UNKNOWN = "unknown"


class FileType(str, Enum):
    LOGIC = "logic"  # Contains functions/classes
    DATA = "data"  # Constants, configs
    SCHEMA = "schema"  # Database/API schemas
    TEST = "test"  # Test files
    ENTRY = "entry"  # Entry points
    CONFIG = "config"  # Configuration files
    STATIC = "static"  # Static assets
    TEMPLATE = "template"  # Templates
    UNKNOWN = "unknown"


class FunctionInfo(BaseModel):
    """Basic function information extracted from code."""
    name: str
    parent_class: Optional[str] = None
    signature: str
    docstring: Optional[str] = None
    start_line: int
    end_line: int
    is_async: bool = False
    is_generator: bool = False
    decorators: List[str] = Field(default_factory=list)
    complexity_estimate: Optional[int] = None  # Cyclomatic complexity if available


class ClassInfo(BaseModel):
    """Basic class information extracted from code."""
    name: str
    parent_classes: List[str] = Field(default_factory=list)
    docstring: Optional[str] = None
    methods: List[FunctionInfo] = Field(default_factory=list)
    properties: List[str] = Field(default_factory=list)
    start_line: int
    end_line: int
    is_abstract: bool = False
    decorators: List[str] = Field(default_factory=list)


class FileSpecification(BaseModel):
    """Enhanced file specification with function-level detail."""
    file_path: str
    file_type: FileType
    language: str
    description: Optional[str] = None
    functions: List[FunctionInfo] = Field(default_factory=list)
    classes: List[ClassInfo] = Field(default_factory=list)
    imports: List[str] = Field(default_factory=list)
    exports: List[str] = Field(default_factory=list)
    global_variables: List[str] = Field(default_factory=list)
    line_count: int = 0
    complexity_score: Optional[int] = None
    requires_analysis: bool = True
    metadata: Dict[str, Any] = Field(default_factory=dict)


class FolderSpecification(BaseModel):
    """Folder-level specification with semantic understanding."""
    path: str
    name: str
    purpose: FolderPurpose
    description: str
    files: List[FileSpecification] = Field(default_factory=list)
    subfolders: List['FolderSpecification'] = Field(default_factory=list)
    primary_language: Optional[str] = None
    file_count: int = 0
    total_lines: int = 0
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    class Config:
        # Allow self-reference for nested folders
        arbitrary_types_allowed = True


class ProjectSpecification(BaseModel):
    """Top-level project specification."""
    project_name: str
    project_root: str
    project_type: ProjectType
    architecture: ArchitecturePattern
    description: str
    primary_language: str
    languages_used: List[str] = Field(default_factory=list)
    technology_stack: List[str] = Field(default_factory=list)
    entry_points: List[str] = Field(default_factory=list)
    folder_structure: FolderSpecification
    dependencies: Dict[str, str] = Field(default_factory=dict)  # package -> version
    
    # Key directories for different purposes
    handlers_path: Optional[str] = None
    services_path: Optional[str] = None
    models_path: Optional[str] = None
    utils_path: Optional[str] = None
    config_path: Optional[str] = None
    tests_path: Optional[str] = None
    
    # Statistics
    total_files: int = 0
    total_lines: int = 0
    total_functions: int = 0
    total_classes: int = 0
    
    # Analysis metadata
    analysis_timestamp: str
    analysis_version: str = "2.0"
    metadata: Dict[str, Any] = Field(default_factory=dict)


class FunctionSpecification(BaseModel):
    """Detailed specification for a single function."""
    function_name: str
    file_path: str
    parent_class: Optional[str] = None
    signature: str
    description: str
    
    # Semantic analysis (from DocumenterAgent)
    inputs: List[Dict[str, Any]] = Field(default_factory=list)
    outputs: List[Dict[str, Any]] = Field(default_factory=list)
    operations: List[Dict[str, Any]] = Field(default_factory=list)
    side_effects: List[Dict[str, Any]] = Field(default_factory=list)
    module_calls: List[Dict[str, Any]] = Field(default_factory=list)
    
    # Relationships
    calls_functions: List[str] = Field(default_factory=list)  # Functions this calls
    called_by: List[str] = Field(default_factory=list)  # Functions that call this
    
    # Complexity metrics
    cyclomatic_complexity: Optional[int] = None
    cognitive_complexity: Optional[int] = None
    lines_of_code: int = 0
    
    # Testing
    has_tests: bool = False
    test_files: List[str] = Field(default_factory=list)
    
    metadata: Dict[str, Any] = Field(default_factory=dict)


# Update the import in FolderSpecification to avoid circular import
FolderSpecification.model_rebuild()