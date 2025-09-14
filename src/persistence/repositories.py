"""
Repository for managing translation projects in PostgreSQL.
"""
import asyncio
import json
import logging
from typing import Dict, Any, Optional, List
from uuid import UUID
from datetime import datetime
from pathlib import Path
import asyncpg
import json

from .pg_connection import db_manager
from ..models.graph_state import OrchestratorState
from ..models.specification import ModuleSpecification

logger = logging.getLogger(__name__)


class DocumentationRepository:
    """Repository for saving codebase documentation to PostgreSQL - NOW REMOVED."""
    
    def __init__(self):
        self.db_manager = db_manager
    
    async def save_project(self, project_spec: Any, workflow_id: Optional[str] = None) -> UUID:
        """Save project specification to database - REMOVED."""
        logger.warning("Documentation saving is disabled - project documentation not saved")
        return UUID('00000000-0000-0000-0000-000000000000')
    
    async def save_folder_structure(self, project_id: UUID, folder_spec: Any, parent_id: Optional[UUID] = None) -> UUID:
        """Save folder structure to database - REMOVED."""
        logger.warning("Documentation saving is disabled - folder structure not saved")
        return UUID('00000000-0000-0000-0000-000000000000')
    
    async def save_files(self, project_id: UUID, folder_id: UUID, files: List[Any]):
        """Save file classifications to database - REMOVED."""
        logger.warning("Documentation saving is disabled - file classifications not saved")
    
    async def save_function_analysis(self, project_id: UUID, function_specs: Dict[str, List[Dict[str, Any]]]):
        """Save function analysis data - REMOVED."""
        logger.warning("Documentation saving is disabled - function analysis not saved")


# Global repository instance
documentation_repo = DocumentationRepository()


class ModuleSpecificationRepository:
    """Repository for saving and retrieving module specifications."""
    
    def __init__(self):
        self.db_manager = db_manager
    
    async def save_module_specifications(self, project_id: UUID, module_specs: List[ModuleSpecification]) -> List[UUID]:
        """Save module specifications to database."""
        if not module_specs:
            return []
            
        connection = self.db_manager.get_connection()
        pool = connection.get_pool()
        
        saved_ids = []
        
        async with pool.acquire() as conn:
            for spec in module_specs:
                try:
                    # Convert the entire specification to JSON
                    spec_data = spec.model_dump()
                    
                    spec_id = await conn.fetchval("""
                        INSERT INTO module_specifications (
                            project_id, module_name, file_path, original_language,
                            module_type, description, specification_data
                        ) VALUES ($1, $2, $3, $4, $5, $6, $7)
                        RETURNING id
                    """, str(project_id), spec.module_name, spec.file_path, spec.original_language,
                       spec.module_type, spec.description, json.dumps(spec_data))
                    
                    saved_ids.append(spec_id)
                    logger.info(f"Saved module specification: {spec.module_name} with ID: {spec_id}")
                    
                except Exception as e:
                    logger.warning(f"Failed to save module specification {spec.module_name}: {e}")
                    # Continue with other specifications
                    continue
        
        return saved_ids
    
    async def get_module_specifications(self, project_id: UUID) -> List[ModuleSpecification]:
        """Retrieve module specifications from database."""
        connection = self.db_manager.get_connection()
        pool = connection.get_pool()
        
        async with pool.acquire() as conn:
            try:
                rows = await conn.fetch("""
                    SELECT specification_data FROM module_specifications
                    WHERE project_id = $1
                    ORDER BY module_name
                """, project_id)
                
                specs = []
                for row in rows:
                    try:
                        spec_data = row['specification_data']
                        if isinstance(spec_data, str):
                            spec_data = json.loads(spec_data)
                        spec = ModuleSpecification(**spec_data)
                        specs.append(spec)
                    except Exception as e:
                        logger.warning(f"Failed to deserialize module specification: {e}")
                        continue
                
                logger.info(f"Retrieved {len(specs)} module specifications for project {project_id}")
                return specs
                
            except Exception as e:
                logger.warning(f"Failed to retrieve module specifications for project {project_id}: {e}")
                return []


# Global repository instance
module_spec_repo = ModuleSpecificationRepository()