from typing import Dict, List, Any, Optional
from pathlib import Path
from langchain_core.prompts import ChatPromptTemplate
from .base_agent import BaseAgent
from ..models.specification import ModuleSpecification, CodebaseSpecification
import json
import logging

logger = logging.getLogger(__name__)

class TranslatorAgent(BaseAgent):
    def __init__(self, checkpoint_manager=None, language_settings=None, **kwargs):
        # Remove language_settings from kwargs before passing to parent
        kwargs_copy = kwargs.copy()
        super().__init__(**kwargs_copy)
        self.checkpoint_manager = checkpoint_manager
        self.language_mappings = self._load_language_mappings()
        # Store language settings from config
        self.language_settings = language_settings or {}
        logger.info(f"Translator agent initialized with language settings: {list(self.language_settings.keys())}")
        
    def get_prompt(self) -> ChatPromptTemplate:
        return ChatPromptTemplate.from_messages([
            ("system", """You are an expert code translator that converts language-agnostic specifications into working code.
            
            Given a module specification, generate idiomatic code in the target language that:
            1. Implements all specified operations in the correct order
            2. Maintains the same inputs and outputs
            3. Preserves all side effects
            4. Uses appropriate language-specific constructs and patterns
            5. Follows the target language's best practices and conventions
            
            Important rules:
            - Map data types appropriately (e.g., Python list -> Java ArrayList)
            - Use language-specific idioms (e.g., Python list comprehension -> Java streams)
            - Handle imports/dependencies correctly for the target language
            - Maintain functional equivalence - the translated code must behave identically
            
            Return the complete, working code for the module."""),
            ("human", """Translate this specification to {target_language}:

            Specification:
            {specification}

            Target Framework Context:
            {framework_context}

            Language-specific requirements:
            {language_requirements}

            Generate the complete code:""")
        ])
    
    async def process(self, state: Dict[str, Any]) -> Dict[str, Any]:
        # Defensive check for None state
        if state is None:
            logger.error("State is None in translator process")
            return {}
        
        current_spec = state.get('current_module')
        target_language = state.get('target_language')

        # Initialize required state fields if missing
        if 'errors' not in state:
            state['errors'] = []
        if 'messages' not in state:
            state['messages'] = []

        if not current_spec:
            state['errors'].append({"type": "missing_spec", "message": "No specification to translate"})
            return state

        if not target_language:
            state['errors'].append({"type": "missing_target_language", "message": "No target language specified"})
            return state
        
        self.log_action(f"Translating {current_spec.module_name} to {target_language}")
        
        try:
            translated_code = await self._translate_module(current_spec, target_language, state)
            
            if not current_spec.file_path:
                raise ValueError(f"Invalid file path for {current_spec.module_name}")

            output_path = self._generate_output_path(
                current_spec.file_path,
                target_language,
                state.get('output_path', 'translated')
            )
            
            # Initialize translation_state if not present
            if 'translation_state' not in state or state['translation_state'] is None:
                state['translation_state'] = {'translated_modules': {}, 'errors': []}
            elif not isinstance(state['translation_state'], dict):
                state['translation_state'] = {'translated_modules': {}, 'errors': []}
            elif 'translated_modules' not in state['translation_state']:
                state['translation_state']['translated_modules'] = {}
                
            state['translation_state']['translated_modules'][current_spec.file_path] = {
                'code': translated_code,
                'output_path': output_path
            }
            
            state['messages'].append(f"Translated {current_spec.module_name} to {target_language}")
            
        except Exception as e:
            import traceback
            logger.error(f"Translation error for {current_spec.module_name}: {e}")
            logger.error(f"Full traceback: {traceback.format_exc()}")
            state['errors'].append({
                "type": "translation_error",
                "module": current_spec.module_name,
                "message": str(e)
            })
        
        return state
    
    async def _translate_module(
        self, 
        spec: ModuleSpecification, 
        target_language: str,
        state: Dict[str, Any]
    ) -> str:
        
        language_requirements = self._get_language_requirements(target_language)
        framework_context = self._get_framework_context(state)

        # Ensure spec is valid before serialization
        if not spec:
            raise ValueError(f"Invalid specification for {spec.module_name if spec else 'unknown module'}")

        try:
            spec_json = spec.model_dump_json(indent=2)
        except Exception as e:
            raise ValueError(f"Failed to serialize specification for {spec.module_name}: {e}")

        prompt = self.get_prompt()
        if not prompt:
            raise ValueError(f"Failed to get prompt for {spec.module_name}")

        chain = prompt | self.llm
        if not chain:
            raise ValueError(f"Failed to create LLM chain for {spec.module_name}")

        response = await chain.ainvoke({
            "target_language": target_language,
            "specification": spec_json,
            "framework_context": framework_context,
            "language_requirements": language_requirements
        })

        # Check if response is valid
        if not response or not hasattr(response, 'content'):
            raise ValueError(f"Invalid LLM response for {spec.module_name}")

        code = response.content

        # Check if response.content is None or empty
        if not code:
            raise ValueError(f"LLM returned empty response for {spec.module_name}")

        code = self._post_process_code(code, target_language, spec)
        
        imports = self._generate_imports(spec, target_language, state)
        if imports:
            code = imports + "\n\n" + code
        
        return code
    
    def _get_language_requirements(self, language: str) -> str:
        """Get language-specific requirements from config or defaults."""
        # Check if language settings are provided in config
        if language in self.language_settings:
            settings = self.language_settings[language]
            requirements = []
            
            # Generate requirements based on config settings
            if language == 'python':
                if settings.get('include_type_hints', False):
                    requirements.append("- Use type hints for all functions")
                if settings.get('format_with_black', False):
                    requirements.append("- Format code with Black formatter")
                requirements.extend([
                    "- Follow PEP 8 style guide",
                    "- Use f-strings for string formatting",
                    "- Prefer list comprehensions where appropriate",
                    "- Use context managers for file operations"
                ])
                
            elif language == 'javascript':
                if settings.get('use_es6', False):
                    requirements.append("- Use modern ES6+ syntax")
                if settings.get('include_jsdoc', False):
                    requirements.append("- Include JSDoc comments for all functions")
                requirements.extend([
                    "- Use const/let instead of var",
                    "- Use arrow functions where appropriate",
                    "- Handle async operations with async/await",
                    "- Include proper error handling"
                ])
                
            elif language == 'typescript':
                if settings.get('strict_mode', False):
                    requirements.append("- Use strict typing throughout")
                if settings.get('include_interfaces', False):
                    requirements.append("- Define interfaces for all data structures")
                requirements.extend([
                    "- Follow TypeScript best practices",
                    "- Use enums for constant values",
                    "- Include JSDoc comments"
                ])
                
            elif language == 'java':
                if settings.get('package_structure', False):
                    requirements.append("- Use proper package structure")
                if settings.get('include_javadoc', False):
                    requirements.append("- Include Javadoc comments for all public methods")
                requirements.extend([
                    "- Follow Java naming conventions",
                    "- Use appropriate access modifiers",
                    "- Implement proper exception handling",
                    "- Use generics where applicable",
                    "- Follow SOLID principles"
                ])
                
            elif language == 'go':
                if settings.get('format_with_gofmt', False):
                    requirements.append("- Format code with gofmt")
                if settings.get('include_godoc', False):
                    requirements.append("- Include Godoc comments for all exported functions")
                requirements.extend([
                    "- Follow Go idioms and conventions",
                    "- Handle errors explicitly",
                    "- Use defer for cleanup",
                    "- Keep interfaces small",
                    "- Use goroutines for concurrency where specified"
                ])
                
            else:
                # For other languages, use default requirements
                requirements.extend([
                    "- Follow language best practices and conventions",
                    "- Use appropriate idioms for the target language",
                    "- Maintain functional equivalence with the source specification"
                ])
            
            return "\n".join(requirements)
        
        # Fallback to hardcoded defaults if no config settings
        requirements = {
            'python': """
            - Use type hints for all functions
            - Follow PEP 8 style guide
            - Use f-strings for string formatting
            - Prefer list comprehensions where appropriate
            - Use context managers for file operations
            """,
            'javascript': """
            - Use modern ES6+ syntax
            - Use const/let instead of var
            - Use arrow functions where appropriate
            - Handle async operations with async/await
            - Include proper error handling
            """,
            'typescript': """
            - Define interfaces for all data structures
            - Use strict typing throughout
            - Follow TypeScript best practices
            - Use enums for constant values
            - Include JSDoc comments
            """,
            'java': """
            - Follow Java naming conventions
            - Use appropriate access modifiers
            - Implement proper exception handling
            - Use generics where applicable
            - Follow SOLID principles
            """,
            'go': """
            - Follow Go idioms and conventions
            - Handle errors explicitly
            - Use defer for cleanup
            - Keep interfaces small
            - Use goroutines for concurrency where specified
            """,
            'rust': """
            - Follow Rust ownership rules
            - Use Result<T, E> for error handling
            - Implement traits where appropriate
            - Use match expressions
            - Follow Rust naming conventions
            """,
            'clojure': """
            - Use idiomatic Clojure syntax with proper parentheses
            - Use namespaces correctly with ns declarations
            - Follow Clojure naming conventions (kebab-case for functions/variables)
            - Use functional programming patterns
            - Use immutability by default
            - Use appropriate data structures (maps, vectors, lists, sets)
            - Include proper documentation strings for functions
            - Use defn for function definitions
            - Use let for local bindings
            """
        }
        return requirements.get(language, "Follow language best practices and conventions")

    def _get_framework_context(self, state: Dict[str, Any]) -> str:
        """Extract framework context from architecture translation."""
        arch_translation = state.get('architecture_translation', {})

        if not arch_translation:
            return "No specific framework context available."

        context_parts = []

        # Target framework info
        target_framework = arch_translation.get('target_framework', 'unknown')
        context_parts.append(f"Target Framework: {target_framework}")

        # Framework mappings for this translation
        mappings = arch_translation.get('architectural_mappings', {})
        if mappings:
            context_parts.append("Pattern Mappings:")
            for source_pattern, target_pattern in mappings.items():
                context_parts.append(f"  {source_pattern} → {target_pattern}")

        # Dependencies available
        dependencies = arch_translation.get('dependencies', [])
        if dependencies:
            context_parts.append("Available Dependencies:")
            for dep in dependencies[:5]:  # Limit to first 5
                dep_name = dep.get('name', 'unknown') if isinstance(dep, dict) else str(dep)
                purpose = dep.get('purpose', '') if isinstance(dep, dict) else ''
                if purpose:
                    context_parts.append(f"  {dep_name} - {purpose}")
                else:
                    context_parts.append(f"  {dep_name}")

        # Migration notes
        notes = arch_translation.get('migration_notes', [])
        if notes:
            context_parts.append("Migration Notes:")
            for note in notes[:3]:  # Limit to first 3 notes
                context_parts.append(f"  - {note}")

        # Instructions based on framework
        if target_framework:
            context_parts.append(f"\nIMPORTANT: Generate code that integrates with {target_framework} framework.")
            context_parts.append("Use framework-specific patterns, base classes, and conventions.")
            context_parts.append("Ensure the translated code works with the generated project scaffolding.")

        return "\n".join(context_parts)

    def _generate_imports(
        self, 
        spec: ModuleSpecification, 
        target_language: str,
        state: Dict[str, Any]
    ) -> str:
        imports = []
        
        # Ensure dependencies is not None
        dependencies = spec.dependencies or []
        
        if target_language == 'python':
            standard_imports = set()
            for dep in dependencies:
                if dep.import_type == 'standard':
                    standard_imports.add(f"import {dep.module}")
                elif dep.import_type == 'from_import':
                    parts = dep.module.rsplit('.', 1)
                    if len(parts) == 2:
                        imports.append(f"from {parts[0]} import {parts[1]}")
            
            imports = list(standard_imports) + imports
            
        elif target_language == 'javascript':
            # Use generic JS imports without language mapping
            for dep in dependencies:
                imports.append(f"const {{{dep.module}}} = require('{dep.module}');")
        
        elif target_language == 'typescript':
            # Use generic TS imports without language mapping
            for dep in dependencies:
                imports.append(f"import {{{dep.module}}} from '{dep.module}';")
        
        elif target_language == 'java':
            imports.append("import java.util.*;")
            imports.append("import java.io.*;")
            # Skip specific mappings for now
        
        elif target_language == 'go':
            imports.append("package main")
            # Add common Go imports
            go_imports = ['import (']
            go_imports.append('    "fmt"')
            go_imports.append('    "net/http"')
            go_imports.append(')')
            imports.extend(go_imports)
        
        elif target_language == 'clojure':
            # Add Clojure namespace declaration
            if spec and spec.file_path:
                module_name = Path(spec.file_path).stem.replace('_', '-')
            else:
                module_name = 'unknown-module'
            clojure_imports = [f'(ns {module_name})']
            imports.extend(clojure_imports)
        
        return '\n'.join(imports)
    
    def _map_module_name(self, module: str, source_lang: str, target_lang: str) -> Optional[str]:
        if not source_lang or source_lang not in self.language_mappings:
            return None
        
        source_mappings = self.language_mappings.get(source_lang)
        if not source_mappings or not target_lang or target_lang not in source_mappings:
            return None
        
        mappings = source_mappings[target_lang]
        return mappings.get(module) if mappings else None
    
    def _post_process_code(self, code: str, language: str, spec=None) -> str:
        if not code:
            return ""

        code = code.strip()

        if code.startswith('```'):
            lines = code.split('\n')
            if lines[0].startswith('```'):
                lines = lines[1:]
            if lines and lines[-1] == '```':
                lines = lines[:-1]
            code = '\n'.join(lines)

        if language == 'python':
            if not code.startswith('#!/usr/bin/env python'):
                code = '#!/usr/bin/env python3\n# -*- coding: utf-8 -*-\n\n' + code
        
        # Add Clojure-specific post-processing
        elif language == 'clojure':
            if not code.startswith('(ns '):
                # If no namespace declaration, add a default one
                if spec and spec.module_name:
                    module_name = spec.module_name.replace('_', '-')
                else:
                    module_name = 'unknown-module'
                code = f'(ns {module_name})\n\n{code}'

        return code
    
    def _generate_output_path(self, original_path: str, target_language: str, output_dir: str) -> str:
        if not original_path:
            raise ValueError("Original path cannot be None or empty")

        path = Path(original_path)
        
        extension_map = {
            'python': '.py',
            'javascript': '.js',
            'typescript': '.ts',
            'java': '.java',
            'go': '.go',
            'rust': '.rs',
            'cpp': '.cpp',
            'c': '.c',
            'clojure': '.clj'
        }
        
        new_ext = extension_map.get(target_language, '.txt')
        new_name = path.stem + new_ext
        
        output_path = Path(output_dir) / target_language / path.parent / new_name
        
        return str(output_path)
    
    def _load_language_mappings(self) -> Dict[str, Dict[str, Dict[str, str]]]:
        return {
            'python': {
                'javascript': {
                    'os': 'fs',
                    'sys': 'process',
                    'json': 'JSON',
                    'requests': 'axios',
                    'numpy': 'numeric',
                    'pandas': 'dataframe-js'
                },
                'java': {
                    'os': 'java.io.File',
                    'sys': 'java.lang.System',
                    'json': 'com.google.gson.Gson',
                    'requests': 'java.net.http.HttpClient'
                },
                'go': {
                    'os': 'os',
                    'sys': 'os',
                    'json': 'encoding/json',
                    'requests': 'net/http'
                }
            },
            'clojure': {
                'go': {
                    'ring.adapter.jetty': 'net/http',
                    'ring.util.response': 'net/http'
                },
                'javascript': {
                    'ring.adapter.jetty': 'express',
                    'ring.util.response': 'express'
                },
                'java': {
                    'ring.adapter.jetty': 'org.eclipse.jetty',
                    'ring.util.response': 'javax.servlet.http'
                }
            }
        }
    def _get_architectural_context(self, spec: ModuleSpecification, state: Dict[str, Any]) -> Dict[str, Any]:
        """Extract architectural context from module specification and workflow state."""
        context = {
            "architectural_context": None,
            "deployment_pattern": None,
            "scaling_characteristics": None,
            "failure_tolerance": None,
            "infrastructure_assumptions": [],
            "domain_context": None
        }
        
        # Extract from module specification if available
        if hasattr(spec, 'architectural_context') and spec.architectural_context:
            context["architectural_context"] = spec.architectural_context
            
        if hasattr(spec, 'deployment_pattern') and spec.deployment_pattern:
            context["deployment_pattern"] = spec.deployment_pattern
            
        if hasattr(spec, 'scaling_characteristics') and spec.scaling_characteristics:
            context["scaling_characteristics"] = spec.scaling_characteristics
            
        if hasattr(spec, 'failure_tolerance') and spec.failure_tolerance:
            context["failure_tolerance"] = spec.failure_tolerance
            
        if hasattr(spec, 'infrastructure_assumptions') and spec.infrastructure_assumptions:
            context["infrastructure_assumptions"] = spec.infrastructure_assumptions
            
        if hasattr(spec, 'domain_context') and spec.domain_context:
            context["domain_context"] = spec.domain_context
            
        # Extract from workflow state if available
        if state.get('project_spec'):
            project_spec = state['project_spec']
            if hasattr(project_spec, 'architectural_context') and project_spec.architectural_context:
                context["architectural_context"] = project_spec.architectural_context
                
        return context

    def _generate_context_guidance(self, architectural_context: Dict[str, Any], target_language: str) -> str:
        """Generate context-aware guidance for translation based on architectural patterns."""
        if not architectural_context or not any(architectural_context.values()):
            return "No specific architectural context detected."
        
        guidance_parts = ["ARCHITECTURAL CONTEXT GUIDANCE:"]
        
        # Background job guidance
        if architectural_context.get("architectural_context") == "background_job":
            guidance_parts.append("BACKGROUND JOB PATTERN DETECTED:")
            guidance_parts.append("- Use appropriate async/concurrent processing patterns")
            guidance_parts.append("- Implement proper queue system integration")
            guidance_parts.append("- Include retry mechanisms with exponential backoff")
            guidance_parts.append("- Add graceful shutdown handling")
            guidance_parts.append("- Include health monitoring and logging")
            
            if "redis" in architectural_context.get("infrastructure_assumptions", []):
                guidance_parts.append("- Redis queue system detected")
                if target_language == "go":
                    guidance_parts.append("- Recommended Go libraries: github.com/go-redis/redis/v8")
                    
        return "\n".join(guidance_parts)
