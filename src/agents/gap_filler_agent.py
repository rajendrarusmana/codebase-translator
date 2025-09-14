"""
GapFillerAgent - Identifies and implements missing functionality in translated code.
"""
import asyncio
from typing import Dict, List, Any, Optional, Set
from pathlib import Path
from langchain_core.prompts import ChatPromptTemplate
from .base_agent import BaseAgent
from ..models.specification import ModuleSpecification
import logging
import ast
import re

logger = logging.getLogger(__name__)

class GapFillerAgent(BaseAgent):
    """Analyzes translated code and fills in missing functionality."""

    def __init__(self, checkpoint_manager=None, **kwargs):
        super().__init__(**kwargs)
        self.checkpoint_manager = checkpoint_manager

    def get_prompt(self) -> ChatPromptTemplate:
        return ChatPromptTemplate.from_messages([
            ("system", """You are an expert code completion agent that identifies and implements missing functionality.

Your task is to analyze existing translated code and a specification, then generate the missing parts to complete the implementation.

Focus on:
1. Missing functions or methods
2. Missing classes or structures
3. Missing endpoints or routes
4. Missing imports or dependencies
5. Incomplete implementations

Return ONLY valid code that can be directly integrated."""),
            ("human", """Analyze this specification and existing code, then implement missing functionality:

SPECIFICATION:
{specification}

EXISTING CODE:
{existing_code}

MISSING COMPONENTS TO IMPLEMENT:
{missing_components}

Generate the missing code in {target_language} that integrates seamlessly with the existing code:""")
        ])

    async def process(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze translated code and fill in missing functionality."""
        translated_modules = state.get('translation_state', {}).get('translated_modules', {})
        module_specs = state.get('module_specifications', [])

        if not translated_modules:
            logger.warning("No translated modules found to analyze")
            return state

        self.log_action(f"Analyzing {len(translated_modules)} translated modules for gaps")

        gaps_found = []
        filled_gaps = []

        try:
            for module_path, translation_data in translated_modules.items():
                if not isinstance(translation_data, dict) or 'code' not in translation_data:
                    continue

                existing_code = translation_data['code']
                spec = self._find_matching_spec(module_path, module_specs)

                if not spec:
                    logger.warning(f"No specification found for {module_path}")
                    continue

                # Analyze gaps in this module
                module_gaps = await self._analyze_module_gaps(
                    existing_code, spec, state.get('target_language', 'python')
                )

                if module_gaps:
                    gaps_found.extend(module_gaps)

                    # Fill the gaps
                    filled_code = await self._fill_module_gaps(
                        existing_code, spec, module_gaps, state.get('target_language', 'python')
                    )

                    if filled_code and filled_code != existing_code:
                        # Update the translated code
                        translation_data['code'] = filled_code
                        filled_gaps.append({
                            'module': module_path,
                            'gaps_filled': len(module_gaps)
                        })

                        logger.info(f"Filled {len(module_gaps)} gaps in {module_path}")

            # Update state
            state['gaps_found'] = gaps_found
            state['filled_gaps'] = filled_gaps
            state['gap_analysis_stats'] = {
                'total_gaps_found': len(gaps_found),
                'modules_analyzed': len(translated_modules),
                'modules_with_gaps': len([g for g in filled_gaps if g['gaps_filled'] > 0])
            }

        except Exception as e:
            logger.error(f"Error in gap filling: {e}")
            state['errors'].append({
                "agent": "gap_filler",
                "error": str(e)
            })

        return state

    def _find_matching_spec(self, module_path: str, module_specs: List[ModuleSpecification]) -> Optional[ModuleSpecification]:
        """Find the specification that matches the module path."""
        for spec in module_specs:
            if spec.file_path == module_path:
                return spec
        return None

    async def _analyze_module_gaps(
        self,
        existing_code: str,
        spec: ModuleSpecification,
        target_language: str
    ) -> List[Dict[str, Any]]:
        """Analyze what functionality is missing from the translated code."""
        gaps = []

        try:
            # Parse existing code based on language
            if target_language == 'python':
                existing_functions = self._extract_python_functions(existing_code)
            elif target_language == 'go':
                existing_functions = self._extract_go_functions(existing_code)
            elif target_language == 'javascript':
                existing_functions = self._extract_js_functions(existing_code)
            else:
                existing_functions = set()

            # Check for missing functions
            spec_functions = set()
            for operation in spec.operations:
                if operation.operation and operation.operation != 'unknown':
                    spec_functions.add(operation.operation)

            missing_functions = spec_functions - existing_functions
            for func_name in missing_functions:
                gaps.append({
                    'type': 'function',
                    'name': func_name,
                    'description': f'Missing function: {func_name}'
                })

            # Check for missing imports
            if spec.dependencies:
                existing_imports = self._extract_imports(existing_code, target_language)
                spec_imports = {dep.module for dep in spec.dependencies}

                missing_imports = spec_imports - existing_imports
                for import_name in missing_imports:
                    gaps.append({
                        'type': 'import',
                        'name': import_name,
                        'description': f'Missing import: {import_name}'
                    })

            # Check for missing endpoints/routes (for web apps)
            if spec.module_type in ['web_api', 'web_app']:
                existing_endpoints = self._extract_endpoints(existing_code, target_language)
                spec_endpoints = self._extract_spec_endpoints(spec)

                missing_endpoints = spec_endpoints - existing_endpoints
                for endpoint in missing_endpoints:
                    gaps.append({
                        'type': 'endpoint',
                        'name': endpoint,
                        'description': f'Missing endpoint: {endpoint}'
                    })

        except Exception as e:
            logger.error(f"Error analyzing gaps: {e}")

        return gaps

    async def _fill_module_gaps(
        self,
        existing_code: str,
        spec: ModuleSpecification,
        gaps: List[Dict[str, Any]],
        target_language: str
    ) -> str:
        """Fill the identified gaps by generating missing code."""
        if not gaps:
            return existing_code

        try:
            # Prepare gap information for the LLM
            missing_components = []
            for gap in gaps:
                missing_components.append(f"- {gap['type']}: {gap['name']} - {gap['description']}")

            gap_summary = "\n".join(missing_components)

            prompt = self.get_prompt()
            chain = prompt | self.llm

            response = await chain.ainvoke({
                "specification": spec.model_dump_json(indent=2),
                "existing_code": existing_code,
                "missing_components": gap_summary,
                "target_language": target_language
            })

            new_code = str(response.content).strip()

            # Clean up the response
            if new_code.startswith('```'):
                lines = new_code.split('\n')
                if lines[0].startswith('```'):
                    lines = lines[1:]
                if lines and lines[-1] == '```':
                    lines = lines[:-1]
                new_code = '\n'.join(lines)

            # Integrate the new code with existing code
            integrated_code = self._integrate_code(existing_code, new_code, target_language)

            return integrated_code

        except Exception as e:
            logger.error(f"Error filling gaps: {e}")
            return existing_code

    def _extract_python_functions(self, code: str) -> Set[str]:
        """Extract function names from Python code."""
        functions = set()
        try:
            tree = ast.parse(code)
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    functions.add(node.name)
        except:
            pass
        return functions

    def _extract_go_functions(self, code: str) -> Set[str]:
        """Extract function names from Go code."""
        functions = set()
        # Simple regex-based extraction for Go functions
        func_pattern = r'func\s+(\w+)\s*\('
        matches = re.findall(func_pattern, code)
        functions.update(matches)
        return functions

    def _extract_js_functions(self, code: str) -> Set[str]:
        """Extract function names from JavaScript code."""
        functions = set()
        # Extract function declarations and arrow functions
        patterns = [
            r'function\s+(\w+)\s*\(',
            r'const\s+(\w+)\s*=\s*\(',
            r'(\w+)\s*:\s*function\s*\('
        ]
        for pattern in patterns:
            matches = re.findall(pattern, code)
            functions.update(matches)
        return functions

    def _extract_imports(self, code: str, language: str) -> Set[str]:
        """Extract import statements from code."""
        imports = set()
        if language == 'python':
            import_patterns = [
                r'import\s+(\w+)',
                r'from\s+(\w+)\s+import'
            ]
        elif language == 'go':
            import_patterns = [r'"([^"]+)"']
        elif language == 'javascript':
            import_patterns = [
                r'import\s+.*from\s+["\']([^"\']+)["\']',
                r'const\s+\w+\s*=\s*require\s*\(\s*["\']([^"\']+)["\']'
            ]
        else:
            return imports

        for pattern in import_patterns:
            matches = re.findall(pattern, code)
            imports.update(matches)

        return imports

    def _extract_endpoints(self, code: str, language: str) -> Set[str]:
        """Extract endpoint/route definitions from code."""
        endpoints = set()
        if language == 'python':
            # Flask/Django style routes
            patterns = [
                r'@app\.route\s*\(\s*["\']([^"\']+)["\']',
                r'path\s*\(\s*["\']([^"\']+)["\']'
            ]
        elif language == 'go':
            # Gorilla mux or standard HTTP routes
            patterns = [
                r'HandleFunc\s*\(\s*["\']([^"\']+)["\']',
                r'Handle\s*\(\s*["\']([^"\']+)["\']'
            ]
        elif language == 'javascript':
            # Express.js routes
            patterns = [
                r'app\.(get|post|put|delete)\s*\(\s*["\']([^"\']+)["\']'
            ]
        else:
            return endpoints

        for pattern in patterns:
            matches = re.findall(pattern, code)
            if matches:
                if isinstance(matches[0], tuple):
                    endpoints.update(match[1] for match in matches)
                else:
                    endpoints.update(matches)

        return endpoints

    def _extract_spec_endpoints(self, spec: ModuleSpecification) -> Set[str]:
        """Extract endpoint information from specification."""
        endpoints = set()
        for operation in spec.operations:
            if operation.description:
                # Look for HTTP method patterns in descriptions
                http_methods = ['GET', 'POST', 'PUT', 'DELETE', 'PATCH']
                for method in http_methods:
                    if method in operation.description.upper():
                        # Try to extract path from description
                        path_match = re.search(r'/?[^\s]+', operation.description)
                        if path_match:
                            endpoints.add(path_match.group(0))
        return endpoints

    def _integrate_code(self, existing_code: str, new_code: str, language: str) -> str:
        """Integrate new code with existing code."""
        if not new_code:
            return existing_code

        if isinstance(new_code, str) and new_code.strip() == existing_code.strip():
            return existing_code

        # Simple integration - append new code
        # In a more sophisticated implementation, this would do smart merging
        if language == 'python':
            # Try to find the last import and add after it
            lines = existing_code.split('\n')
            last_import_idx = -1
            for i, line in enumerate(lines):
                if line.strip().startswith(('import ', 'from ')):
                    last_import_idx = i

            if last_import_idx >= 0:
                lines.insert(last_import_idx + 1, '\n' + new_code)
                return '\n'.join(lines)

        # Default: append at the end
        return existing_code + '\n\n' + new_code