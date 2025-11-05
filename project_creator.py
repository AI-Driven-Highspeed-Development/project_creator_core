from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List

import yaml

from cores.github_api_core import GithubApi


@dataclass
class ProjectParams:
    repo_path: str
    module_urls: List[str]
    project_name: str
    module_type: str


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

        api = GithubApi(template_url)
        dest = api.pull_repo(str(target))
        if not dest:
            raise RuntimeError(f"Failed to clone template from {template_url} to {target}")

        # Emit init.yaml
        init_data = {
            "name": self.params.project_name,
            "description": "",
            "modules": list(self.params.module_urls),
        }
        init_path = Path(dest) / "init.yaml"
        with open(init_path, "w", encoding="utf-8") as f:
            yaml.safe_dump(init_data, f, allow_unicode=True, sort_keys=False)

        return str(dest)


__all__ = ["ProjectCreator", "ProjectParams"]