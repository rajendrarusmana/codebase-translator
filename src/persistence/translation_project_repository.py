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

from .pg_connection import db_manager
from ..models.graph_state import OrchestratorState

logger = logging.getLogger(__name__)


class TranslationProjectRepository:
    """Repository for tracking translation projects in PostgreSQL."""
    
    def __init__(self):
        self.db_manager = db_manager
    
    async def create_translation_project(
        self, 
        project_root: str, 
        target_language: str, 
        output_path: str
    ) -> UUID:
        """Create a new translation project record."""
        connection = self.db_manager.get_connection()
        pool = connection.get_pool()
        
        async with pool.acquire() as conn:
            # Extract project name from root path
            project_name = Path(project_root).name
            
            # Insert translation project record
            project_id = await conn.fetchval("""
                INSERT INTO translation_projects (
                    project_name, project_root, target_language, output_path, status
                ) VALUES ($1, $2, $3, $4, $5)
                ON CONFLICT (project_name, target_language) 
                DO UPDATE SET 
                    project_root = EXCLUDED.project_root,
                    output_path = EXCLUDED.output_path,
                    status = EXCLUDED.status,
                    created_at = CURRENT_TIMESTAMP
                RETURNING id
            """, project_name, project_root, target_language, output_path, 'started')
            
            logger.info(f"Created translation project record: {project_name}-{target_language} with ID: {project_id}")
            return project_id
    
    async def update_translation_project_status(
        self, 
        project_id: UUID, 
        status: str, 
        completed_at: Optional[datetime] = None
    ):
        """Update translation project status."""
        connection = self.db_manager.get_connection()
        pool = connection.get_pool()
        
        async with pool.acquire() as conn:
            await conn.execute("""
                UPDATE translation_projects 
                SET status = $1, completed_at = $2
                WHERE id = $3
            """, status, completed_at, project_id)
            
            logger.info(f"Updated translation project {project_id} status to: {status}")
    
    async def get_translation_project(
        self, 
        project_root: str, 
        target_language: str
    ) -> Optional[Dict[str, Any]]:
        """Get translation project by root path and target language."""
        connection = self.db_manager.get_connection()
        pool = connection.get_pool()
        
        async with pool.acquire() as conn:
            project = await conn.fetchrow("""
                SELECT * FROM translation_projects 
                WHERE project_root = $1 AND target_language = $2
            """, project_root, target_language)
            
            return dict(project) if project else None
    
    async def list_translation_projects(
        self, 
        status: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """List translation projects, optionally filtered by status."""
        connection = self.db_manager.get_connection()
        pool = connection.get_pool()
        
        async with pool.acquire() as conn:
            if status:
                projects = await conn.fetch("""
                    SELECT * FROM translation_projects 
                    WHERE status = $1
                    ORDER BY created_at DESC
                """, status)
            else:
                projects = await conn.fetch("""
                    SELECT * FROM translation_projects 
                    ORDER BY created_at DESC
                """)
            
            return [dict(project) for project in projects]


# Global repository instance
translation_project_repo = TranslationProjectRepository()