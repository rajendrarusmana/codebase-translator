-- PostgreSQL Schema for Codebase Translation Project Management
-- Clean, simplified schema without documentation tables

-- Enable UUID generation
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- Drop old documentation tables if they exist
DROP TABLE IF EXISTS function_module_calls CASCADE;
DROP TABLE IF EXISTS function_side_effects CASCADE;
DROP TABLE IF EXISTS function_operations CASCADE;
DROP TABLE IF EXISTS function_outputs CASCADE;
DROP TABLE IF EXISTS function_inputs CASCADE;

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

-- Projects table (based on ProjectSpecification)
CREATE TABLE IF NOT EXISTS projects (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_name VARCHAR(255) NOT NULL,
    root_path TEXT NOT NULL,
    project_type VARCHAR(50) NOT NULL, -- From ProjectType enum
    architecture_pattern VARCHAR(50) NOT NULL, -- From ArchitecturePattern enum
    primary_language VARCHAR(50) NOT NULL,
    languages_used TEXT[], -- Array from current collection
    total_files INTEGER DEFAULT 0,
    entry_points TEXT[], -- Array of entry point files
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    created_by UUID, -- User who created the project
    workflow_id TEXT, -- Links to checkpoint system
    UNIQUE(project_name, root_path)
);

CREATE INDEX IF NOT EXISTS idx_projects_name ON projects(project_name);
CREATE INDEX IF NOT EXISTS idx_projects_language ON projects(primary_language);
CREATE INDEX IF NOT EXISTS idx_projects_type ON projects(project_type);

-- Folders table (based on FolderSpecification)
CREATE TABLE IF NOT EXISTS folders (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID, -- Project this folder belongs to
    folder_path TEXT NOT NULL,
    folder_name VARCHAR(255) NOT NULL,
    folder_purpose VARCHAR(50) NOT NULL, -- From FolderPurpose enum
    description TEXT, -- From LLM analysis
    confidence DECIMAL(3,2), -- From LLM analysis
    parent_folder_id UUID, -- Parent folder (if any)
    file_count INTEGER DEFAULT 0,
    UNIQUE(project_id, folder_path)
);

CREATE INDEX IF NOT EXISTS idx_folders_project ON folders(project_id);
CREATE INDEX IF NOT EXISTS idx_folders_parent ON folders(parent_folder_id);
CREATE INDEX IF NOT EXISTS idx_folders_purpose ON folders(folder_purpose);

-- Files table (based on file_classifications data)
CREATE TABLE IF NOT EXISTS files (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID, -- Project this file belongs to
    folder_id UUID, -- Folder containing this file
    file_path TEXT NOT NULL,
    file_type VARCHAR(50) NOT NULL, -- From FileType enum (logic, data, test, etc.)
    classification_confidence DECIMAL(3,2),
    UNIQUE(project_id, file_path)
);

CREATE INDEX IF NOT EXISTS idx_files_project ON files(project_id);
CREATE INDEX IF NOT EXISTS idx_files_folder ON files(folder_id);
CREATE INDEX IF NOT EXISTS idx_files_type ON files(file_type);

-- Functions table with context-specific fields
CREATE TABLE IF NOT EXISTS functions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID, -- Project this function belongs to
    file_id UUID, -- File containing this function
    function_name VARCHAR(255) NOT NULL,
    function_namespace TEXT NOT NULL,
    parent_class VARCHAR(255),
    signature TEXT,
    start_line INTEGER,
    end_line INTEGER,
    is_async BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    -- LLM-detected context and specialized fields
    function_context VARCHAR(50), -- handler, repository, service, utility, component, test, etc.
    
    -- Handler/Controller context (if detected)
    http_method VARCHAR(10),
    endpoint_path TEXT,
    status_codes INTEGER[],
    
    -- Repository/Data Access context (if detected)
    sql_operation VARCHAR(20),
    primary_table VARCHAR(100),
    sql_example TEXT,
    database_type VARCHAR(50),
    
    -- Service/Business Logic context (if detected)
    business_domain VARCHAR(100),
    transaction_type VARCHAR(50),
    external_dependencies TEXT[],
    
    -- Component/UI context (if detected)
    component_type VARCHAR(50),
    ui_framework VARCHAR(50),
    
    -- Background Job context (if detected)
    job_queue VARCHAR(50),
    schedule_pattern VARCHAR(100),
    
    -- Enhanced Test context (if detected)
    test_type VARCHAR(50), -- unit, integration, e2e, performance, security
    test_framework VARCHAR(50), -- pytest, jest, junit, mocha, etc.
    test_case_description TEXT, -- What specific behavior is being tested
    test_scenario VARCHAR(100), -- happy_path, edge_case, error_condition, boundary_condition
    function_under_test VARCHAR(255), -- The actual function being tested
    test_assertion_type VARCHAR(50), -- equality, exception, behavior, state_change, side_effect
    expected_outcome TEXT, -- What the test expects to happen
    test_setup_required TEXT, -- Any special setup needed for the test
    mock_dependencies TEXT[], -- What dependencies are mocked/stubbed
    
    -- Utility context (if detected)
    utility_category VARCHAR(50),
    input_constraints TEXT,
    output_guarantees TEXT,
    
    UNIQUE(project_id, file_id, function_name, parent_class)
);

