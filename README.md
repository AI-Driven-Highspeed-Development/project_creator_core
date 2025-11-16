# Project Creator Core

Fast, opinionated scaffolder that clones a project template, wires preload modules, and optionally bootstraps a GitHub repository.

## Overview
- Normalizes project names and destinations through the interactive wizard
- Clones project templates via `gh repo clone`, stripping template git metadata
- Writes `init.yaml` with preload modules so downstream automation can hydrate dependencies
- Supports optional GitHub repo creation + initial push via shared creator helpers
- Offers scriptable `ProjectCreator` for non-interactive flows

## Features
- **Interactive wizard** – prompts for name, destination, template, preload sets, and repo ownership
- **Template + preload management** – parses template catalogs and module preload sets from YAML
- **Remote repo automation** – uses Creator Common Core helpers to create/push to GitHub
- **Init manifest emitting** – records project metadata to `init.yaml` for further tooling

## Quickstart

Programmatic creation:

```python
from cores.project_creator_core.project_creator import ProjectCreator, ProjectParams
from cores.creator_common_core.creator_common_core import RepoCreationOptions

params = ProjectParams(
	repo_path="./demo_service",
	module_urls=["https://github.com/org/auth"],
	project_name="demo_service",
	repo_options=RepoCreationOptions(owner="my-org", visibility="private"),
)

creator = ProjectCreator(params)
project_dir = creator.create("https://github.com/org/templates/python-service")
print(f"Project ready at {project_dir}")
```

Interactive wizard:

```python
from cores.project_creator_core.project_creation_wizard import run_project_creation_wizard
from cores.questionary_core.questionary_core import QuestionaryCore
from utils.logger_util.logger import Logger

run_project_creation_wizard(
	prompter=QuestionaryCore(),
	logger=Logger("ProjectWizard"),
)
```

## API

```python
@dataclass
class ProjectParams:
	repo_path: str
	module_urls: list[str]
	project_name: str
	repo_options: RepoCreationOptions | None = None

class ProjectCreator:
	def __init__(self, params: ProjectParams) -> None: ...
	def create(self, template_url: str) -> pathlib.Path: ...

def run_project_creation_wizard(*, prompter: QuestionaryCore, logger: Logger) -> None: ...

@dataclass
class TemplateInfo:
	name: str
	description: str
	url: str

def list_project_templates(yaml: YamlFile) -> list[TemplateInfo]: ...

@dataclass
class PreloadSet:
	name: str
	description: str
	urls: list[str]

def parse_preload_sets(yaml: YamlFile) -> tuple[list[str], list[PreloadSet]]: ...
```

## Notes
- `ProjectCreator` strips the template’s `.git` folder so your repo starts clean.
- The wizard loads template/preload YAML paths from `main_config.path.*`; keep those files up to date.
- Repo creation relies on GitHub CLI auth; the wizard falls back gracefully when `gh` is unavailable.

## Requirements & prerequisites
- GitHub CLI (`gh`) installed and authenticated
- `git` available on PATH
- Python dependency: `pyyaml`

## Troubleshooting
- **“No project templates found”** – verify the YAML at `main_config.path.project_templates` exists and follows the `{name: {description,url}}` schema.
- **Clone fails with `gh` error** – run `gh auth status` to confirm you’re logged in and have repo access.
- **Preload selection missing entries** – ensure `module_preload_sets` YAML defines `always` and `options` keys with URL lists.
- **Remote repo creation skipped** – the wizard only offers repo creation when GitHub CLI auth succeeds; check logs for details.

## Module structure

```
cores/project_creator_core/
├─ __init__.py                    # package marker / exports
├─ project_creator.py             # ProjectCreator + params
├─ project_creation_wizard.py     # interactive flow
├─ preload_sets.py                # parse preload definitions
├─ templates.py                   # legacy template listing helpers
├─ init.yaml                      # module metadata
└─ README.md                      # this file
```

## See also
- Creator Common Core – shared clone/repo helpers used by this module
- GitHub API Core – low-level gh wrapper
- Module Creator Core – complementary scaffolder for modules
- Questionary Core – provides the prompt UX used in the wizard