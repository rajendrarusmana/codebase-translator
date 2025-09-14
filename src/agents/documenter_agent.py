import json
import asyncio
from typing import Dict, List, Any, Optional
from pathlib import Path
from langchain_core.prompts import ChatPromptTemplate
from .base_agent import BaseAgent
from ..models.specification import (
    ModuleSpecification, DataType, Operation, 
    SideEffect, Dependency, Algorithm, ModuleCall
)
import logging

logger = logging.getLogger(__name__)

class DocumenterAgent(BaseAgent):
    """Pure LLM-based semantic code analyzer that creates language-agnostic specifications."""
    
    def __init__(self, checkpoint_manager=None, analysis_mode="file", **kwargs):
        super().__init__(**kwargs)
        self.checkpoint_manager = checkpoint_manager
        self.analysis_mode = analysis_mode  # "file" or "function"
        
    def get_prompt(self) -> ChatPromptTemplate:
        return ChatPromptTemplate.from_messages([
            ("system", """You are a semantic code analyzer that creates language-agnostic behavioral specifications.

            CRITICAL: You must return a JSON object that exactly matches this schema:

            {{
              "module_name": "string",
              "description": "semantic purpose of the entire module",
              "inputs": [
                {{
                  "name": "parameter_name",
                  "type": "semantic_data_type", 
                  "description": "what this data represents semantically",
                  "optional": boolean
                }}
              ],
              "outputs": [
                {{
                  "name": "return_name",
                  "type": "semantic_result_type",
                  "description": "what this output represents"
                }}
              ],
              "operations": [
                {{
                  "step": 1,
                  "operation": "semantic_operation_name",
                  "description": "what this step accomplishes behaviorally",
                  "data_flow": "input|transform|aggregate|filter|output",
                  "control_flow": "linear|conditional|iteration|parallel",
                  "side_effects": ["side_effect_id1", "side_effect_id2"]
                }}
              ],
              "side_effects": [
                {{
                  "id": "side_effect_id1",
                  "type": "console|file_io|network|database|system",
                  "description": "semantic purpose of the side effect",
                  "scope": "local|external|system",
                  "resource": "what external resource is affected"
                }}
              ],
              "dependencies": [
                {{
                  "module": "module_name",
                  "usage": "semantic_purpose_of_dependency",
                  "import_type": "capability_category"
                }}
              ],
              "module_calls": [
                {{
                  "target_module": "module_being_called",
                  "target_function": "function_or_method_name",
                  "call_context": "operation_step_or_context_where_call_occurs",
                  "call_type": "direct_function|method|constructor|static_method",
                  "parameters_passed": ["param_type1", "param_type2"],
                  "return_used": true
                }}
              ],
              "algorithms": [
                {{
                  "name": "algorithm_pattern_name",
                  "complexity": "big_o_notation",
                  "description": "what the algorithm accomplishes"
                }}
              ]
            }}

            JSON FORMATTING RULES - CRITICAL:
            - ALWAYS use double quotes for strings, never single quotes
            - NEVER add trailing commas after the last item in arrays or objects
            - ESCAPE special characters in strings: \" for quotes, \\ for backslash, \n for newline
            - Keep descriptions concise to avoid truncation
            - Ensure all brackets and braces are properly closed
            - Test your JSON mentally before outputting

            SEMANTIC FOCUS RULES:

            1. OPERATIONS must be in EXACT chronological order of execution
            2. Describe WHAT is accomplished, not syntax:
               ❌ "for loop iterating over list"  
               ✅ "process_each_item_in_collection"
               
               ❌ "if statement checking condition"
               ✅ "validate_input_meets_business_rules"
               
               ❌ "variable assignment"  
               ✅ "store_calculated_result_for_next_operation"

            3. DATA TYPES must be semantic:
               ❌ "List[int]" → ✅ "collection_of_numeric_measurements"
               ❌ "Dict" → ✅ "user_configuration_settings" 
               ❌ "bool" → ✅ "validation_success_indicator"

            4. INPUTS/OUTPUTS must capture ALL data flowing in/out:
               - Function parameters → inputs
               - Return values → outputs  
               - Modified external state → side_effects

            5. STEP NUMBERS must reflect actual execution order

            6. OPERATION-SIDE EFFECT LINKING is CRITICAL:
               - Each operation MUST list IDs of side effects it causes
               - Side effects MUST have unique IDs
               - Use descriptive IDs like "db_user_lookup", "console_result_output"
               - Empty side_effects array [] if operation has no side effects

            7. MODULE CALLS - Identify inter-module function calls:
               - Look for calls to functions from other modules/libraries
               - Include both internal project calls and external library calls
               - Specify the target module, function name, and call context
               - Examples:
                 * (braid.core.user/get-user user-id) → target_module: "braid.core.user", target_function: "get-user"
                 * re-frame/dispatch → target_module: "re-frame", target_function: "dispatch"
                 * (.println System/out message) → target_module: "System", target_function: "println", call_type: "method"
               - Distinguish between direct functions, methods, constructors, static methods
               - Track what parameters are passed and if return value is used

            8. Focus on the MODULE as a whole - if it has multiple functions, describe the overall workflow"""),
            ("human", """Analyze this code and return ONLY the JSON specification:

            File: {file_path}
            Language: {language}
            Code:
            ```
            {code}
            ```

            IMPORTANT: Return ONLY valid, properly formatted JSON matching the exact schema above.
            - No text before or after the JSON
            - Ensure all quotes are double quotes
            - No trailing commas
            - All strings must be properly escaped
            Focus on semantic behavior of the entire module.""")
        ])
    
    def get_function_prompt(self) -> ChatPromptTemplate:
        """Context-aware prompt for function-level analysis with pattern recognition."""
        return ChatPromptTemplate.from_messages([
            ("system", """You are analyzing a single function/method. Create a comprehensive semantic specification with context classification.

            CRITICAL: You must identify the function's CONTEXT by analyzing its pattern, not just its file path.

            Return ONLY valid JSON:
            {{
              "function_name": "name",
              "description": "what this function does semantically",
              "function_context": "handler|repository|service|utility|component|test|background_job|middleware|config",
              "inputs": [
                {{
                  "name": "parameter_name",
                  "type": "semantic_type",
                  "description": "purpose",
                  "optional": false
                }}
              ],
              "outputs": [
                {{
                  "name": "return_name",
                  "type": "semantic_type", 
                  "description": "what is returned"
                }}
              ],
              "operations": [
                {{
                  "step": 1,
                  "operation": "semantic_operation",
                  "description": "what happens",
                  "data_flow": "input|transform|output",
                  "control_flow": "linear|conditional|iteration",
                  "side_effects": ["effect_id"]
                }}
              ],
              "side_effects": [
                {{
                  "id": "effect_id",
                  "type": "file_io|network|database|system|console|memory|external_api",
                  "description": "what side effect",
                  "scope": "local|external|system",
                  "resource": "affected_resource"
                }}
              ],
              "module_calls": [
                {{
                  "target_module": "module_name",
                  "target_function": "function_name", 
                  "call_context": "when/why called",
                  "call_type": "direct_function|method|constructor|static_method",
                  "parameters_passed": ["param_types"],
                  "return_used": true
                }}
              ],
              
              // CONTEXT-SPECIFIC FIELDS (include only if detected):
              
              // For HANDLER/CONTROLLER functions:
              "http_method": "GET|POST|PUT|DELETE|PATCH", // if HTTP handler
              "endpoint_path": "/api/users/{{id}}", // if HTTP endpoint
              "status_codes": [200, 400, 404], // possible HTTP status codes
              
              // For REPOSITORY/DATA ACCESS functions:
              "sql_operation": "SELECT|INSERT|UPDATE|DELETE|JOIN", // if database operation
              "primary_table": "table_name", // main table being operated on
              "sql_example": "SELECT * FROM users WHERE id = ?", // example SQL pattern
              "database_type": "postgresql|mysql|sqlite|mongodb",
              
              // For SERVICE/BUSINESS LOGIC functions:
              "business_domain": "user_management|payment|inventory|auth", // domain area
              "transaction_type": "read_only|write|transaction|batch", 
              "external_dependencies": ["payment_service", "email_service"], // external systems
              
              // For COMPONENT/UI functions:
              "component_type": "page|modal|form|button|hook|context",
              "ui_framework": "react|vue|angular|svelte",
              
              // For BACKGROUND_JOB functions:
              "job_queue": "celery|sidekiq|bull|agenda",
              "schedule_pattern": "cron|interval|once|immediate",
              
              // For TEST functions (ENHANCED):
              "test_type": "unit|integration|e2e|performance|security",
              "test_framework": "pytest|jest|junit|mocha|rspec|go_test", 
              "test_case_description": "validates user creation with valid email",
              "test_scenario": "happy_path|edge_case|error_condition|boundary_condition|negative_case",
              "function_under_test": "create_user", // actual function being tested
              "test_assertion_type": "equality|exception|behavior|state_change|side_effect|mock_verification",
              "expected_outcome": "user created successfully with generated ID",
              "test_setup_required": "mock database, create test user data",
              "mock_dependencies": ["database", "email_service", "payment_gateway"],
              
              // For UTILITY functions:
              "utility_category": "validation|formatting|conversion|calculation|encryption|parsing",
              "input_constraints": "non-empty string, valid email format",
              "output_guarantees": "always returns boolean, throws ValueError on invalid input"
            }}

            CONTEXT DETECTION PATTERNS:

            1. HANDLER: HTTP request handling, route decorators (@app.route, @get, @post), request/response objects, status codes
            2. REPOSITORY: Database queries, SQL operations, ORM calls, CRUD operations, database connections
            3. SERVICE: Business logic, domain operations, orchestrates multiple repositories, external API calls
            4. TEST: Test frameworks (test_, _test, it(), describe(), @Test), assertions, mocks, test data setup
            5. UTILITY: Pure functions, data transformations, validations, helpers, no side effects
            6. COMPONENT: UI components, JSX/templates, state management, props/events, render methods
            7. BACKGROUND_JOB: Async task processing, queues, schedulers, job decorators (@celery.task)
            8. MIDDLEWARE: Request/response processing, authentication, logging, cross-cutting concerns
            9. CONFIG: Configuration loading, environment variables, settings, constants

            ENHANCED TEST ANALYSIS:
            - Identify EXACTLY what behavior is being tested
            - Extract the specific assertion being made
            - Determine the test scenario type (happy path vs edge case)
            - Find which function/method is actually under test
            - List all mocked dependencies
            - Describe the expected outcome in business terms

            JSON RULES: Double quotes only, no trailing commas, escape special chars.
            ONLY include context-specific fields that actually apply to this function."""),
            
            ("human", """Analyze this {language} function with pattern recognition:
            
            Function: {function_name}
            File: {file_path}
            
            ```{language}
            {code}
            ```
            
            Focus on identifying the function's CONTEXT by analyzing its patterns, imports, decorators, and behavior.
            Return ONLY the JSON specification with relevant context-specific fields.""")
        ])
    
    async def process(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Process a single module to create its semantic specification."""
        file_path = state.get('current_module')
        if not file_path:
            state['errors'].append({"type": "missing_module", "message": "No module to document"})
            return state
        
        self.log_action(f"Creating semantic specification for: {file_path}")
        
        try:
            # Read the source code
            full_path = Path(state['root_path']) / file_path
            code = await self._read_file(full_path)
            language = self._detect_language(file_path)
            
            # Create semantic specification using pure LLM analysis
            spec = await self._create_semantic_specification(file_path, code, language)
            
            # Add to state
            state['module_specs'].append(spec)
            state['processed_modules'].append(file_path)
            state['messages'].append(f"Created semantic spec: {spec.module_name} ({len(spec.operations)} operations)")
            
        except Exception as e:
            logger.error(f"Error creating specification for {file_path}: {e}")
            state['errors'].append({
                "type": "semantic_analysis_error",
                "module": file_path,
                "message": str(e)
            })
        
        return state
    
    async def process_functions(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Process extracted functions for detailed analysis."""
        extracted_functions = state.get('extracted_functions', {})
        root_path = Path(state.get('root_path', '.'))
        
        if not extracted_functions:
            logger.warning("No extracted functions found for analysis")
            return state
        
        # Initialize or load checkpoint
        analyzed_functions = {}
        processed_files = []
        
        if self.checkpoint_manager:
            checkpoint = self.checkpoint_manager.load_agent_state("documenter")
            if checkpoint:
                if checkpoint.agent_phase == "completed":
                    logger.info("Function analysis already completed")
                    state['function_specs'] = checkpoint.state.get('function_specs', {})
                    return state
                
                analyzed_functions = checkpoint.state.get('analyzed_functions', {})
                processed_files = checkpoint.state.get('processed_files', [])
                logger.info(f"Resuming function analysis, {len(processed_files)} files processed")
        
        total_functions = sum(
            len(file_data.get('functions', [])) + 
            sum(len(cls.get('methods', [])) for cls in file_data.get('classes', []))
            for file_data in extracted_functions.values()
        )
        
        self.log_action(f"Analyzing {total_functions} functions across {len(extracted_functions)} files")
        
        try:
            for file_path, file_data in extracted_functions.items():
                if file_path in processed_files:
                    continue
                
                file_functions = []
                
                # Analyze standalone functions
                for func_info in file_data.get('functions', []):
                    spec = await self._analyze_function(
                        file_path, func_info, root_path
                    )
                    if spec:
                        file_functions.append(spec)
                
                # Analyze class methods
                for class_info in file_data.get('classes', []):
                    for method_info in class_info.get('methods', []):
                        spec = await self._analyze_function(
                            file_path, method_info, root_path, class_info['name']
                        )
                        if spec:
                            file_functions.append(spec)
                
                analyzed_functions[file_path] = file_functions
                processed_files.append(file_path)
                
                # Checkpoint every file
                if self.checkpoint_manager:
                    self.checkpoint_manager.save_agent_state(
                        "documenter",
                        {
                            "analyzed_functions": analyzed_functions,
                            "processed_files": processed_files
                        },
                        {
                            "processed_files": len(processed_files),
                            "total_files": len(extracted_functions),
                            "analyzed_functions": sum(len(funcs) for funcs in analyzed_functions.values())
                        },
                        phase="processing"
                    )
                
                self.log_action(f"Analyzed {len(file_functions)} functions in {file_path}")
            
            # Save to state
            state['function_specs'] = analyzed_functions
            
            # Mark as completed
            if self.checkpoint_manager:
                self.checkpoint_manager.save_agent_state(
                    "documenter",
                    {
                        "function_specs": analyzed_functions,
                        "processed_files": processed_files
                    },
                    {"status": "completed", "total_functions": total_functions},
                    phase="completed"
                )
            
        except Exception as e:
            logger.error(f"Error during function analysis: {e}")
            state['errors'].append({
                "agent": "documenter",
                "error": str(e)
            })
        
        return state
    
    async def process_functions_concurrent(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Process functions with concurrent file-level processing."""
        extracted_functions = state.get('extracted_functions')
        if not extracted_functions:
            logger.warning("No extracted functions found for analysis")
            # Initialize function_specs to empty dict to prevent NoneType errors
            state['function_specs'] = {}
            return state
        
        root_path = Path(state.get('root_path', '.'))
        
        # Get concurrency settings from config
        config = state.get('config', {})
        rate_config = config.get('rate_limiting', {})
        max_concurrent_files = min(2, rate_config.get('max_concurrent_requests', 2))
        max_concurrent_functions = min(3, rate_config.get('max_concurrent_requests', 2))
        batch_delay = rate_config.get('batch_delay_seconds', 2)
        
        # Check for checkpoint
        processed_files = set()
        if self.checkpoint_manager:
            checkpoint = self.checkpoint_manager.load_agent_state("documenter")
            if checkpoint and checkpoint.agent_phase == "completed":
                logger.info("Function analysis already completed")
                state['function_specs'] = checkpoint.state.get('function_specs', {})
                return state
            elif checkpoint:
                processed_files = set(checkpoint.state.get('processed_files', []))
        
        total_functions = sum(
            len(file_data.get('functions', [])) + 
            sum(len(cls.get('methods', [])) for cls in file_data.get('classes', []))
            for file_data in extracted_functions.values()
        )
        
        self.log_action(f"Analyzing {total_functions} functions across {len(extracted_functions)} files concurrently")
        
        try:
            # Create semaphore to limit concurrent files
            file_semaphore = asyncio.Semaphore(max_concurrent_files)
            
            async def process_single_file(file_path: str, file_data: Dict) -> tuple:
                """Process a single file's functions concurrently."""
                async with file_semaphore:
                    if file_path in processed_files:
                        return file_path, []
                    
                    logger.info(f"Processing functions in {file_path}")
                    function_semaphore = asyncio.Semaphore(max_concurrent_functions)
                    
                    async def analyze_with_semaphore(func_info, parent_class=None):
                        async with function_semaphore:
                            return await self._analyze_function(
                                file_path, func_info, root_path, parent_class
                            )
                    
                    # Collect all function tasks for this file
                    function_tasks = []
                    
                    # Process standalone functions
                    for func_info in file_data.get('functions', []):
                        function_tasks.append(analyze_with_semaphore(func_info))
                    
                    # Process class methods
                    for class_info in file_data.get('classes', []):
                        for method_info in class_info.get('methods', []):
                            function_tasks.append(
                                analyze_with_semaphore(method_info, class_info['name'])
                            )
                    
                    # Execute all functions for this file concurrently
                    if function_tasks:
                        results = await asyncio.gather(*function_tasks, return_exceptions=True)
                        # Filter successful results
                        file_functions = [
                            spec for spec in results 
                            if spec and not isinstance(spec, Exception)
                        ]
                        
                        # Log any exceptions
                        exceptions = [r for r in results if isinstance(r, Exception)]
                        if exceptions:
                            logger.warning(f"Function analysis errors in {file_path}: {len(exceptions)} failures")
                            for exc in exceptions[:3]:  # Log first 3 exceptions
                                logger.warning(f"  - {exc}")
                        
                        logger.info(f"Analyzed {len(file_functions)} functions in {file_path}")
                        return file_path, file_functions
                    else:
                        logger.info(f"No functions found in {file_path}")
                        return file_path, []
            
            # Create tasks for all files
            file_tasks = [
                process_single_file(file_path, file_data)
                for file_path, file_data in extracted_functions.items()
            ]
            
            # Execute files in batches with delays to respect rate limits
            batch_size = max_concurrent_files
            results = []
            
            for i in range(0, len(file_tasks), batch_size):
                batch = file_tasks[i:i + batch_size]
                logger.info(f"Processing batch {i//batch_size + 1} of {(len(file_tasks) + batch_size - 1)//batch_size}")
                
                batch_results = await asyncio.gather(*batch, return_exceptions=True)
                results.extend(batch_results)
                
                # Add delay between batches
                if i + batch_size < len(file_tasks):
                    logger.info(f"Waiting {batch_delay} seconds before next batch...")
                    await asyncio.sleep(batch_delay)
            
            # Combine results
            analyzed_functions = {}
            successful_results = [r for r in results if not isinstance(r, Exception)]
            
            for file_path, file_functions in successful_results:
                analyzed_functions[file_path] = file_functions
            
            # Log any file-level exceptions
            exceptions = [r for r in results if isinstance(r, Exception)]
            if exceptions:
                logger.error(f"File processing errors: {len(exceptions)} files failed")
                for exc in exceptions[:3]:
                    logger.error(f"  - {exc}")
            
            # Update state
            state['function_specs'] = analyzed_functions
            
            # Final checkpoint
            if self.checkpoint_manager:
                self.checkpoint_manager.save_agent_state(
                    "documenter",
                    {
                        "function_specs": analyzed_functions,
                        "processed_files": list(analyzed_functions.keys())
                    },
                    {"status": "completed", "total_functions": total_functions},
                    phase="completed"
                )
            
            total_analyzed = sum(len(funcs) for funcs in analyzed_functions.values())
            self.log_action(f"Concurrent analysis complete: {total_analyzed}/{total_functions} functions analyzed")
            
        except Exception as e:
            logger.error(f"Error during concurrent function analysis: {e}")
            state['errors'].append({
                "agent": "documenter",
                "error": str(e)
            })
        
        return state
    
    async def _analyze_function(
        self, 
        file_path: str, 
        func_info: Dict[str, Any], 
        root_path: Path,
        parent_class: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Analyze a single function."""
        try:
            full_path = root_path / file_path
            
            # Read the file and extract function code
            with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
            
            start_line = func_info.get('start_line', 1) - 1
            end_line = func_info.get('end_line', len(lines))
            
            # Extract function code with context
            context_start = max(0, start_line - 2)
            context_end = min(len(lines), end_line + 2)
            
            # Add line numbers
            numbered_code = ""
            for i, line in enumerate(lines[context_start:context_end], context_start + 1):
                numbered_code += f"{i:4d}: {line}"
            
            # Use function-specific prompt
            prompt = self.get_function_prompt()
            chain = prompt | self.llm
            
            # Use retry wrapper for rate limit handling
            response = await self._execute_with_retry(
                chain.ainvoke,
                {
                "function_name": func_info['name'],
                "file_path": file_path,
                "language": self._detect_language(file_path),
                "code": numbered_code
                }
            )
            
            # Parse response
            content = self._clean_json_response(response.content)
            function_spec = json.loads(content)
            
            # Add metadata
            function_spec['file_path'] = file_path
            function_spec['parent_class'] = parent_class
            function_spec['line_range'] = [start_line + 1, end_line]
            function_spec['signature'] = func_info.get('signature', func_info['name'])
            
            return function_spec
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM JSON for function {func_info['name']} in {file_path}: {e}")
            logger.debug(f"Raw response: {content[:500] if 'content' in locals() else 'No content available'}...")
            
            # Retry with explicit JSON-only request
            try:
                retry_prompt = ChatPromptTemplate.from_messages([
                    ("system", "You MUST return ONLY valid JSON. No explanations, no markdown, just JSON."),
                    ("human", self.get_function_prompt().messages[1].prompt.template)
                ])
                retry_chain = retry_prompt | self.llm
                
                retry_response = await retry_chain.ainvoke({
                    "function_name": func_info['name'],
                    "file_path": file_path,
                    "language": self._detect_language(file_path),
                    "code": numbered_code[:3000]  # Limit to avoid truncation
                })
                
                retry_content = self._clean_json_response(retry_response.content)
                retry_function_spec = json.loads(retry_content)
                
                # Add metadata to retry result
                retry_function_spec['file_path'] = file_path
                retry_function_spec['parent_class'] = parent_class
                retry_function_spec['line_range'] = [start_line + 1, end_line]
                retry_function_spec['signature'] = func_info.get('signature', func_info['name'])
                retry_function_spec['retry_reason'] = str(e)
                
                logger.info(f"Retry successful for function {func_info['name']} in {file_path}")
                return retry_function_spec
                
            except Exception as retry_error:
                logger.debug(f"Retry also failed for function {func_info['name']}: {retry_error}")
                logger.error(f"Error analyzing function {func_info['name']} in {file_path}: {e}")
                return None
        
        except Exception as e:
            logger.error(f"Error analyzing function {func_info['name']} in {file_path}: {e}")
            return None
    
    async def _read_file(self, path: Path) -> str:
        """Read source code file."""
        with open(path, 'r', encoding='utf-8') as f:
            return f.read()
    
    def _detect_language(self, file_path: str) -> str:
        """Detect programming language from file extension."""
        ext_mapping = {
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
        ext = Path(file_path).suffix
        return ext_mapping.get(ext, 'unknown')
    
    async def _create_semantic_specification(self, file_path: str, code: str, language: str) -> ModuleSpecification:
        """Create semantic specification using pure LLM analysis."""
        try:
            # Invoke LLM for semantic analysis
            prompt = self.get_prompt()
            chain = prompt | self.llm
            
            self.log_action(f"Analyzing semantic behavior of {Path(file_path).name}")
            
            # Use retry wrapper for rate limit handling
            response = await self._execute_with_retry(
                chain.ainvoke,
                {
                "file_path": file_path,
                "language": language,
                "code": code
                }
            )
            
            # Parse JSON response
            content = self._clean_json_response(response.content)
            semantic_data = json.loads(content)
            
            # Create specification from LLM analysis
            spec = ModuleSpecification(
                module_name=semantic_data.get('module_name', Path(file_path).stem),
                file_path=file_path,
                original_language=language,
                description=semantic_data.get('description', ''),
                inputs=[DataType(**inp) for inp in semantic_data.get('inputs', [])],
                outputs=[DataType(**out) for out in semantic_data.get('outputs', [])],
                operations=[Operation(**op) for op in semantic_data.get('operations', [])],
                side_effects=[SideEffect(**se) for se in semantic_data.get('side_effects', [])],
                dependencies=[Dependency(**dep) for dep in semantic_data.get('dependencies', [])],
                module_calls=[ModuleCall(**call) for call in semantic_data.get('module_calls', [])],
                algorithms=[Algorithm(**algo) for algo in semantic_data.get('algorithms', [])],
                data_structures=semantic_data.get('data_structures', {}),
                constants=semantic_data.get('constants', {}),
                metadata={
                    'analysis_method': 'pure_llm_semantic',
                    'llm_model': getattr(self.llm, 'model_name', 'unknown'),
                    'language': language,
                    'operations_count': len(semantic_data.get('operations', [])),
                    'complexity_detected': len(semantic_data.get('algorithms', []))
                }
            )
            
            self.log_action(f"Generated specification: {len(spec.operations)} operations, {len(spec.side_effects)} side effects")
            return spec
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM JSON for {file_path}: {e}")
            logger.debug(f"Raw response: {content[:500]}...")
            
            # Try one more time with explicit JSON-only request
            try:
                retry_prompt = ChatPromptTemplate.from_messages([
                    ("system", "You MUST return ONLY valid JSON. No explanations, no markdown, just JSON."),
                    ("human", self.get_prompt().messages[1].prompt.template)
                ])
                retry_chain = retry_prompt | self.llm
                retry_response = await retry_chain.ainvoke({
                    "file_path": file_path,
                    "language": language,
                    "code": code[:3000]  # Limit to avoid truncation
                })
                retry_content = self._clean_json_response(retry_response.content)
                retry_data = json.loads(retry_content)
                
                # Successfully parsed on retry
                logger.info(f"Retry successful for {file_path}")
                return ModuleSpecification(
                    module_name=retry_data.get('module_name', Path(file_path).stem),
                    file_path=file_path,
                    original_language=language,
                    description=retry_data.get('description', ''),
                    inputs=[DataType(**inp) for inp in retry_data.get('inputs', [])],
                    outputs=[DataType(**out) for out in retry_data.get('outputs', [])],
                    operations=[Operation(**op) for op in retry_data.get('operations', [])],
                    side_effects=[SideEffect(**se) for se in retry_data.get('side_effects', [])],
                    dependencies=[Dependency(**dep) for dep in retry_data.get('dependencies', [])],
                    module_calls=[ModuleCall(**call) for call in retry_data.get('module_calls', [])],
                    algorithms=[Algorithm(**algo) for algo in retry_data.get('algorithms', [])],
                    data_structures=retry_data.get('data_structures', {}),
                    constants=retry_data.get('constants', {}),
                    metadata={'analysis_method': 'retry', 'retry_reason': str(e)}
                )
                
            except Exception as retry_error:
                logger.debug(f"Retry also failed: {retry_error}")
            
            return self._create_fallback_specification(file_path, language, f"JSON parse error: {e}")
            
        except Exception as e:
            logger.error(f"Error in semantic analysis for {file_path}: {e}")
            return self._create_fallback_specification(file_path, language, f"Analysis error: {e}")
    
    def _clean_json_response(self, content: str) -> str:
        """Clean LLM response to extract pure JSON."""
        content = content.strip()
        
        # Remove markdown code blocks
        if content.startswith('```json'):
            content = content[7:]
        elif content.startswith('```'):
            content = content[3:]
        
        if content.endswith('```'):
            content = content[:-3]
        
        content = content.strip()
        
        # Try to fix common JSON issues
        # Fix trailing commas before closing braces/brackets
        import re
        content = re.sub(r',(\s*[}\]])', r'\1', content)
        
        # Ensure the JSON is complete (sometimes truncated)
        # Count braces and brackets
        open_braces = content.count('{')
        close_braces = content.count('}')
        open_brackets = content.count('[')
        close_brackets = content.count(']')
        
        # Add missing closing braces/brackets
        if open_braces > close_braces:
            content += '}' * (open_braces - close_braces)
        if open_brackets > close_brackets:
            content += ']' * (open_brackets - close_brackets)
            
        return content
    
    def _create_fallback_specification(self, file_path: str, language: str, error_msg: str) -> ModuleSpecification:
        """Create minimal specification when LLM analysis fails."""
        return ModuleSpecification(
            module_name=Path(file_path).stem,
            file_path=file_path,
            original_language=language,
            description=f"Module analysis failed: {error_msg}",
            operations=[
                Operation(
                    step=1,
                    operation="unknown_operation",
                    description="Could not determine semantic operations",
                    data_flow="unknown",
                    control_flow="unknown"
                )
            ],
            metadata={
                'analysis_method': 'fallback',
                'error': error_msg,
                'status': 'failed'
            }
        )