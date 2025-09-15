-- PostgreSQL Schema for Codebase Translation Project Management
-- Minimal schema with only essential tables

-- Enable UUID generation
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- Drop old documentation tables if they exist
DROP TABLE IF EXISTS users CASCADE;
DROP TABLE IF EXISTS function_module_calls CASCADE;
DROP TABLE IF EXISTS function_side_effects CASCADE;
DROP TABLE IF EXISTS function_operations CASCADE;
DROP TABLE IF EXISTS function_outputs CASCADE;
DROP TABLE IF EXISTS function_inputs CASCADE;
DROP TABLE IF EXISTS function_analysis CASCADE;
DROP TABLE IF EXISTS functions CASCADE;
DROP TABLE IF EXISTS files CASCADE;
DROP TABLE IF EXISTS folders CASCADE;
DROP TABLE IF EXISTS projects CASCADE;

-- Translation Projects table for tracking active translations
CREATE TABLE IF NOT EXISTS translation_projects (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_name VARCHAR(255) NOT NULL,
    project_root TEXT NOT NULL,
    target_language VARCHAR(50) NOT NULL,
    output_path TEXT NOT NULL,
    status VARCHAR(50) DEFAULT 'started', -- started, analyzing, translating, completed, failed
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP WITH TIME ZONE,
    UNIQUE(project_name, target_language)
);

CREATE INDEX IF NOT EXISTS idx_translation_projects_name ON translation_projects(project_name);
CREATE INDEX IF NOT EXISTS idx_translation_projects_status ON translation_projects(status);
CREATE INDEX IF NOT EXISTS idx_translation_projects_created ON translation_projects(created_at);

-- Module Specifications table for storing translation specifications
CREATE TABLE IF NOT EXISTS module_specifications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES translation_projects(id) ON DELETE CASCADE,
    module_name VARCHAR(255) NOT NULL,
    file_path TEXT NOT NULL,
    original_language VARCHAR(50) NOT NULL,
    module_type VARCHAR(50) NOT NULL,
    description TEXT,
    specification_data JSONB NOT NULL, -- Complete module specification as JSON
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_module_specifications_project ON module_specifications(project_id);
CREATE INDEX IF NOT EXISTS idx_module_specifications_module ON module_specifications(module_name);