from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

import yaml

from cores.github_api_core.api import GithubApi


@dataclass
class RepoCreationOptions:
    owner: str
    visibility: str  # "public" or "private"


@dataclass
class ProjectParams:
    repo_path: str
    module_urls: List[str]
    project_name: str
    repo_options: Optional[RepoCreationOptions] = None


class ProjectCreator:
    """Create a project from a template and emit an init.yaml."""

    def __init__(self, params: ProjectParams) -> None:
        self.params = params

    def create(self, template_url: str) -> str:
        target = self._prepare_target_path()
        api = GithubApi()
        dest_path = self._clone_template(api, template_url, target)
        self._write_init_yaml(dest_path / "init.yaml")
        self._maybe_create_remote_repo(api, dest_path)
        return str(dest_path)

    def _prepare_target_path(self) -> Path:
        target = Path(self.params.repo_path).expanduser().resolve()
        target.parent.mkdir(parents=True, exist_ok=True)
        return target

    def _clone_template(self, api: GithubApi, template_url: str, target: Path) -> Path:
        repo = api.repo(template_url)
        dest = repo.clone_repo(str(target))
        if not dest:
            raise RuntimeError(f"Failed to clone template from {template_url} to {target}")
        dest_path = Path(dest).resolve()
        self._remove_git_dir(dest_path)
        return dest_path

    def _remove_git_dir(self, path: Path) -> None:
        """Remove the cloned template's .git directory."""
        git_dir = path / ".git"
        if git_dir.exists() and git_dir.is_dir():
            shutil.rmtree(git_dir)

    def _write_init_yaml(self, init_path: Path) -> None:
        init_data = {
            "name": self.params.project_name,
            "description": "",
            "modules": list(self.params.module_urls),
        }
        with open(init_path, "w", encoding="utf-8") as handle:
            yaml.safe_dump(init_data, handle, allow_unicode=True, sort_keys=False)

    def _maybe_create_remote_repo(self, api: GithubApi, dest: Path) -> None:
        options = self.params.repo_options
        if not options:
            return

        repo_name = self._determine_repo_name(dest)
        name_with_owner = f"{options.owner}/{repo_name}"
        is_private = options.visibility.lower() == "private"
        if not api.create_repo(name_with_owner, private=is_private):
            raise RuntimeError(f"Failed to create remote repository {name_with_owner}")
        api.push_initial_commit(dest, name_with_owner, branch="main", message="init commit")

    def _determine_repo_name(self, dest: Path) -> str:
        name = dest.name.strip()
        if not name:
            raise ValueError("Unable to determine repository name from destination path")
        return name.replace(" ", "-")


__all__ = ["ProjectCreator", "ProjectParams", "RepoCreationOptions"]