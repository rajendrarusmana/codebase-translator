from typing import Dict, Any, List, Optional
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from ..models.graph_state import OrchestratorState
from ..agents.traverser_agent import TraverserAgent
from ..agents.documenter_agent import DocumenterAgent
from ..agents.translator_agent import TranslatorAgent
from ..models.specification import CodebaseSpecification, ModuleSpecification
from ..persistence.checkpoint import WorkflowCheckpoint
from pathlib import Path
import asyncio
import logging

logger = logging.getLogger(__name__)

class CodebaseTranslatorWorkflow:
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.traverser = TraverserAgent(**config.get('traverser', {}))
        self.documenter = DocumenterAgent(**config.get('documenter', {}))
        self.translator = TranslatorAgent(**config.get('translator', {}))
        self.checkpoint = WorkflowCheckpoint()
        self.graph = self._build_graph()
    
    def _build_graph(self) -> StateGraph:
        graph = StateGraph(OrchestratorState)
        
        graph.add_node("traverse", self._traverse_codebase)
        graph.add_node("document_modules", self._document_modules)
        graph.add_node("create_specifications", self._create_specifications)
        graph.add_node("translate_modules", self._translate_modules)
        graph.add_node("save_output", self._save_output)
        graph.add_node("human_review", self._human_review)
        
        graph.add_edge("traverse", "document_modules")
        graph.add_edge("document_modules", "create_specifications")
        
        graph.add_conditional_edges(
            "create_specifications",
            self._should_review,
            {
                "review": "human_review",
                "translate": "translate_modules"
            }
        )
        
        graph.add_edge("human_review", "translate_modules")
        graph.add_edge("translate_modules", "save_output")
        graph.add_edge("save_output", END)
        
        graph.set_entry_point("traverse")
        
        return graph.compile()
    
    async def _traverse_codebase(self, state: OrchestratorState) -> OrchestratorState:
        logger.info("Starting codebase traversal...")
        
        analysis_state = {
            'root_path': state['root_path'],
            'target_language': state['target_language'],
            'file_paths': [],
            'current_module': None,
            'processed_modules': [],
            'module_specs': [],
            'codebase_spec': None,
            'dependencies': {},
            'errors': [],
            'messages': []
        }
        
        analysis_state = await self.traverser.process(analysis_state)
        
        state['analysis_state'] = analysis_state
        state['phase'] = 'traversal_complete'
        
        return state
    
    async def _document_modules(self, state: OrchestratorState) -> OrchestratorState:
        logger.info("Starting module documentation...")
        
        analysis_state = state['analysis_state']
        modules = analysis_state.get('modules', {})
        processed_modules = analysis_state.get('processed_modules', [])
        
        # Process all files, skipping already processed ones for resumability
        all_files = [file_path for files in modules.values() for file_path in files]
        remaining_files = [f for f in all_files if f not in processed_modules]
        
        logger.info(f"Processing {len(remaining_files)} remaining files (out of {len(all_files)} total)")
        
        for i, file_path in enumerate(remaining_files):
            analysis_state['current_module'] = file_path
            analysis_state = await self.documenter.process(analysis_state)
            
            # Save checkpoint after each module (for large codebases)
            if i % 5 == 0:  # Save every 5 modules
                state['analysis_state'] = analysis_state
                checkpoint_path = self.checkpoint.save_state(state)
                logger.debug(f"Saved checkpoint: {checkpoint_path}")
        
        state['analysis_state'] = analysis_state
        state['phase'] = 'documentation_complete'
        
        return state
    
    async def _create_specifications(self, state: OrchestratorState) -> OrchestratorState:
        logger.info("Creating codebase specification...")
        
        analysis_state = state['analysis_state']
        
        codebase_spec = CodebaseSpecification(
            project_name=Path(state['root_path']).name,
            root_path=state['root_path'],
            original_language=analysis_state.get('source_language', 'unknown'),
            modules=analysis_state.get('module_specs', []),
            entry_points=analysis_state.get('entry_points', []),
            metadata={
                'total_files': len(analysis_state.get('file_paths', [])),
                'errors': analysis_state.get('errors', [])
            }
        )
        
        analysis_state['codebase_spec'] = codebase_spec
        state['analysis_state'] = analysis_state
        state['phase'] = 'specification_ready'
        
        return state
    
    async def _translate_modules(self, state: OrchestratorState) -> OrchestratorState:
        logger.info("Starting module translation...")
        
        analysis_state = state['analysis_state']
        codebase_spec = analysis_state['codebase_spec']
        
        translation_state = {
            'source_spec': codebase_spec,
            'target_language': state['target_language'],
            'current_module': None,
            'translated_modules': {},
            'translation_mapping': {},
            'output_path': state.get('config', {}).get('output_path', 'translated'),
            'errors': [],
            'messages': []
        }
        
        for module_spec in codebase_spec.modules:
            translation_state['current_module'] = module_spec
            translation_state = await self.translator.process(translation_state)
        
        state['translation_state'] = translation_state
        state['phase'] = 'translation_complete'
        
        return state
    
    async def _save_output(self, state: OrchestratorState) -> OrchestratorState:
        logger.info("Saving translated output...")
        
        translation_state = state['translation_state']
        
        for original_path, translation_data in translation_state['translated_modules'].items():
            output_path = Path(translation_data['output_path'])
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(translation_data['code'])
            
            logger.info(f"Saved translated module: {output_path}")
        
        state['phase'] = 'complete'
        state['completed'] = True
        
        return state
    
    async def _human_review(self, state: OrchestratorState) -> OrchestratorState:
        logger.info("Waiting for human review...")
        
        analysis_state = state['analysis_state']
        codebase_spec = analysis_state.get('codebase_spec')
        
        if codebase_spec:
            print("\n=== CODEBASE SPECIFICATION READY FOR REVIEW ===")
            print(f"Project: {codebase_spec.project_name}")
            print(f"Language: {codebase_spec.original_language}")
            print(f"Modules found: {len(codebase_spec.modules)}")
            print(f"Entry points: {codebase_spec.entry_points}")
            
            if analysis_state.get('errors'):
                print(f"\nErrors encountered: {len(analysis_state['errors'])}")
                for error in analysis_state['errors'][:3]:
                    print(f"  - {error}")
            
            feedback = input("\nProceed with translation? (y/n/feedback): ").strip().lower()
            
            if feedback == 'n':
                state['completed'] = True
                return state
            elif feedback not in ['y', 'yes']:
                state['human_feedback'] = feedback
        
        return state
    
    def _should_review(self, state: OrchestratorState) -> str:
        config = state.get('config', {})
        if config.get('human_review', False):
            return "review"
        return "translate"
    
    async def run(self, root_path: str, target_language: str, resume: bool = False, **kwargs) -> Dict[str, Any]:
        # Try to resume from checkpoint if requested
        if resume and self.checkpoint.checkpoint_exists(root_path, target_language):
            logger.info("Resuming from checkpoint...")
            initial_state = self.checkpoint.load_state(root_path, target_language)
            if initial_state:
                logger.info(f"Resumed from phase: {initial_state['phase']}")
                # Update config with any new values
                initial_state['config'].update(kwargs)
            else:
                logger.warning("Failed to load checkpoint, starting fresh")
                resume = False
        
        if not resume or not initial_state:
            initial_state = OrchestratorState(
                messages=[],
                root_path=root_path,
                source_language=None,
                target_language=target_language,
                analysis_state=None,
                translation_state=None,
                phase="starting",
                completed=False,
                human_feedback=None,
                config=kwargs
            )
        
        try:
            # Save initial checkpoint
            self.checkpoint.save_state(initial_state)
            
            final_state = await self.graph.ainvoke(initial_state)
            
            # Clean up checkpoint on successful completion
            if final_state.get('completed'):
                self.checkpoint.remove_checkpoint(root_path, target_language)
                logger.info("Workflow completed, checkpoint removed")
            
            return {
                "success": True,
                "final_state": final_state,
                "errors": final_state.get('analysis_state', {}).get('errors', []) +
                         final_state.get('translation_state', {}).get('errors', [])
            }
        
        except Exception as e:
            logger.error(f"Workflow execution failed: {e}")
            # Save error state for debugging
            if 'initial_state' in locals():
                initial_state['phase'] = 'error'
                self.checkpoint.save_state(initial_state)
            return {
                "success": False,
                "error": str(e),
                "final_state": initial_state
            }
    
    def get_checkpoint_info(self, root_path: str, target_language: str) -> Optional[Dict[str, Any]]:
        """Get information about available checkpoint."""
        checkpoints = self.checkpoint.list_checkpoints()
        for cp in checkpoints:
            if cp['root_path'] == root_path and cp['target_language'] == target_language:
                return cp
        return None