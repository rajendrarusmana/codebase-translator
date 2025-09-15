"""
Hierarchical workflow orchestrator for the enhanced codebase translation system.
"""
from typing import Dict, Any, List, Optional
from langgraph.graph import StateGraph, END
from pathlib import Path
import asyncio
import logging
import hashlib
from uuid import UUID

from ..models.graph_state import OrchestratorState
from ..agents.project_analyzer_agent import ProjectAnalyzerAgent
from ..agents.architecture_translator_agent import ArchitectureTranslatorAgent
from ..agents.traverser_agent import TraverserAgent
from ..agents.file_classifier_agent import FileClassifierAgent
from ..agents.function_extractor_agent import FunctionExtractorAgent
from ..agents.documenter_agent import DocumenterAgent
from ..agents.translator_agent import TranslatorAgent
from ..agents.gap_filler_agent import GapFillerAgent
from ..persistence.agent_checkpoint import CheckpointManager, WorkflowCheckpoint
from ..models.specification import ModuleSpecification
from ..utils.project_management import calculate_output_path

# PostgreSQL persistence is optional - only import if enabled
try:
    from ..persistence.repositories import documentation_repo
    from ..persistence.pg_connection import db_manager
    POSTGRES_AVAILABLE = True
except ImportError:
    POSTGRES_AVAILABLE = False
    documentation_repo = None
    db_manager = None

logger = logging.getLogger(__name__)


