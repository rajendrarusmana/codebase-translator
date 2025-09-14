from typing import TypedDict, List, Dict, Any, Optional
from langgraph.graph import MessagesState
from .specification import ModuleSpecification, CodebaseSpecification

class CodebaseAnalysisState(TypedDict):
    root_path: str
    target_language: str
    file_paths: List[str]
    current_module: Optional[str]
    processed_modules: List[str]
    module_specs: List[ModuleSpecification]
    codebase_spec: Optional[CodebaseSpecification]
    dependencies: Dict[str, List[str]]
    errors: List[Dict[str, Any]]
    messages: List[str]
    
class TranslationState(TypedDict):
    source_spec: CodebaseSpecification
    target_language: str
    current_module: Optional[ModuleSpecification]
    translated_modules: Dict[str, str]
    translation_mapping: Dict[str, Dict[str, Any]]
    output_path: str
    errors: List[Dict[str, Any]]
    messages: List[str]

class OrchestratorState(MessagesState):
    root_path: str
    source_language: Optional[str]
    target_language: str
    analysis_state: Optional[CodebaseAnalysisState]
    translation_state: Optional[TranslationState]
    phase: str
    completed: bool
    human_feedback: Optional[str]
    config: Dict[str, Any]
    
    # Hierarchical analysis state
    file_paths: Optional[List[str]] = None  # Files discovered by traverser
    project_spec: Optional[Any] = None  # ProjectSpecification
    folder_structure: Optional[Any] = None  # FolderSpecification  
    file_classifications: Optional[Dict[str, str]] = None
    file_specs: Optional[List[Any]] = None  # List[FileSpecification]
    extracted_functions: Optional[Dict[str, Any]] = None
    function_specs: Optional[Dict[str, List[Any]]] = None  # Dict[str, List[FunctionSpec]]
    module_specifications: Optional[List[ModuleSpecification]] = None  # Aggregated module specs for translation
    current_module: Optional[ModuleSpecification] = None  # Current module being translated
    errors: List[Dict[str, Any]] = []