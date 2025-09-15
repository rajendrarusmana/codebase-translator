# Simplified Project Management System Design

## Core Requirements

1. **Deterministic folder structure**: `{{output-root}}/{{project-name}}-{{target-language}}`
2. **Database tracking**: Keep record of all translation projects
3. **No custom project IDs**: Fully deterministic naming
4. **Simple configuration**: Just `output_root` parameter

## Implementation

### 1. Project Identifier Generation

```python
def generate_project_identifier(project_root: str, target_language: str) -> str:
    """Generate deterministic project identifier: {project_name}-{target_language}"""
    project_name = Path(project_root).name
    return f"{project_name}-{target_language}"
```

### 2. Output Path Calculation

```python
def calculate_output_path(project_root: str, target_language: str, output_root: str = "./translated") -> Path:
    """Calculate deterministic output path"""
    project_id = generate_project_identifier(project_root, target_language)
    return Path(output_root) / project_id
```

### 3. Database Tracking

Add to PostgreSQL schema:
```sql
CREATE TABLE translation_projects (
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
```

### 4. CLI Interface

Keep it simple:
```bash
# Same as before, but with organized output
translator /path/to/order-service go
# Output: ./translated/order-service-go/

# Custom output root
translator /path/to/order-service go --output-root /path/to/my-translations  
# Output: /path/to/my-translations/order-service-go/
```

## Key Benefits

1. **Organized**: Each translation in its own folder
2. **Trackable**: Database records all projects
3. **Predictable**: Deterministic naming convention
4. **Simple**: Minimal configuration needed
5. **Discoverable**: Easy to find previous translations