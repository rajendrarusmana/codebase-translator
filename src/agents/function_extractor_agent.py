"""
FunctionExtractor Agent - Extracts functions and classes from logic files.
"""
import ast
import re
from typing import Dict, List, Any, Optional, Tuple
from pathlib import Path
from langchain_core.prompts import ChatPromptTemplate
from .base_agent import BaseAgent
from ..models.hierarchical_spec import (
    FileType, FunctionInfo, ClassInfo, FileSpecification
)
from ..persistence.agent_checkpoint import CheckpointManager
import logging

logger = logging.getLogger(__name__)


class FunctionExtractorAgent(BaseAgent):
    """Extracts functions and classes from code files for granular analysis."""
    
    def __init__(self, checkpoint_manager: Optional[CheckpointManager] = None, **kwargs):
        super().__init__(**kwargs)
        self.checkpoint_manager = checkpoint_manager
    
    def get_prompt(self) -> ChatPromptTemplate:
        """Prompt for language-agnostic function extraction."""
        return ChatPromptTemplate.from_messages([
            ("system", """You are a code parser that extracts function and class definitions from code.
            
            Return ONLY valid JSON with this structure:
            {{
              "functions": [
                {{
                  "name": "function_name",
                  "parent_class": null,
                  "signature": "full function signature",
                  "docstring": "docstring if present",
                  "start_line": 1,
                  "end_line": 10,
                  "is_async": false,
                  "is_generator": false,
                  "decorators": ["@decorator1"]
                }}
              ],
              "classes": [
                {{
                  "name": "ClassName",
                  "parent_classes": ["ParentClass"],
                  "docstring": "class docstring",
                  "start_line": 15,
                  "end_line": 50,
                  "is_abstract": false,
                  "decorators": ["@decorator"],
                  "methods": [
                    {{
                      "name": "method_name",
                      "signature": "method signature",
                      "start_line": 20,
                      "end_line": 25
                    }}
                  ],
                  "properties": ["prop1", "prop2"]
                }}
              ]
            }}
            
            Extract ALL functions and classes, including nested ones.
            For languages without classes, use functions only.
            Provide accurate line numbers for each definition."""),
            
            ("human", """Extract functions and classes from this {language} code:
            
            File: {file_path}
            
            ```{language}
            {code}
            ```
            
            Return ONLY the JSON with extracted functions and classes.""")
        ])
    
    async def process(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Extract functions from all logic files."""
        file_specs = state.get('file_specs', [])
        root_path = Path(state.get('root_path', '.'))
        
        # Filter for logic files that need analysis
        logic_files = [
            spec for spec in file_specs
            if spec.file_type in [FileType.LOGIC, FileType.ENTRY] and spec.requires_analysis
        ]
        
        # Initialize or load checkpoint
        extracted_functions = {}
        processed_files = []
        
        if self.checkpoint_manager:
            checkpoint = self.checkpoint_manager.load_agent_state("function_extractor")
            if checkpoint:
                if checkpoint.agent_phase == "completed":
                    logger.info("Function extraction already completed")
                    state['extracted_functions'] = checkpoint.state.get('extracted_functions', {})
                    return state
                
                extracted_functions = checkpoint.state.get('extracted_functions', {})
                processed_files = checkpoint.state.get('processed_files', [])
                logger.info(f"Resuming function extraction, {len(processed_files)} files already processed")
        
        self.log_action(f"Extracting functions from {len(logic_files)} logic files")
        
        try:
            for i, file_spec in enumerate(logic_files):
                if file_spec.file_path in processed_files:
                    continue
                
                full_path = root_path / file_spec.file_path
                
                # Extract functions based on language
                if file_spec.language == 'python':
                    functions_data = await self._extract_python_functions(full_path)
                else:
                    # Use LLM for other languages
                    functions_data = await self._extract_functions_with_llm(
                        full_path, 
                        file_spec.file_path,
                        file_spec.language
                    )
                
                if functions_data:
                    extracted_functions[file_spec.file_path] = functions_data
                    processed_files.append(file_spec.file_path)
                    
                    # Update file spec with extracted info
                    file_spec.functions = functions_data.get('functions', [])
                    file_spec.classes = functions_data.get('classes', [])
                
                # Checkpoint every 10 files
                if (i + 1) % 10 == 0 and self.checkpoint_manager:
                    self.checkpoint_manager.save_agent_state(
                        "function_extractor",
                        {
                            "extracted_functions": extracted_functions,
                            "processed_files": processed_files
                        },
                        {
                            "processed": len(processed_files),
                            "total": len(logic_files)
                        },
                        phase="processing"
                    )
                    
                self.log_action(f"Extracted functions from {file_spec.file_path}: "
                              f"{len(functions_data.get('functions', []))} functions, "
                              f"{len(functions_data.get('classes', []))} classes")
            
            # Save to state
            state['extracted_functions'] = extracted_functions or {}
            state['function_extraction_stats'] = self._generate_extraction_stats(extracted_functions)
            
            # Mark as completed
            if self.checkpoint_manager:
                self.checkpoint_manager.save_agent_state(
                    "function_extractor",
                    {
                        "extracted_functions": extracted_functions,
                        "processed_files": processed_files
                    },
                    {"status": "completed", "total_processed": len(processed_files)},
                    phase="completed"
                )
            
        except Exception as e:
            logger.error(f"Error during function extraction: {e}")
            state['errors'].append({
                "agent": "function_extractor",
                "error": str(e)
            })
        
        return state
    
    async def _extract_python_functions(self, file_path: Path) -> Dict[str, Any]:
        """Extract functions from Python files using AST."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            tree = ast.parse(content)
            
            functions = []
            classes = []
            
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef) or isinstance(node, ast.AsyncFunctionDef):
                    # Check if it's a method (has a parent class)
                    parent_class = self._find_parent_class(tree, node)
                    
                    if not parent_class:  # Only add standalone functions
                        functions.append(FunctionInfo(
                            name=node.name,
                            parent_class=None,
                            signature=self._get_function_signature(node),
                            docstring=ast.get_docstring(node),
                            start_line=node.lineno,
                            end_line=node.end_lineno or node.lineno,
                            is_async=isinstance(node, ast.AsyncFunctionDef),
                            is_generator=self._is_generator(node),
                            decorators=[self._decorator_to_string(d) for d in node.decorator_list]
                        ))
                
                elif isinstance(node, ast.ClassDef):
                    methods = []
                    properties = []
                    
                    for item in node.body:
                        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                            methods.append(FunctionInfo(
                                name=item.name,
                                parent_class=node.name,
                                signature=self._get_function_signature(item),
                                docstring=ast.get_docstring(item),
                                start_line=item.lineno,
                                end_line=item.end_lineno or item.lineno,
                                is_async=isinstance(item, ast.AsyncFunctionDef),
                                is_generator=self._is_generator(item),
                                decorators=[self._decorator_to_string(d) for d in item.decorator_list]
                            ))
                        elif isinstance(item, ast.Assign):
                            for target in item.targets:
                                if isinstance(target, ast.Name):
                                    properties.append(target.id)
                    
                    classes.append(ClassInfo(
                        name=node.name,
                        parent_classes=[self._get_base_name(base) for base in node.bases],
                        docstring=ast.get_docstring(node),
                        methods=methods,
                        properties=properties,
                        start_line=node.lineno,
                        end_line=node.end_lineno or node.lineno,
                        is_abstract='ABC' in [self._get_base_name(base) for base in node.bases],
                        decorators=[self._decorator_to_string(d) for d in node.decorator_list]
                    ))
            
            return {
                "functions": [f.dict() for f in functions],
                "classes": [c.dict() for c in classes]
            }
            
        except Exception as e:
            logger.error(f"Error parsing Python file {file_path}: {e}")
            return {"functions": [], "classes": []}
    
    def _find_parent_class(self, tree: ast.AST, func_node: ast.AST) -> Optional[str]:
        """Find if a function is inside a class."""
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                for item in node.body:
                    if item is func_node:
                        return node.name
        return None
    
    def _get_function_signature(self, node: ast.FunctionDef) -> str:
        """Extract function signature."""
        args = []
        for arg in node.args.args:
            args.append(arg.arg)
        
        return f"{node.name}({', '.join(args)})"
    
    def _is_generator(self, node: ast.FunctionDef) -> bool:
        """Check if function is a generator."""
        for child in ast.walk(node):
            if isinstance(child, (ast.Yield, ast.YieldFrom)):
                return True
        return False
    
    def _decorator_to_string(self, decorator: ast.AST) -> str:
        """Convert decorator AST to string."""
        if isinstance(decorator, ast.Name):
            return f"@{decorator.id}"
        elif isinstance(decorator, ast.Call):
            if isinstance(decorator.func, ast.Name):
                return f"@{decorator.func.id}"
        return "@unknown"
    
    def _get_base_name(self, base: ast.AST) -> str:
        """Get base class name from AST."""
        if isinstance(base, ast.Name):
            return base.id
        elif isinstance(base, ast.Attribute):
            return base.attr
        return "unknown"
    
    async def _extract_functions_with_llm(
        self, 
        file_path: Path, 
        relative_path: str,
        language: str
    ) -> Dict[str, Any]:
        """Use LLM to extract functions for non-Python languages."""
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                # Read file with line numbers for accurate extraction
                lines = f.readlines()
                
                # Add line numbers to help LLM identify positions
                numbered_code = ""
                for i, line in enumerate(lines[:500], 1):  # Limit to first 500 lines
                    numbered_code += f"{i:4d}: {line}"
            
            prompt = self.get_prompt()
            chain = prompt | self.llm
            
            response = await chain.ainvoke({
                "file_path": relative_path,
                "language": language,
                "code": numbered_code
            })
            
            # Parse response
            content = response.content.strip()
            if content.startswith('```json'):
                content = content[7:]
            if content.startswith('```'):
                content = content[3:]
            if content.endswith('```'):
                content = content[:-3]
            
            import json
            result = json.loads(content.strip())
            
            # Convert to our models
            functions = []
            for func_data in result.get('functions', []):
                functions.append(FunctionInfo(**func_data))
            
            classes = []
            for class_data in result.get('classes', []):
                # Process methods
                methods = []
                for method_data in class_data.get('methods', []):
                    methods.append(FunctionInfo(
                        name=method_data['name'],
                        parent_class=class_data['name'],
                        signature=method_data.get('signature', method_data['name']),
                        docstring=method_data.get('docstring'),
                        start_line=method_data['start_line'],
                        end_line=method_data['end_line'],
                        is_async=method_data.get('is_async', False),
                        is_generator=method_data.get('is_generator', False),
                        decorators=method_data.get('decorators', [])
                    ))
                
                class_data['methods'] = methods
                classes.append(ClassInfo(**class_data))
            
            return {
                "functions": [f.dict() for f in functions],
                "classes": [c.dict() for c in classes]
            }
            
        except Exception as e:
            logger.error(f"Error extracting functions with LLM for {file_path}: {e}")
            return {"functions": [], "classes": []}
    
    def _generate_extraction_stats(self, extracted_functions: Dict[str, Any]) -> Dict[str, Any]:
        """Generate statistics about extracted functions."""
        total_functions = 0
        total_classes = 0
        total_methods = 0
        
        for file_data in extracted_functions.values():
            total_functions += len(file_data.get('functions', []))
            classes = file_data.get('classes', [])
            total_classes += len(classes)
            for class_data in classes:
                total_methods += len(class_data.get('methods', []))
        
        return {
            "files_processed": len(extracted_functions),
            "total_functions": total_functions,
            "total_classes": total_classes,
            "total_methods": total_methods,
            "total_code_units": total_functions + total_methods
        }