class HierarchicalCodebaseTranslatorWorkflow:
    """Enhanced workflow with hierarchical analysis and agent-specific checkpointing."""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.workflow_id = None
        self.checkpoint_manager = None
        
        # Initialize agents (will be done in run() with proper checkpoint manager)
        self.project_analyzer = None
        self.architecture_translator = None
        self.traverser = None
        self.file_classifier = None
        self.function_extractor = None
        self.documenter = None
        self.translator = None
        
        self.graph = None
    
    def _generate_workflow_id(self, root_path: str, target_language: str) -> str:
        """Generate unique workflow ID."""
        content = f"{root_path}:{target_language}"
        return hashlib.md5(content.encode()).hexdigest()[:12]
    
    def _initialize_agents(self):
        """Initialize all agents with the checkpoint manager."""
        base_config = {
            'model_name': self.config.get('documenter', {}).get('model_name', 'claude-3-5-sonnet-20241022'),
            'temperature': 0.0
        }
        
        self.project_analyzer = ProjectAnalyzerAgent(
            checkpoint_manager=self.checkpoint_manager,
            **self.config.get('project_analyzer', base_config)
        )

        self.architecture_translator = ArchitectureTranslatorAgent(
            checkpoint_manager=self.checkpoint_manager,
            **self.config.get('architecture_translator', base_config)
        )
        
        self.traverser = TraverserAgent(
            checkpoint_manager=self.checkpoint_manager,
            **self.config.get('traverser', base_config)
        )
        
        self.file_classifier = FileClassifierAgent(
            checkpoint_manager=self.checkpoint_manager,
            batch_size=self.config.get('file_classifier_batch_size', 50),
            **base_config
        )
        
        self.function_extractor = FunctionExtractorAgent(
            checkpoint_manager=self.checkpoint_manager,
            **self.config.get('function_extractor', base_config)
        )
        
        self.documenter = DocumenterAgent(
            checkpoint_manager=self.checkpoint_manager,
            analysis_mode="function",
            **self.config.get('documenter', base_config)
        )
        
        self.translator = TranslatorAgent(
            checkpoint_manager=self.checkpoint_manager,
            language_settings=self.config.get('language_settings', {}),
            **self.config.get('translator', base_config)
        )
    
    def _build_graph(self) -> StateGraph:
        """Build the workflow graph."""
        graph = StateGraph(OrchestratorState)
        
        # Add nodes for each phase
        graph.add_node("project_analysis", self._analyze_project)
        graph.add_node("architecture_translation", self._translate_architecture)
        graph.add_node("traverse_codebase", self._traverse_codebase)
        graph.add_node("classify_files", self._classify_files)
        graph.add_node("extract_functions", self._extract_functions)
        graph.add_node("analyze_functions", self._analyze_functions)
        graph.add_node("create_specifications", self._create_specifications)
        graph.add_node("translate_modules", self._translate_modules)

        # Define workflow edges
        graph.add_edge("project_analysis", "architecture_translation")
        graph.add_edge("architecture_translation", "traverse_codebase")
        graph.add_edge("traverse_codebase", "classify_files")
        graph.add_edge("classify_files", "extract_functions")
        graph.add_edge("extract_functions", "analyze_functions")
        graph.add_edge("analyze_functions", "create_specifications")
        
        # Direct translation after specifications
        graph.add_edge("create_specifications", "translate_modules")
        # Connect translate_modules directly to END (removing Phase 8)
        graph.add_edge("translate_modules", END)
        
        graph.set_entry_point("project_analysis")
        
        return graph.compile()
    
    async def run(
        self, 
        root_path: str, 
        target_language: str, 
        source_language: str = None,
        resume: bool = False,
        **kwargs
    ) -> Dict[str, Any]:
        """Run the hierarchical workflow."""
        self.workflow_id = self._generate_workflow_id(root_path, target_language)
        self.checkpoint_manager = CheckpointManager(self.workflow_id)
        
        # Initialize agents with checkpoint manager
        self._initialize_agents()
        self.graph = self._build_graph()
        
        try:
            # Create initial workflow state
            initial_state = self._create_initial_state(root_path, target_language, **kwargs)
            
            # Create or update translation project record in database
            postgres_config = self.config.get('postgres', {})
            if postgres_config.get('enabled', False) and POSTGRES_AVAILABLE:
                try:
                    from ..persistence.translation_project_repository import translation_project_repo
                    
                    # Calculate deterministic output path
                    output_root = kwargs.get('output_path', './translated')
                    project_output_path = str(calculate_output_path(root_path, target_language, output_root))
                    
                    # Create translation project record
                    project_id = await translation_project_repo.create_translation_project(
                        root_path, target_language, project_output_path
                    )
                    logger.info(f"Created translation project record with ID: {project_id}")
                    
                    # Update state with calculated output path
                    initial_state['target_output_path'] = project_output_path
                    
                    # Update translation project status to analyzing
                    await translation_project_repo.update_translation_project_status(
                        project_id, 'analyzing'
                    )
                    
                except Exception as e:
                    logger.warning(f"Failed to create translation project record: {e}")
                    # Fall back to default behavior
                    project_output_path = str(calculate_output_path(root_path, target_language, kwargs.get('output_path', './translated')))
                    initial_state['target_output_path'] = project_output_path
            else:
                # Calculate output path without database
                project_output_path = str(calculate_output_path(root_path, target_language, kwargs.get('output_path', './translated')))
                initial_state['target_output_path'] = project_output_path
            
            logger.info(f"Translation output will be saved to: {project_output_path}")
            
            # Create workflow checkpoint
            workflow_checkpoint = WorkflowCheckpoint(
                workflow_id=self.workflow_id,
                project_root=root_path,
                target_language=target_language,
                current_phase="starting"
            )
            
            # Save initial workflow checkpoint
            workflow_checkpoint.save(self.checkpoint_manager)
            
            # Execute the workflow
            final_state = await self.graph.ainvoke(initial_state)
            
            # Update translation project status to completed
            postgres_config = self.config.get('postgres', {})
            if postgres_config.get('enabled', False) and POSTGRES_AVAILABLE:
                try:
                    from ..persistence.translation_project_repository import translation_project_repo
                    from datetime import datetime
                    await translation_project_repo.update_translation_project_status(
                        project_id, 'completed', datetime.now()
                    )
                except Exception as e:
                    logger.warning(f"Failed to update translation project status: {e}")
            
            # Mark workflow as completed
            workflow_checkpoint.current_phase = "completed"
            workflow_checkpoint.completed_agents = [
                "project_analyzer", "architecture_translator", "traverser", "file_classifier",
                "function_extractor", "documenter", "translator"
            ]
            workflow_checkpoint.save(self.checkpoint_manager)
            
            # Cleanup on success if configured
            if self.config.get('cleanup_on_success', True):
                self.checkpoint_manager.cleanup_workflow()
                logger.info("Workflow completed successfully, checkpoints cleaned up")
            
            return {
                "success": True,
                "final_state": final_state,
                "workflow_id": self.workflow_id,
                "errors": self._collect_errors(final_state)
            }
            
        except Exception as e:
            logger.error(f"Workflow execution failed: {e}")
            
            # Update translation project status to failed
            postgres_config = self.config.get('postgres', {})
            if postgres_config.get('enabled', False) and POSTGRES_AVAILABLE:
                try:
                    from ..persistence.translation_project_repository import translation_project_repo
                    from datetime import datetime
                    # Try to get project record and update status
                    # Note: This might not work if project creation failed
                    pass
                except Exception as update_e:
                    logger.warning(f"Failed to update translation project failure status: {update_e}")
            
            return {
                "success": False,
                "error": str(e),
                "workflow_id": self.workflow_id,
                "final_state": initial_state
            }
    
    def _create_initial_state(
        self, 
        root_path: str, 
        target_language: str, 
        **kwargs
    ) -> OrchestratorState:
        """Create initial workflow state."""
        return OrchestratorState(
            messages=[],
            root_path=root_path,
            source_language=None,
            target_language=target_language,
            analysis_state=None,
            translation_state=None,
            phase="starting",
            completed=False,
            human_feedback=None,
            config=kwargs,
            # New hierarchical state
            project_spec=None,
            folder_structure=None,
            file_classifications=None,
            file_specs=None,
            extracted_functions=None,
            function_specs=None,
            module_specifications=None,
            current_module=None,
            errors=[]
        )
    
    async def _analyze_project(self, state: OrchestratorState) -> OrchestratorState:
        """Phase 1: Analyze project to determine type and architecture."""
        logger.info("Phase 1: Project Analysis")
        state['phase'] = 'project_analysis'
        
        try:
            state = await self.project_analyzer.process(state)
            logger.info(f"Project type: {state.get('project_type')}, Architecture: {state.get('architecture')}")
        except Exception as e:
            logger.error(f"Project analysis failed: {e}")
            state['errors'].append({"phase": "project_analysis", "error": str(e)})
        
        return state

    async def _translate_architecture(self, state: OrchestratorState) -> OrchestratorState:
        """Phase 2: Translate project architecture to target framework."""
        logger.info("Phase 2: Architecture Translation")
        state['phase'] = 'architecture_translation'

        try:
            state = await self.architecture_translator.process(state)
            arch_translation = state.get('architecture_translation', {})
            target_framework = arch_translation.get('target_framework', 'unknown')
            logger.info(f"Selected target framework: {target_framework}")

            # Write scaffolding files to output directory
            scaffolding_files = arch_translation.get('scaffolding_files', {})
            if scaffolding_files:
                output_path = Path(state.get('target_output_path', state.get('output_path', 'translated')))
                output_path.mkdir(parents=True, exist_ok=True)

                files_written = 0
                for file_path, content in scaffolding_files.items():
                    full_path = output_path / file_path
                    full_path.parent.mkdir(parents=True, exist_ok=True)
                    with open(full_path, 'w', encoding='utf-8') as f:
                        f.write(content)
                    files_written += 1

                logger.info(f"Generated {files_written} scaffolding files in {output_path}")

        except Exception as e:
            logger.error(f"Architecture translation failed: {e}")
            state['errors'].append({"phase": "architecture_translation", "error": str(e)})

        return state

    async def _traverse_codebase(self, state: OrchestratorState) -> OrchestratorState:
        """Phase 3: Traverse codebase and analyze folder structure."""
        logger.info("Phase 3: Codebase Traversal")
        state['phase'] = 'traversal'
        
        try:
            state = await self.traverser.process(state)
            logger.info(f"Discovered {len(state.get('file_paths', []))} files")
        except Exception as e:
            logger.error(f"Codebase traversal failed: {e}")
            state['errors'].append({"phase": "traversal", "error": str(e)})
        
        return state
    
    async def _classify_files(self, state: OrchestratorState) -> OrchestratorState:
        """Phase 4: Classify files by type."""
        logger.info("Phase 4: File Classification")
        state['phase'] = 'file_classification'
        
        try:
            state = await self.file_classifier.process(state)
            stats = state.get('classification_stats', {})
            logger.info(f"Classified files: {stats}")
        except Exception as e:
            logger.error(f"File classification failed: {e}")
            state['errors'].append({"phase": "file_classification", "error": str(e)})
        
        return state
    
    async def _extract_functions(self, state: OrchestratorState) -> OrchestratorState:
        """Phase 5: Extract functions from logic files."""
        logger.info("Phase 5: Function Extraction")
        state['phase'] = 'function_extraction'
        
        try:
            state = await self.function_extractor.process(state)
            stats = state.get('function_extraction_stats', {})
            logger.info(f"Extracted functions: {stats}")
        except Exception as e:
            logger.error(f"Function extraction failed: {e}")
            state['errors'].append({"phase": "function_extraction", "error": str(e)})
        
        return state
    
    async def _analyze_functions(self, state: OrchestratorState) -> OrchestratorState:
        """Phase 6: Analyze functions semantically."""
        logger.info("Phase 6: Function Analysis") 
        state['phase'] = 'function_analysis'
        
        try:
            # Use the new concurrent function-level analysis
            state = await self.documenter.process_functions_concurrent(state)
            function_specs = state.get('function_specs', {})
            total_functions = sum(len(specs) for specs in function_specs.values()) if function_specs else 0
            logger.info(f"Analyzed {total_functions} functions")
        except Exception as e:
            logger.error(f"Function analysis failed: {e}")
            state['errors'].append({"phase": "function_analysis", "error": str(e)})
        
        return state
    
    async def _create_specifications(self, state: OrchestratorState) -> OrchestratorState:
        """Phase 7: Create final codebase specification and save to database."""
        logger.info("Phase 7: Creating Specifications")
        state['phase'] = 'specification_creation'
        
        try:
            # Check if specifications already exist
            existing_specs = await self._check_existing_specifications(state)
            if existing_specs:
                logger.info(f"Using {len(existing_specs)} existing module specifications")
                state['module_specifications'] = existing_specs
                state['specifications_ready'] = True
                
                # Update project status to indicate reuse
                project_id = state.get('project_id')
                if project_id:
                    try:
                        from ..persistence.translation_project_repository import translation_project_repo
                        from datetime import datetime
                        await translation_project_repo.update_translation_project_status(
                            UUID(project_id), 'analyzing_reuse'
                        )
                    except Exception as e:
                        logger.warning(f"Failed to update translation project status: {e}")
                
                # Save specifications to database (should be no-op since they already exist)
                await self._save_specifications_to_database(state, existing_specs)
                return state
            
            from ..models.specification import ModuleSpecification, DataType, Operation, SideEffect, Dependency, Algorithm, ModuleCall
            
            function_specs = state.get('function_specs', {})
            if not function_specs:
                logger.warning("No function specifications found to convert to module specifications")
                state['specifications_ready'] = True
                # Save to database even if no function specs
                await self._save_specifications_to_database(state, [])
                return state
            
            module_specifications = []
            
            # Convert function specs to module specs by aggregating per file
            for file_path, file_functions in function_specs.items():
                if not file_functions:  # Skip files with no functions
                    continue
                
                # Aggregate data from all functions in the file
                all_inputs = []
                all_outputs = []
                all_operations = []
                all_side_effects = []
                all_dependencies = []
                all_module_calls = []
                all_algorithms = []
                descriptions = []
                
                # Extract language from first function or detect from file path
                original_language = 'unknown'
                if file_functions and isinstance(file_functions[0], dict):
                    # Try to get language from function metadata
                    first_func = file_functions[0]
                    if 'file_path' in first_func:
                        original_language = self._detect_language_from_path(first_func['file_path'])
                else:
                    original_language = self._detect_language_from_path(file_path)
                
                # Combine description from all functions
                for func_spec in file_functions:
                    if isinstance(func_spec, dict):
                        if func_spec.get('description'):
                            descriptions.append(f"{func_spec.get('function_name', 'unknown')}: {func_spec['description']}")
                        
                        # Aggregate inputs (avoid duplicates by name)
                        existing_input_names = {inp.name for inp in all_inputs}
                        for inp_data in func_spec.get('inputs') or []:
                            if isinstance(inp_data, dict) and inp_data.get('name') not in existing_input_names:
                                all_inputs.append(DataType(**inp_data))
                        
                        # Aggregate outputs (avoid duplicates by name)
                        existing_output_names = {out.name for out in all_outputs}
                        for out_data in func_spec.get('outputs') or []:
                            if isinstance(out_data, dict) and out_data.get('name') not in existing_output_names:
                                all_outputs.append(DataType(**out_data))
                        
                        # Aggregate operations with step number adjustment
                        step_offset = len(all_operations)
                        for op_data in func_spec.get('operations') or []:
                            if isinstance(op_data, dict):
                                # Adjust step numbers to maintain sequence across functions
                                op_data_copy = op_data.copy()
                                op_data_copy['step'] = op_data.get('step', 1) + step_offset
                                all_operations.append(Operation(**op_data_copy))
                        
                        # Aggregate side effects (ensure unique IDs)
                        existing_effect_ids = {se.id for se in all_side_effects}
                        for se_data in func_spec.get('side_effects') or []:
                            if isinstance(se_data, dict):
                                se_id = se_data.get('id', f"effect_{len(all_side_effects)}")
                                if se_id not in existing_effect_ids:
                                    se_data_copy = se_data.copy()
                                    se_data_copy['id'] = se_id
                                    all_side_effects.append(SideEffect(**se_data_copy))
                        
                        # Aggregate dependencies (avoid duplicates by module name)
                        existing_dep_modules = {dep.module for dep in all_dependencies}
                        for dep_data in func_spec.get('dependencies') or []:
                            if isinstance(dep_data, dict) and dep_data.get('module') not in existing_dep_modules:
                                all_dependencies.append(Dependency(**dep_data))
                        
                        # Aggregate module calls
                        for mc_data in func_spec.get('module_calls') or []:
                            if isinstance(mc_data, dict):
                                all_module_calls.append(ModuleCall(**mc_data))
                        
                        # Aggregate algorithms (avoid duplicates by name)
                        existing_algo_names = {algo.name for algo in all_algorithms}
                        for algo_data in func_spec.get('algorithms') or []:
                            if isinstance(algo_data, dict) and algo_data.get('name') not in existing_algo_names:
                                all_algorithms.append(Algorithm(**algo_data))
                
                # Create module specification
                module_name = Path(file_path).stem
                combined_description = f"Module containing {len(file_functions)} functions. " + "; ".join(descriptions[:3])
                if len(descriptions) > 3:
                    combined_description += f" and {len(descriptions) - 3} more functions."
                
                module_spec = ModuleSpecification(
                    module_name=module_name,
                    file_path=file_path,
                    original_language=original_language,
                    module_type="module",
                    description=combined_description,
                    inputs=all_inputs,
                    outputs=all_outputs,
                    operations=all_operations,
                    side_effects=all_side_effects,
                    dependencies=all_dependencies,
                    module_calls=all_module_calls,
                    algorithms=all_algorithms,
                    metadata={
                        'analysis_method': 'hierarchical_function_aggregation',
                        'function_count': len(file_functions),
                        'total_operations': len(all_operations),
                        'total_side_effects': len(all_side_effects)
                    }
                )
                
                module_specifications.append(module_spec)
                logger.info(f"Created module specification for {file_path}: {len(file_functions)} functions, {len(all_operations)} operations")
            
            # Store module specifications in state for translator
            state['module_specifications'] = module_specifications
            state['specifications_ready'] = True
            
            logger.info(f"Successfully created {len(module_specifications)} module specifications from function analysis")
            
            # Save specifications to database in a non-blocking manner
            await self._save_specifications_to_database(state, module_specifications)
            
        except Exception as e:
            logger.error(f"Specification creation failed: {e}")
            state['errors'].append({"phase": "specification_creation", "error": str(e)})
        
        return state
    
    async def _check_existing_specifications(self, state: OrchestratorState) -> Optional[List[ModuleSpecification]]:
        """Check if module specifications already exist for this project."""
        try:
            postgres_config = self.config.get('postgres', {})
            if not (postgres_config.get('enabled', False) and POSTGRES_AVAILABLE):
                return None
                
            if not db_manager.connection:
                logger.info("Initializing PostgreSQL connection...")
                await db_manager.initialize(postgres_config)
            
            # Get project ID
            project_id = state.get('project_id')
            if not project_id:
                # Try to get existing project record
                from ..persistence.translation_project_repository import translation_project_repo
                project_root = state.get('root_path', '')
                target_language = state.get('target_language', '')
                
                if project_root and target_language:
                    try:
                        project_record = await translation_project_repo.get_translation_project(
                            project_root, target_language
                        )
                        if project_record:
                            project_id = str(project_record['id'])
                            state['project_id'] = project_id
                    except Exception as e:
                        logger.warning(f"Failed to get existing translation project: {e}")
                        return None
            
            if project_id:
                # Check for existing module specifications
                from ..persistence.repositories import module_spec_repo
                try:
                    existing_specs = await module_spec_repo.get_module_specifications(UUID(project_id))
                    if existing_specs:
                        logger.info(f"Found {len(existing_specs)} existing module specifications")
                        return existing_specs
                except Exception as e:
                    logger.warning(f"Failed to retrieve existing module specifications: {e}")
                    
        except Exception as e:
            logger.warning(f"Error checking for existing specifications: {e}")
            
        return None
    
    async def _translate_modules(self, state: OrchestratorState) -> OrchestratorState:
        """Phase 8: Translate modules using hierarchical specs and save to files."""
        logger.info("Phase 8: Module Translation")
        state['phase'] = 'translation'
        
        if state.get('config', {}).get('dry_run'):
            logger.info("Dry run mode - skipping translation")
            state['translation_skipped'] = True
            return state
        
        try:
            # Get module specifications created in previous phase
            module_specifications = state.get('module_specifications', [])
            if not module_specifications:
                logger.warning("No module specifications found for translation")
                return state
            
            # Initialize translation state
            if 'translation_state' not in state:
                state['translation_state'] = {
                    'translated_modules': {},
                    'errors': []
                }
            
            # Translate each module specification
            for module_spec in module_specifications:
                logger.info(f"Translating module: {module_spec.module_name}")
                
                # Set current module for translator
                state['current_module'] = module_spec
                
                try:
                    # Process with translator
                    state = await self.translator.process(state)
                    
                    if state.get('errors'):
                        logger.warning(f"Errors encountered: {state['errors']}")
                        
                except Exception as e:
                    logger.error(f"Error translating module {module_spec.module_name}: {e}")
                    state['errors'].append({"module": module_spec.module_name, "error": str(e)})
            
            # Clear current_module after translation
            state['current_module'] = None
            
            translation_state = state.get('translation_state', {})
            translated_modules = translation_state.get('translated_modules', {})
            logger.info(f"Translation completed: {len(translated_modules)} modules")
            
            # Save translated modules to files
            if translated_modules and not state.get('translation_skipped'):
                output_path = Path(state.get('target_output_path', './translated_output'))
                output_path.mkdir(parents=True, exist_ok=True)
                
                for module_path, translation_data in translated_modules.items():
                    if isinstance(translation_data, dict) and 'code' in translation_data:
                        code_content = translation_data['code']
                        target_file_path = translation_data.get('output_path', module_path)

                        target_file = Path(target_file_path)
                        target_file.parent.mkdir(parents=True, exist_ok=True)

                        with open(target_file, 'w', encoding='utf-8') as f:
                            f.write(code_content)

                        logger.info(f"Saved translated module to {target_file}")
                    else:
                        logger.warning(f"Invalid translation data for {module_path}: {translation_data}")
                
                logger.info(f"Translated code saved to {output_path}")
            
        except Exception as e:
            logger.error(f"Translation failed: {e}")
            state['errors'].append({"phase": "translation", "error": str(e)})
        
        return state
    
    
    def _detect_language_from_path(self, file_path: str) -> str:
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
    
    
    def _collect_errors(self, final_state: OrchestratorState) -> List[Dict[str, Any]]:
        """Collect all errors from the workflow."""
        errors = final_state.get('errors', [])
        
        # Add any analysis-specific errors
        if 'analysis_state' in final_state and final_state['analysis_state']:
            errors.extend(final_state['analysis_state'].get('errors', []))
        
        if 'translation_state' in final_state and final_state['translation_state']:
            errors.extend(final_state['translation_state'].get('errors', []))
        
        return errors
    
    async def _save_specifications_to_database(self, state: OrchestratorState, module_specifications: List[ModuleSpecification]):
        """Save module specifications to database in a non-blocking manner."""
        try:
            # Initialize database if not already done
            postgres_config = self.config.get('postgres', {})
            if postgres_config.get('enabled', False) and POSTGRES_AVAILABLE:
                if not db_manager.connection:
                    logger.info("Initializing PostgreSQL connection...")
                    await db_manager.initialize(postgres_config)
                
                # Save translation project record if not already done
                project_id = state.get('project_id')
                if not project_id:
                    # Create translation project record
                    from ..persistence.translation_project_repository import translation_project_repo
                    project_root = state.get('root_path', '')
                    target_language = state.get('target_language', '')
                    output_path = state.get('target_output_path', './translated')
                    
                    if project_root and target_language:
                        try:
                            project_id = await translation_project_repo.create_translation_project(
                                project_root, target_language, output_path
                            )
                            state['project_id'] = str(project_id)
                            logger.info(f"Created translation project record with ID: {project_id}")
                        except Exception as e:
                            logger.warning(f"Failed to create translation project record: {e}")
                            return
                
                # Save module specifications
                if project_id and module_specifications:
                    try:
                        from ..persistence.repositories import module_spec_repo
                        spec_ids = await module_spec_repo.save_module_specifications(
                            UUID(project_id), module_specifications
                        )
                        logger.info(f"Saved {len(spec_ids)} module specifications to database")
                    except Exception as e:
                        logger.warning(f"Failed to save module specifications: {e}")
                
            elif postgres_config.get('enabled', False) and not POSTGRES_AVAILABLE:
                logger.warning("PostgreSQL persistence enabled but asyncpg not available. Install with: pip install asyncpg")
            else:
                logger.info("PostgreSQL persistence disabled in configuration")
                
        except Exception as e:
            logger.warning(f"Non-critical database saving failed: {e}")
            # Continue execution even if database saving fails
            state['errors'].append({"phase": "database_saving", "error": str(e)})
    
    def get_workflow_status(self) -> Dict[str, Any]:
        """Get current workflow status."""
        if not self.checkpoint_manager:
            return {"status": "not_started"}
        
        workflow_checkpoint = WorkflowCheckpoint.load(self.checkpoint_manager)
        if not workflow_checkpoint:
            return {"status": "not_started"}
        
        agent_checkpoints = self.checkpoint_manager.list_agent_checkpoints()
        
        return {
            "workflow_id": self.workflow_id,
            "phase": workflow_checkpoint.current_phase,
            "completed_agents": workflow_checkpoint.completed_agents,
            "failed_agents": workflow_checkpoint.failed_agents,
            "agent_progress": agent_checkpoints
        }