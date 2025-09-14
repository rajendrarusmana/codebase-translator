"""
Agent-specific checkpoint management for granular recovery.
"""
import json
import hashlib
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime
from pydantic import BaseModel, Field
import logging

logger = logging.getLogger(__name__)


class AgentCheckpoint(BaseModel):
    """Base checkpoint model for individual agents."""
    agent_name: str
    agent_phase: str
    timestamp: datetime = Field(default_factory=datetime.now)
    state: Dict[str, Any]
    progress: Dict[str, Any] = Field(default_factory=dict)
    parent_checkpoint_id: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class CheckpointManager:
    """Manages checkpoints for all agents in a workflow."""
    
    def __init__(self, workflow_id: str, checkpoint_dir: str = ".codebase_translator"):
        self.workflow_id = workflow_id
        self.base_dir = Path(checkpoint_dir) / f"workflow_{workflow_id}"
        self.base_dir.mkdir(parents=True, exist_ok=True)
        
    def _get_agent_checkpoint_path(self, agent_name: str, suffix: str = "") -> Path:
        """Get checkpoint file path for an agent."""
        filename = f"{agent_name}{suffix}.json" if suffix else f"{agent_name}.json"
        return self.base_dir / filename
    
    def save_agent_state(
        self, 
        agent_name: str, 
        state: Dict[str, Any], 
        progress: Optional[Dict[str, Any]] = None,
        phase: str = "processing",
        parent_id: Optional[str] = None
    ) -> str:
        """Save an agent's current state to checkpoint."""
        checkpoint = AgentCheckpoint(
            agent_name=agent_name,
            agent_phase=phase,
            state=state,
            progress=progress or {},
            parent_checkpoint_id=parent_id
        )
        
        checkpoint_path = self._get_agent_checkpoint_path(agent_name)
        
        with open(checkpoint_path, 'w', encoding='utf-8') as f:
            try:
                # Pydantic v2
                json.dump(checkpoint.model_dump(mode='json'), f, indent=2, default=str)
            except AttributeError:
                # Pydantic v1 fallback
                json.dump(checkpoint.dict(default=str), f, indent=2)
        
        logger.debug(f"Saved checkpoint for {agent_name} at {checkpoint_path}")
        return str(checkpoint_path)
    
    def load_agent_state(self, agent_name: str) -> Optional[AgentCheckpoint]:
        """Load an agent's checkpoint if it exists."""
        checkpoint_path = self._get_agent_checkpoint_path(agent_name)
        
        if not checkpoint_path.exists():
            return None
        
        try:
            with open(checkpoint_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Convert timestamp string back to datetime
            if 'timestamp' in data and isinstance(data['timestamp'], str):
                data['timestamp'] = datetime.fromisoformat(data['timestamp'])
            
            return AgentCheckpoint(**data)
        
        except Exception as e:
            logger.error(f"Failed to load checkpoint for {agent_name}: {e}")
            return None
    
    def get_resume_point(self, agent_name: str) -> Dict[str, Any]:
        """Get the resume point for an agent."""
        checkpoint = self.load_agent_state(agent_name)
        
        if not checkpoint:
            return {"status": "not_started", "state": {}}
        
        if checkpoint.agent_phase == "completed":
            return {"status": "completed", "state": checkpoint.state}
        
        return {
            "status": "resume",
            "phase": checkpoint.agent_phase,
            "state": checkpoint.state,
            "progress": checkpoint.progress
        }
    
    def cleanup_completed_agent(self, agent_name: str) -> bool:
        """Remove checkpoint for a completed agent."""
        checkpoint_path = self._get_agent_checkpoint_path(agent_name)
        
        if checkpoint_path.exists():
            checkpoint_path.unlink()
            logger.debug(f"Cleaned up checkpoint for {agent_name}")
            return True
        
        return False
    
    def cleanup_workflow(self) -> bool:
        """Remove all checkpoints for this workflow."""
        try:
            import shutil
            if self.base_dir.exists():
                shutil.rmtree(self.base_dir)
                logger.info(f"Cleaned up workflow checkpoints at {self.base_dir}")
                return True
        except Exception as e:
            logger.error(f"Failed to cleanup workflow: {e}")
        
        return False
    
    def list_agent_checkpoints(self) -> List[Dict[str, Any]]:
        """List all agent checkpoints for this workflow."""
        checkpoints = []
        
        for checkpoint_file in self.base_dir.glob("*.json"):
            if checkpoint_file.name == "workflow.json":
                continue
                
            try:
                checkpoint = self.load_agent_state(checkpoint_file.stem)
                if checkpoint:
                    checkpoints.append({
                        "agent": checkpoint.agent_name,
                        "phase": checkpoint.agent_phase,
                        "timestamp": checkpoint.timestamp,
                        "progress": checkpoint.progress
                    })
            except Exception as e:
                logger.debug(f"Could not load checkpoint {checkpoint_file}: {e}")
        
        return checkpoints
    
    def save_batch_checkpoint(
        self,
        agent_name: str,
        batch_id: str,
        state: Dict[str, Any],
        progress: Optional[Dict[str, Any]] = None
    ) -> str:
        """Save a batch checkpoint for agents that process in batches."""
        batch_dir = self.base_dir / agent_name
        batch_dir.mkdir(exist_ok=True)
        
        checkpoint = AgentCheckpoint(
            agent_name=agent_name,
            agent_phase=f"batch_{batch_id}",
            state=state,
            progress=progress or {}
        )
        
        checkpoint_path = batch_dir / f"batch_{batch_id}.json"
        
        with open(checkpoint_path, 'w', encoding='utf-8') as f:
            try:
                # Pydantic v2
                json.dump(checkpoint.model_dump(mode='json'), f, indent=2, default=str)
            except AttributeError:
                # Pydantic v1 fallback
                json.dump(checkpoint.dict(default=str), f, indent=2)
        
        logger.debug(f"Saved batch checkpoint for {agent_name} batch {batch_id}")
        return str(checkpoint_path)
    
    def load_batch_checkpoints(self, agent_name: str) -> List[AgentCheckpoint]:
        """Load all batch checkpoints for an agent."""
        batch_dir = self.base_dir / agent_name
        
        if not batch_dir.exists():
            return []
        
        checkpoints = []
        for batch_file in sorted(batch_dir.glob("batch_*.json")):
            try:
                with open(batch_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                if 'timestamp' in data and isinstance(data['timestamp'], str):
                    data['timestamp'] = datetime.fromisoformat(data['timestamp'])
                
                checkpoints.append(AgentCheckpoint(**data))
            except Exception as e:
                logger.error(f"Failed to load batch checkpoint {batch_file}: {e}")
        
        return checkpoints


class WorkflowCheckpoint(BaseModel):
    """Overall workflow checkpoint coordinating all agents."""
    workflow_id: str
    project_root: str
    target_language: str
    current_phase: str
    agent_statuses: Dict[str, str] = Field(default_factory=dict)
    completed_agents: List[str] = Field(default_factory=list)
    failed_agents: List[str] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=datetime.now)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    def get_resume_strategy(self) -> Dict[str, List[str]]:
        """Determine which agents need to resume."""
        all_agents = [
            "project_analyzer",
            "traverser", 
            "file_classifier",
            "function_extractor",
            "documenter",
            "translator"
        ]
        
        skip_agents = self.completed_agents
        resume_agents = [
            agent for agent, status in self.agent_statuses.items()
            if status not in ["completed", "not_started", "failed"]
        ]
        start_agents = [
            agent for agent in all_agents
            if agent not in skip_agents and agent not in resume_agents
        ]
        
        return {
            "skip_agents": skip_agents,
            "resume_agents": resume_agents,
            "start_agents": start_agents,
            "failed_agents": self.failed_agents
        }
    
    def save(self, checkpoint_manager: CheckpointManager) -> str:
        """Save workflow checkpoint."""
        checkpoint_path = checkpoint_manager.base_dir / "workflow.json"
        
        with open(checkpoint_path, 'w', encoding='utf-8') as f:
            try:
                # Pydantic v2
                json.dump(self.model_dump(mode='json'), f, indent=2, default=str)
            except AttributeError:
                # Pydantic v1 fallback
                json.dump(self.dict(default=str), f, indent=2)
        
        logger.info(f"Saved workflow checkpoint at {checkpoint_path}")
        return str(checkpoint_path)
    
    @classmethod
    def load(cls, checkpoint_manager: CheckpointManager) -> Optional['WorkflowCheckpoint']:
        """Load workflow checkpoint."""
        checkpoint_path = checkpoint_manager.base_dir / "workflow.json"
        
        if not checkpoint_path.exists():
            return None
        
        try:
            with open(checkpoint_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            if 'timestamp' in data and isinstance(data['timestamp'], str):
                data['timestamp'] = datetime.fromisoformat(data['timestamp'])
            
            return cls(**data)
        
        except Exception as e:
            logger.error(f"Failed to load workflow checkpoint: {e}")
            return None