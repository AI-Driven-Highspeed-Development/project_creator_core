from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List
import shutil

import yaml

from cores.github_api_core.api import GithubApi


@dataclass
class ProjectParams:
    repo_path: str
    module_urls: List[str]
    project_name: str


class ProjectCreator:
    """Create a project from a template and emit an init.yaml.

    Steps:
    - Clone the project template into the target repo_path
    - Write init.yaml in the new project's root with name, description, and modules (list of URLs)
    """

    def __init__(self, params: ProjectParams) -> None:
        self.params = params

    def create(self, template_url: str) -> str:
        target = Path(self.params.repo_path).expanduser().resolve()
        target.parent.mkdir(parents=True, exist_ok=True)
        api = GithubApi()
        repo = api.repo(template_url)
        dest = repo.clone_repo(str(target))
        if not dest:
            raise RuntimeError(f"Failed to clone template from {template_url} to {target}")

        # Remove .git directory from the cloned template
        self._remove_git_dir(Path(dest))

        # Emit init.yaml
        self._write_init_yaml(Path(dest) / "init.yaml")

        return str(dest)
    
    
    def _remove_git_dir(self, path: Path) -> None:
        """Remove .git directory if it exists because we don't want to actually use the template's git history"""  
        git_dir = path / ".git"
        if git_dir.exists() and git_dir.is_dir():
            shutil.rmtree(git_dir)

    def _write_init_yaml(self, init_path: Path) -> None:
        init_data = {
            "name": self.params.project_name,
            "description": "",
            "modules": list(self.params.module_urls),
        }
        with open(init_path, "w", encoding="utf-8") as f:
            yaml.safe_dump(init_data, f, allow_unicode=True, sort_keys=False)

__all__ = ["ProjectCreator", "ProjectParams"]