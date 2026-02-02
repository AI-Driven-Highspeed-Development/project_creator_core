"""project_creator_core - Project creation and scaffolding.

Provides ProjectCreator for creating new ADHD Framework projects.
"""

from __future__ import annotations
from pathlib import Path
import shutil
from functools import lru_cache

PRELOAD_TEMPLATE_PATH = "data/module_preload_sets.yaml"
TEMPLATE_PATH = "data/project_templates.yaml"


def _get_dest_dir() -> Path:
    """Get the destination directory for template files, creating if needed."""
    dest_dir = Path("./project/data/project_creator_core")
    dest_dir.mkdir(parents=True, exist_ok=True)
    return dest_dir


def ensure_file(template_path: str) -> Path:
    """Ensure a template file is copied to the project data directory.
    
    This is called lazily when templates are actually needed, not on import.
    """
    from logger_util import Logger
    logger = Logger(name="ProjectCreatorInit")
    
    dest_dir = _get_dest_dir()
    dest_file_name = Path(template_path).name
    dest_path = dest_dir / dest_file_name

    src = Path(__file__).parent / template_path
    if not src.exists():
        raise FileNotFoundError(f"Bundled template not found: {src}")
    try:
        shutil.copyfile(src, dest_path)
    except Exception as e:
        raise IOError(f"Failed to copy template to {dest_path}: {e}") from e
    logger.info(f"{template_path} ensured at: {dest_path}")
    return dest_path


@lru_cache(maxsize=1)
def ensure_templates() -> None:
    """Ensure all template files are copied. Called lazily, not on import."""
    ensure_file(PRELOAD_TEMPLATE_PATH)
    ensure_file(TEMPLATE_PATH)


from .project_creator import ProjectCreator, ProjectParams

__all__ = ["ProjectCreator", "ProjectParams", "ensure_templates"]