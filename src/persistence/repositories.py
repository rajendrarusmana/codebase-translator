"""
Repository layer for PostgreSQL persistence of documentation data.
"""
import asyncio
import json
import logging
from typing import Dict, List, Any, Optional
from uuid import UUID
from datetime import datetime
from pathlib import Path
import asyncpg

from .pg_connection import db_manager
from ..models.hierarchical_spec import ProjectSpecification, FolderSpecification, FileSpecification

logger = logging.getLogger(__name__)


class DocumentationRepository:
    """Repository for persisting codebase documentation to PostgreSQL."""
    
    def __init__(self):
        self.db_manager = db_manager
    
    async def save_project(self, project_spec: ProjectSpecification, workflow_id: Optional[str] = None) -> UUID:
        """Save project specification and return project UUID."""
        connection = self.db_manager.get_connection()
        pool = connection.get_pool()
        
        async with pool.acquire() as conn:
            async with conn.transaction():
                # Insert project
                project_id = await conn.fetchval("""
                    INSERT INTO projects (
                        project_name, root_path, project_type, architecture_pattern, 
                        primary_language, languages_used, total_files, entry_points, 
                        workflow_id
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                    ON CONFLICT (project_name, root_path) 
                    DO UPDATE SET 
                        project_type = EXCLUDED.project_type,
                        architecture_pattern = EXCLUDED.architecture_pattern,
                        primary_language = EXCLUDED.primary_language,
                        languages_used = EXCLUDED.languages_used,
                        total_files = EXCLUDED.total_files,
                        entry_points = EXCLUDED.entry_points,
                        workflow_id = EXCLUDED.workflow_id
                    RETURNING id
                """, 
                    project_spec.project_name,
                    str(project_spec.project_root),
                    project_spec.project_type.value,
                    project_spec.architecture.value,
                    project_spec.primary_language,
                    project_spec.languages_used,
                    project_spec.total_files,
                    project_spec.entry_points,
                    workflow_id
                )
                
                logger.info(f"Saved project: {project_spec.project_name} with ID: {project_id}")
                return project_id
    
    async def save_folder_structure(self, project_id: UUID, folder_spec: FolderSpecification, parent_id: Optional[UUID] = None) -> UUID:
        """Save folder specification and return folder UUID."""
        connection = self.db_manager.get_connection()
        pool = connection.get_pool()
        
        async with pool.acquire() as conn:
            async with conn.transaction():
                # Insert or update the current folder
                folder_id = await conn.fetchval("""
                    INSERT INTO folders (
                        project_id, folder_path, folder_name, folder_purpose,
                        description, parent_folder_id, file_count
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7)
                    ON CONFLICT (project_id, folder_path)
                    DO UPDATE SET
                        folder_name = EXCLUDED.folder_name,
                        folder_purpose = EXCLUDED.folder_purpose,
                        description = EXCLUDED.description,
                        parent_folder_id = CASE 
                            WHEN folders.parent_folder_id IS NULL AND EXCLUDED.parent_folder_id IS NOT NULL 
                            THEN EXCLUDED.parent_folder_id
                            ELSE folders.parent_folder_id
                        END,
                        file_count = EXCLUDED.file_count
                    RETURNING id
                """,
                    project_id,
                    folder_spec.path,
                    folder_spec.name,
                    folder_spec.purpose.value,
                    folder_spec.description,
                    parent_id,
                    folder_spec.file_count
                )
                
                # Recursively save subfolders
                for subfolder in folder_spec.subfolders:
                    await self.save_folder_structure(project_id, subfolder, folder_id)
                
                return folder_id
    
    async def save_files(self, project_id: UUID, folder_id: UUID, files: List[FileSpecification]):
        """Save file specifications."""
        if not files:
            return
            
        connection = self.db_manager.get_connection()
        pool = connection.get_pool()
        
        async with pool.acquire() as conn:
            async with conn.transaction():
                for file_spec in files:
                    await conn.execute("""
                        INSERT INTO files (
                            project_id, folder_id, file_path, file_type, classification_confidence
                        ) VALUES ($1, $2, $3, $4, $5)
                        ON CONFLICT (project_id, file_path)
                        DO UPDATE SET
                            folder_id = EXCLUDED.folder_id,
                            file_type = EXCLUDED.file_type,
                            classification_confidence = EXCLUDED.classification_confidence
                    """,
                        project_id,
                        folder_id,
                        file_spec.file_path,
                        file_spec.file_type.value,
                        None  # classification_confidence - not currently provided by agents
                    )
    
    async def save_function_analysis(self, project_id: UUID, function_specs: Dict[str, List[Dict[str, Any]]]):
        """Save function analysis data with context-specific fields."""
        if not function_specs:
            return
            
        connection = self.db_manager.get_connection()
        pool = connection.get_pool()
        
        async with pool.acquire() as conn:
            async with conn.transaction():
                # Get file IDs for the functions
                file_paths = list(function_specs.keys())
                file_records = await conn.fetch("""
                    SELECT id, file_path FROM files 
                    WHERE project_id = $1 AND file_path = ANY($2)
                """, project_id, file_paths)
                
                file_id_map = {record['file_path']: record['id'] for record in file_records}
                
                for file_path, functions in function_specs.items():
                    file_id = file_id_map.get(file_path)
                    if not file_id:
                        logger.warning(f"No file record found for {file_path}")
                        continue
                    
                    for func_spec in functions:
                        await self._save_single_function(conn, project_id, file_id, func_spec)
    
    async def _save_single_function(self, conn: asyncpg.Connection, project_id: UUID, file_id: UUID, func_spec: Dict[str, Any]):
        """Save a single function with all its related data."""
        # Extract basic function info
        function_name = func_spec.get('function_name')
        parent_class = func_spec.get('parent_class')
        signature = func_spec.get('signature', function_name)
        description = func_spec.get('description')
        line_range = func_spec.get('line_range', [])
        start_line = line_range[0] if len(line_range) > 0 else None
        end_line = line_range[1] if len(line_range) > 1 else None
        
        # Extract context-specific fields
        function_context = func_spec.get('function_context')
        
        # Handler context
        http_method = func_spec.get('http_method')
        endpoint_path = func_spec.get('endpoint_path')
        status_codes = func_spec.get('status_codes', [])
        
        # Repository context
        sql_operation = func_spec.get('sql_operation')
        primary_table = func_spec.get('primary_table')
        sql_example = func_spec.get('sql_example')
        database_type = func_spec.get('database_type')
        
        # Service context
        business_domain = func_spec.get('business_domain')
        transaction_type = func_spec.get('transaction_type')
        external_dependencies = func_spec.get('external_dependencies', [])
        
        # Component context
        component_type = func_spec.get('component_type')
        ui_framework = func_spec.get('ui_framework')
        
        # Background job context
        job_queue = func_spec.get('job_queue')
        schedule_pattern = func_spec.get('schedule_pattern')
        
        # Test context
        test_type = func_spec.get('test_type')
        test_framework = func_spec.get('test_framework')
        test_case_description = func_spec.get('test_case_description')
        test_scenario = func_spec.get('test_scenario')
        function_under_test = func_spec.get('function_under_test')
        test_assertion_type = func_spec.get('test_assertion_type')
        expected_outcome = func_spec.get('expected_outcome')
        test_setup_required = func_spec.get('test_setup_required')
        mock_dependencies = func_spec.get('mock_dependencies', [])
        
        # Utility context
        utility_category = func_spec.get('utility_category')
        input_constraints = func_spec.get('input_constraints')
        output_guarantees = func_spec.get('output_guarantees')
        
        # Create function namespace
        namespace_parts = [func_spec.get('file_path', '')]
        if parent_class:
            namespace_parts.append(parent_class)
        namespace_parts.append(function_name)
        function_namespace = '.'.join(filter(None, namespace_parts))
        
        # Insert function record
        function_id = await conn.fetchval("""
            INSERT INTO functions (
                project_id, file_id, function_name, function_namespace, parent_class, 
                signature, start_line, end_line, function_context,
                http_method, endpoint_path, status_codes,
                sql_operation, primary_table, sql_example, database_type,
                business_domain, transaction_type, external_dependencies,
                component_type, ui_framework,
                job_queue, schedule_pattern,
                test_type, test_framework, test_case_description, test_scenario,
                function_under_test, test_assertion_type, expected_outcome,
                test_setup_required, mock_dependencies,
                utility_category, input_constraints, output_guarantees
            ) VALUES (
                $1, $2, $3, $4, $5, $6, $7, $8, $9,
                $10, $11, $12, $13, $14, $15, $16,
                $17, $18, $19, $20, $21, $22, $23,
                $24, $25, $26, $27, $28, $29, $30, $31, $32,
                $33, $34, $35
            )
            ON CONFLICT (project_id, file_id, function_name, parent_class)
            DO UPDATE SET
                signature = EXCLUDED.signature,
                start_line = EXCLUDED.start_line,
                end_line = EXCLUDED.end_line,
                function_context = EXCLUDED.function_context,
                http_method = EXCLUDED.http_method,
                endpoint_path = EXCLUDED.endpoint_path,
                status_codes = EXCLUDED.status_codes,
                sql_operation = EXCLUDED.sql_operation,
                primary_table = EXCLUDED.primary_table,
                sql_example = EXCLUDED.sql_example,
                database_type = EXCLUDED.database_type,
                business_domain = EXCLUDED.business_domain,
                transaction_type = EXCLUDED.transaction_type,
                external_dependencies = EXCLUDED.external_dependencies,
                component_type = EXCLUDED.component_type,
                ui_framework = EXCLUDED.ui_framework,
                job_queue = EXCLUDED.job_queue,
                schedule_pattern = EXCLUDED.schedule_pattern,
                test_type = EXCLUDED.test_type,
                test_framework = EXCLUDED.test_framework,
                test_case_description = EXCLUDED.test_case_description,
                test_scenario = EXCLUDED.test_scenario,
                function_under_test = EXCLUDED.function_under_test,
                test_assertion_type = EXCLUDED.test_assertion_type,
                expected_outcome = EXCLUDED.expected_outcome,
                test_setup_required = EXCLUDED.test_setup_required,
                mock_dependencies = EXCLUDED.mock_dependencies,
                utility_category = EXCLUDED.utility_category,
                input_constraints = EXCLUDED.input_constraints,
                output_guarantees = EXCLUDED.output_guarantees
            RETURNING id
        """,
            project_id, file_id, function_name, function_namespace, parent_class,
            signature, start_line, end_line, function_context,
            http_method, endpoint_path, status_codes,
            sql_operation, primary_table, sql_example, database_type,
            business_domain, transaction_type, external_dependencies,
            component_type, ui_framework,
            job_queue, schedule_pattern,
            test_type, test_framework, test_case_description, test_scenario,
            function_under_test, test_assertion_type, expected_outcome,
            test_setup_required, mock_dependencies,
            utility_category, input_constraints, output_guarantees
        )
        
        # Save function analysis
        analysis_method = func_spec.get('retry_reason') and 'retry' or 'pure_llm_semantic'
        retry_reason = func_spec.get('retry_reason')
        
        await conn.execute("""
            INSERT INTO function_analysis (function_id, description, analysis_method, retry_reason)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (function_id) DO UPDATE SET
                description = EXCLUDED.description,
                analysis_method = EXCLUDED.analysis_method,
                retry_reason = EXCLUDED.retry_reason
        """, function_id, description, analysis_method, retry_reason)
        
        # Save inputs, outputs, operations, side effects, and module calls
        # (Note: function_operations, function_side_effects, and related tables have been removed
        #  from the clean schema to simplify the database structure)
        await self._save_function_inputs(conn, function_id, func_spec.get('inputs', []))
        await self._save_function_outputs(conn, function_id, func_spec.get('outputs', []))
        # Removed: await self._save_function_operations(conn, function_id, func_spec.get('operations', []))
        # Removed: await self._save_function_side_effects(conn, function_id, func_spec.get('side_effects', []))
        # Removed: await self._save_function_module_calls(conn, function_id, func_spec.get('module_calls', []))
    
    async def _save_function_inputs(self, conn: asyncpg.Connection, function_id: UUID, inputs: List[Dict[str, Any]]):
        """Save function inputs."""
        # Delete existing inputs
        await conn.execute("DELETE FROM function_inputs WHERE function_id = $1", function_id)
        
        for input_spec in inputs:
            await conn.execute("""
                INSERT INTO function_inputs (function_id, input_name, input_type, description, is_optional)
                VALUES ($1, $2, $3, $4, $5)
            """,
                function_id,
                input_spec.get('name'),
                input_spec.get('type'),
                input_spec.get('description'),
                input_spec.get('optional', False)
            )
    
    async def _save_function_outputs(self, conn: asyncpg.Connection, function_id: UUID, outputs: List[Dict[str, Any]]):
        """Save function outputs."""
        # Delete existing outputs
        await conn.execute("DELETE FROM function_outputs WHERE function_id = $1", function_id)
        
        for output_spec in outputs:
            await conn.execute("""
                INSERT INTO function_outputs (function_id, output_name, output_type, description)
                VALUES ($1, $2, $3, $4)
            """,
                function_id,
                output_spec.get('name'),
                output_spec.get('type'),
                output_spec.get('description')
            )
    
    async def _save_function_operations(self, conn: asyncpg.Connection, function_id: UUID, operations: List[Dict[str, Any]]):
        """Save function operations - REMOVED from clean schema."""
        # This method has been removed as part of schema simplification
        # The function_operations table is no longer used in the clean schema
        pass
    
    async def _save_function_side_effects(self, conn: asyncpg.Connection, function_id: UUID, side_effects: List[Dict[str, Any]]):
        """Save function side effects - REMOVED from clean schema."""
        # This method has been removed as part of schema simplification
        # The function_side_effects table is no longer used in the clean schema
        pass
    
    async def _save_function_module_calls(self, conn: asyncpg.Connection, function_id: UUID, module_calls: List[Dict[str, Any]]):
        """Save function module calls - REMOVED from clean schema."""
        # This method has been removed as part of schema simplification
        # The function_module_calls table is no longer used in the clean schema
        pass
    
    async def get_project_documentation(self, project_id: UUID) -> Dict[str, Any]:
        """Get comprehensive project documentation."""
        connection = self.db_manager.get_connection()
        pool = connection.get_pool()
        
        async with pool.acquire() as conn:
            # Get project overview
            project = await conn.fetchrow("""
                SELECT * FROM project_documentation WHERE project_id = $1
            """, project_id)
            
            if not project:
                return None
            
            return dict(project)
    
    async def get_function_flows(self, project_id: UUID, function_namespace: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get function flow analysis for a project or specific function."""
        connection = self.db_manager.get_connection()
        pool = connection.get_pool()
        
        async with pool.acquire() as conn:
            if function_namespace:
                flows = await conn.fetch("""
                    SELECT * FROM function_flows 
                    WHERE function_namespace = $1
                    ORDER BY step_number
                """, function_namespace)
            else:
                flows = await conn.fetch("""
                    SELECT * FROM function_flows f
                    JOIN functions func ON f.function_namespace = func.function_namespace
                    WHERE func.project_id = $1
                    ORDER BY f.function_namespace, f.step_number
                """, project_id)
            
            return [dict(flow) for flow in flows]
    
    async def get_test_coverage(self, project_id: UUID) -> List[Dict[str, Any]]:
        """Get test coverage analysis for a project."""
        connection = self.db_manager.get_connection()
        pool = connection.get_pool()
        
        async with pool.acquire() as conn:
            coverage = await conn.fetch("""
                SELECT tc.* FROM test_coverage tc
                JOIN functions f ON tc.test_name = f.function_name
                WHERE f.project_id = $1
                ORDER BY tc.function_under_test, tc.test_scenario
            """, project_id)
            
            return [dict(test) for test in coverage]
    
    async def search_functions_by_context(self, project_id: UUID, context: str) -> List[Dict[str, Any]]:
        """Search functions by their context type."""
        connection = self.db_manager.get_connection()
        pool = connection.get_pool()
        
        async with pool.acquire() as conn:
            functions = await conn.fetch("""
                SELECT f.*, fa.description
                FROM functions f
                LEFT JOIN function_analysis fa ON f.id = fa.function_id
                WHERE f.project_id = $1 AND f.function_context = $2
                ORDER BY f.function_namespace
            """, project_id, context)
            
            return [dict(func) for func in functions]


# Global repository instance
documentation_repo = DocumentationRepository()