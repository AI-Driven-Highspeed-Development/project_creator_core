from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

import yaml

from cores.github_api_core.api import GithubApi
from cores.creator_common_core.creator_common_core import (
    RepoCreationOptions,
    clone_template,
    create_remote_repo,
)
from utils.logger_util.logger import Logger


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
        self.logger = Logger(name=__class__.__name__)

    def create(self, template_url: str) -> Path:
        target = self._prepare_target_path()
        api = GithubApi()
        dest_path = clone_template(api, template_url, target)
        self._write_init_yaml(dest_path / "init.yaml")

        if self.params.repo_options:
            create_remote_repo(
                api=api,
                repo_name=self.params.project_name,
                local_path=dest_path,
                options=self.params.repo_options,
                logger=self.logger,
            )
        return dest_path

    def _prepare_target_path(self) -> Path:
        target = Path(self.params.repo_path).expanduser().resolve()
        target.parent.mkdir(parents=True, exist_ok=True)
        return target

    # ---------------- Internal helpers ----------------

    def _write_init_yaml(self, init_path: Path) -> None:
        init_data = {
            "name": self.params.project_name,
            "description": "",
            "modules": list(self.params.module_urls),
        }
        with open(init_path, "w", encoding="utf-8") as handle:
            yaml.safe_dump(init_data, handle, allow_unicode=True, sort_keys=False)


__all__ = ["ProjectCreator", "ProjectParams", "RepoCreationOptions"]