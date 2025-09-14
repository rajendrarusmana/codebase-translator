"""
State persistence for resumable workflows.
"""
import json
import pickle
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime
import hashlib

from ..models.graph_state import OrchestratorState
from ..models.specification import ModuleSpecification, CodebaseSpecification


class WorkflowCheckpoint:
    """Manages saving and loading workflow state for resumability."""
    
    def __init__(self, checkpoint_dir: str = ".codebase_translator"):
        self.checkpoint_dir = Path(checkpoint_dir)
        self.checkpoint_dir.mkdir(exist_ok=True)
    
    def _get_project_hash(self, root_path: str) -> str:
        """Generate unique hash for project to avoid conflicts."""
        return hashlib.md5(str(Path(root_path).absolute()).encode()).hexdigest()[:8]
    
    def _get_checkpoint_path(self, root_path: str, target_language: str) -> Path:
        """Get checkpoint file path for a specific translation."""
        project_hash = self._get_project_hash(root_path)
        filename = f"checkpoint_{project_hash}_{target_language}.json"
        return self.checkpoint_dir / filename
    
    def save_state(self, state: OrchestratorState) -> str:
        """Save current workflow state to checkpoint file."""
        checkpoint_path = self._get_checkpoint_path(
            state['root_path'], 
            state['target_language']
        )
        
        # Convert state to serializable format
        serializable_state = self._serialize_state(state)
        
        with open(checkpoint_path, 'w', encoding='utf-8') as f:
            json.dump(serializable_state, f, indent=2, default=str)
        
        return str(checkpoint_path)
    
    def load_state(self, root_path: str, target_language: str) -> Optional[OrchestratorState]:
        """Load workflow state from checkpoint file."""
        checkpoint_path = self._get_checkpoint_path(root_path, target_language)
        
        if not checkpoint_path.exists():
            return None
        
        try:
            with open(checkpoint_path, 'r', encoding='utf-8') as f:
                serializable_state = json.load(f)
            
            return self._deserialize_state(serializable_state)
        
        except Exception as e:
            print(f"Warning: Failed to load checkpoint {checkpoint_path}: {e}")
            return None
    
    def checkpoint_exists(self, root_path: str, target_language: str) -> bool:
        """Check if a checkpoint exists for this translation."""
        return self._get_checkpoint_path(root_path, target_language).exists()
    
    def remove_checkpoint(self, root_path: str, target_language: str) -> bool:
        """Remove checkpoint file after successful completion."""
        checkpoint_path = self._get_checkpoint_path(root_path, target_language)
        if checkpoint_path.exists():
            checkpoint_path.unlink()
            return True
        return False
    
    def list_checkpoints(self) -> list:
        """List all available checkpoints."""
        checkpoints = []
        for checkpoint_file in self.checkpoint_dir.glob("checkpoint_*.json"):
            try:
                with open(checkpoint_file, 'r') as f:
                    data = json.load(f)
                checkpoints.append({
                    'file': checkpoint_file.name,
                    'root_path': data.get('root_path'),
                    'target_language': data.get('target_language'),
                    'phase': data.get('phase'),
                    'timestamp': data.get('metadata', {}).get('checkpoint_time'),
                    'processed_modules': len(data.get('analysis_state', {}).get('processed_modules', []))
                })
            except Exception:
                continue
        return checkpoints
    
    def _serialize_state(self, state: OrchestratorState) -> Dict[str, Any]:
        """Convert OrchestratorState to JSON-serializable format."""
        serializable = {
            'root_path': state['root_path'],
            'source_language': state.get('source_language'),
            'target_language': state['target_language'],
            'phase': state['phase'],
            'completed': state['completed'],
            'human_feedback': state.get('human_feedback'),
            'config': state.get('config', {}),
            'messages': state.get('messages', []),
            'metadata': {
                'checkpoint_time': datetime.now().isoformat(),
                'version': '1.0'
            }
        }
        
        # Serialize analysis_state
        if state.get('analysis_state'):
            analysis = state['analysis_state']
            serializable['analysis_state'] = {
                'root_path': analysis.get('root_path'),
                'target_language': analysis.get('target_language'),
                'file_paths': analysis.get('file_paths', []),
                'current_module': analysis.get('current_module'),
                'processed_modules': analysis.get('processed_modules', []),
                'dependencies': analysis.get('dependencies', {}),
                'errors': analysis.get('errors', []),
                'messages': analysis.get('messages', []),
                'module_specs': [self._serialize_module_spec(spec) for spec in analysis.get('module_specs', [])],
                'codebase_spec': self._serialize_codebase_spec(analysis.get('codebase_spec')) if analysis.get('codebase_spec') else None
            }
        
        # Serialize translation_state
        if state.get('translation_state'):
            translation = state['translation_state']
            serializable['translation_state'] = {
                'target_language': translation.get('target_language'),
                'translated_modules': translation.get('translated_modules', {}),
                'translation_mapping': translation.get('translation_mapping', {}),
                'output_path': translation.get('output_path'),
                'errors': translation.get('errors', []),
                'messages': translation.get('messages', []),
                'source_spec': self._serialize_codebase_spec(translation.get('source_spec')) if translation.get('source_spec') else None,
                'current_module': self._serialize_module_spec(translation.get('current_module')) if translation.get('current_module') else None
            }
        
        return serializable
    
    def _serialize_module_spec(self, spec: ModuleSpecification) -> Dict[str, Any]:
        """Serialize ModuleSpecification to dict."""
        return {
            'module_name': spec.module_name,
            'file_path': spec.file_path,
            'original_language': spec.original_language,
            'description': spec.description,
            'inputs': [input_spec.dict() for input_spec in (spec.inputs or [])],
            'outputs': [output_spec.dict() for output_spec in (spec.outputs or [])],
            'operations': [op.dict() for op in (spec.operations or [])],
            'side_effects': [se.dict() for se in (spec.side_effects or [])],
            'dependencies': [dep.dict() for dep in (spec.dependencies or [])],
            'module_calls': [call.dict() for call in (spec.module_calls or [])],
            'algorithms': [algo.dict() for algo in (spec.algorithms or [])],
            'data_structures': spec.data_structures or {},
            'constants': spec.constants or {},
            'metadata': spec.metadata or {}
        }
    
    def _serialize_codebase_spec(self, spec: CodebaseSpecification) -> Dict[str, Any]:
        """Serialize CodebaseSpecification to dict."""
        return {
            'project_name': spec.project_name,
            'root_path': spec.root_path,
            'original_language': spec.original_language,
            'modules': [self._serialize_module_spec(mod) for mod in spec.modules],
            'entry_points': spec.entry_points,
            'metadata': spec.metadata
        }
    
    def _deserialize_state(self, data: Dict[str, Any]) -> OrchestratorState:
        """Convert serialized data back to OrchestratorState."""
        from ..models.specification import DataType, Operation, SideEffect, Dependency, Algorithm, ModuleCall
        
        state = OrchestratorState(
            messages=data.get('messages', []),
            root_path=data['root_path'],
            source_language=data.get('source_language'),
            target_language=data['target_language'],
            phase=data['phase'],
            completed=data['completed'],
            human_feedback=data.get('human_feedback'),
            config=data.get('config', {}),
            analysis_state=None,
            translation_state=None
        )
        
        # Deserialize analysis_state
        if data.get('analysis_state'):
            analysis_data = data['analysis_state']
            module_specs = []
            for spec_data in analysis_data.get('module_specs', []):
                spec = ModuleSpecification(
                    module_name=spec_data['module_name'],
                    file_path=spec_data['file_path'],
                    original_language=spec_data['original_language'],
                    description=spec_data['description'],
                    inputs=[DataType(**inp) for inp in spec_data['inputs']],
                    outputs=[DataType(**out) for out in spec_data['outputs']],
                    operations=[Operation(**op) for op in spec_data['operations']],
                    side_effects=[SideEffect(**se) for se in spec_data['side_effects']],
                    dependencies=[Dependency(**dep) for dep in spec_data['dependencies']],
                    module_calls=[ModuleCall(**call) for call in spec_data.get('module_calls', [])],
                    algorithms=[Algorithm(**algo) for algo in spec_data['algorithms']],
                    data_structures=spec_data.get('data_structures', {}),
                    constants=spec_data.get('constants', {}),
                    metadata=spec_data.get('metadata', {})
                )
                module_specs.append(spec)
            
            codebase_spec = None
            if analysis_data.get('codebase_spec'):
                codebase_data = analysis_data['codebase_spec']
                codebase_spec = CodebaseSpecification(
                    project_name=codebase_data['project_name'],
                    root_path=codebase_data['root_path'],
                    original_language=codebase_data['original_language'],
                    modules=module_specs,  # Use the deserialized modules
                    entry_points=codebase_data['entry_points'],
                    metadata=codebase_data['metadata']
                )
            
            state['analysis_state'] = {
                'root_path': analysis_data['root_path'],
                'target_language': analysis_data['target_language'],
                'file_paths': analysis_data['file_paths'],
                'current_module': analysis_data.get('current_module'),
                'processed_modules': analysis_data['processed_modules'],
                'module_specs': module_specs,
                'codebase_spec': codebase_spec,
                'dependencies': analysis_data['dependencies'],
                'errors': analysis_data['errors'],
                'messages': analysis_data['messages']
            }
        
        # Deserialize translation_state if present
        if data.get('translation_state'):
            translation_data = data['translation_state']
            state['translation_state'] = {
                'target_language': translation_data['target_language'],
                'translated_modules': translation_data['translated_modules'],
                'translation_mapping': translation_data['translation_mapping'],
                'output_path': translation_data['output_path'],
                'errors': translation_data['errors'],
                'messages': translation_data['messages'],
                'source_spec': None,  # Will be reconstructed from analysis_state
                'current_module': None
            }
        
        return state