"""
Utility functions for project management and output path calculation.
"""
from pathlib import Path
from typing import Union


def generate_project_identifier(project_root: Union[str, Path], target_language: str) -> str:
    """
    Generate deterministic project identifier: {project_name}-{target_language}
    
    Args:
        project_root: Path to project root directory
        target_language: Target programming language
        
    Returns:
        Project identifier string
    """
    project_name = Path(project_root).name
    return f"{project_name}-{target_language}"


def calculate_output_path(
    project_root: Union[str, Path], 
    target_language: str, 
    output_root: Union[str, Path] = "./translated"
) -> Path:
    """
    Calculate deterministic output path for translated code.
    
    Args:
        project_root: Path to source project root
        target_language: Target programming language
        output_root: Root directory for all translations
        
    Returns:
        Path to project-specific output directory
    """
    project_id = generate_project_identifier(project_root, target_language)
    return Path(output_root) / project_id