-- Indexes for function queries
CREATE INDEX IF NOT EXISTS idx_function_namespace ON functions(function_namespace);
CREATE INDEX IF NOT EXISTS idx_function_context ON functions(function_context);
CREATE INDEX IF NOT EXISTS idx_function_http_method ON functions(http_method) WHERE http_method IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_function_endpoint ON functions(endpoint_path) WHERE endpoint_path IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_function_sql_op ON functions(sql_operation) WHERE sql_operation IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_function_business_domain ON functions(business_domain) WHERE business_domain IS NOT NULL;

-- Additional indexes for test function queries
CREATE INDEX IF NOT EXISTS idx_function_under_test ON functions(function_under_test) WHERE function_under_test IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_test_scenario ON functions(test_scenario) WHERE test_scenario IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_test_assertion ON functions(test_assertion_type) WHERE test_assertion_type IS NOT NULL;

-- Function analysis table (based on function_specs from LLM)
CREATE TABLE IF NOT EXISTS function_analysis (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    function_id UUID UNIQUE, -- Function this analysis belongs to
    description TEXT, -- From LLM analysis
    analysis_method VARCHAR(50), -- 'pure_llm_semantic', 'retry'
    retry_reason TEXT, -- If retry was needed
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_function_analysis_function ON function_analysis(function_id);

-- View for complete project documentation
CREATE OR REPLACE VIEW project_documentation AS
SELECT 
    p.id as project_id,
    p.project_name,
    p.project_type,
    p.architecture_pattern,
    p.primary_language,
    p.languages_used,
    COUNT(DISTINCT f.id) as total_functions,
    COUNT(DISTINCT files.id) as total_files,
    COUNT(DISTINCT folders.id) as total_folders,
    COUNT(DISTINCT f.id) FILTER (WHERE f.function_context = 'handler') as handler_functions,
    COUNT(DISTINCT f.id) FILTER (WHERE f.function_context = 'repository') as repository_functions,
    COUNT(DISTINCT f.id) FILTER (WHERE f.function_context = 'service') as service_functions,
    COUNT(DISTINCT f.id) FILTER (WHERE f.function_context = 'test') as test_functions,
    COUNT(DISTINCT f.id) FILTER (WHERE f.function_context = 'utility') as utility_functions
FROM projects p
LEFT JOIN files ON p.id = files.project_id
LEFT JOIN folders ON p.id = folders.project_id  
LEFT JOIN functions f ON p.id = f.project_id
GROUP BY p.id, p.project_name, p.project_type, p.architecture_pattern, 
         p.primary_language, p.languages_used;

-- View for function flow analysis
CREATE OR REPLACE VIEW function_flows AS
SELECT 
    f.function_namespace,
    f.function_context,
    f.signature,
    fo.step_number,
    fo.operation_description,
    fo.data_flow,
    fo.control_flow,
    fo.conditions,
    se.side_effect_type,
    se.description as side_effect_desc,
    se.scope as side_effect_scope,
    mc.target_module || '.' || mc.target_function as calls_function,
    mc.call_type
FROM functions f
LEFT JOIN function_operations fo ON f.id = fo.function_id
LEFT JOIN function_side_effects se ON f.id = se.function_id 
    AND se.side_effect_id = ANY(fo.side_effect_ids)
LEFT JOIN function_module_calls mc ON f.id = mc.function_id;

-- View for test coverage analysis
CREATE OR REPLACE VIEW test_coverage AS
SELECT 
    test_func.function_under_test,
    main_func.function_context as target_function_type,
    test_func.function_name as test_name,
    test_func.test_case_description,
    test_func.test_scenario,
    test_func.test_assertion_type,
    test_func.expected_outcome,
    test_func.mock_dependencies
FROM functions test_func
LEFT JOIN functions main_func ON test_func.function_under_test = main_func.function_name
WHERE test_func.function_context = 'test'
  AND test_func.function_under_test IS NOT NULL;