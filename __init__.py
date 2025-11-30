from __future__ import annotations
from pathlib import Path
import shutil
import os
import sys

# Add path handling to work from the new nested directory structure
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.getcwd()  # Use current working directory as project root
sys.path.insert(0, project_root)

PRELOAD_TEMPLATE_PATH = "data/module_preload_sets.yaml"

TEMPLATE_PATH = "data/project_templates.yaml"

from utils.logger_util.logger import Logger
logger = Logger(name="ProjectCreatorInit")

dest_dir = Path("./project/data/project_creator_core")
if dest_dir.exists():
    shutil.rmtree(dest_dir)
dest_dir.mkdir(parents=True, exist_ok=True)

def ensure_file(template_path: str) -> Path:
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


ensure_file(PRELOAD_TEMPLATE_PATH)
ensure_file(TEMPLATE_PATH)