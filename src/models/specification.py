from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from enum import Enum

class DataType(BaseModel):
    name: str
    type: str
    description: str
    optional: bool = False
    default_value: Optional[Any] = None

class Operation(BaseModel):
    step: int
    operation: str
    description: str
    data_flow: Optional[str] = None
    control_flow: Optional[str] = None
    conditions: Optional[List[str]] = None
    side_effects: List[str] = Field(default_factory=list, description="IDs of side effects caused by this operation")

from enum import Enum
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

# Common side effect types as constants for reference
FILE_IO = "file_io"
NETWORK = "network"
DATABASE = "database"
SYSTEM = "system"
CONSOLE = "console"
MEMORY = "memory"
EXTERNAL_API = "external_api"
ENCRYPTION = "encryption"
AUTHENTICATION = "authentication"
LOGGING = "logging"
CACHE = "cache"

class SideEffect(BaseModel):
    id: str = Field(description="Unique identifier for this side effect")
    type: str = Field(description="Type of side effect (file_io, network, database, system, console, memory, external_api, encryption, authentication, logging, cache, etc.)")
    description: str
    scope: str
    resource: Optional[str] = None

class Dependency(BaseModel):
    module: str
    usage: str
    import_type: str = "standard"

class ModuleCall(BaseModel):
    """Represents a call from this module to another module"""
    target_module: str = Field(description="Module being called")
    target_function: str = Field(description="Function or method being called")
    call_context: str = Field(description="Context where the call is made (operation step, condition, etc)")
    call_type: str = Field(description="Type of call: direct_function, method, constructor, etc")
    parameters_passed: List[str] = Field(default_factory=list, description="Types of parameters passed to the call")
    return_used: bool = Field(default=False, description="Whether the return value is used")
    
class Algorithm(BaseModel):
    name: str
    complexity: str
    description: str
    implementation_notes: Optional[str] = None

class ModuleSpecification(BaseModel):
    module_name: str
    file_path: str
    original_language: str
    module_type: str = Field(default="module", description="module, class, function, etc.")
    description: str
    
    inputs: List[DataType] = Field(default_factory=list)
    outputs: List[DataType] = Field(default_factory=list)
    
    operations: List[Operation] = Field(default_factory=list)
    side_effects: List[SideEffect] = Field(default_factory=list)
    dependencies: List[Dependency] = Field(default_factory=list)
    module_calls: List[ModuleCall] = Field(default_factory=list, description="Calls made to functions/methods in other modules")
    algorithms: List[Algorithm] = Field(default_factory=list)
    
    data_structures: Dict[str, Any] = Field(default_factory=dict)
    constants: Dict[str, Any] = Field(default_factory=dict)
    
    metadata: Dict[str, Any] = Field(default_factory=dict)

class CodebaseSpecification(BaseModel):
    project_name: str
    root_path: str
    original_language: str
    modules: List[ModuleSpecification] = Field(default_factory=list)
    dependency_graph: Dict[str, List[str]] = Field(default_factory=dict)
    entry_points: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)