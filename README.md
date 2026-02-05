# Project Creator Core

Fast, opinionated scaffolder that creates ADHD Framework projects with uv workspace configuration. Clones preload modules as workspace members, enabling local dependency resolution without PyPI.

## Overview
- Creates new projects with **uv workspace** configuration
- Clones modules into layer-specific folders (`modules/foundation/`, `modules/runtime/`, `modules/dev/`)
- Generates `[tool.uv.sources]` with workspace references for ADHD modules
- Dependencies between ADHD modules resolve locally (no PyPI lookup required)
- Supports optional GitHub repo creation + initial push via shared creator helpers

## Features
- **uv Workspace Setup** – projects use workspace members pattern matching source framework
- **Module Installation** – clones modules from git, extracts metadata from `pyproject.toml`
- **Automatic Configuration** – generates dependencies and `[tool.uv.sources]` from installed modules
- **Remote repo automation** – uses Creator Common Core helpers to create/push to GitHub

## How It Works

When creating a project with preload modules:

1. **Clone modules** – Each module URL is cloned temporarily
2. **Extract metadata** – Reads `pyproject.toml` for package name, module type
3. **Install to workspace** – Moves module to `modules/foundation/`, `modules/runtime/`, or `modules/dev/` based on layer
4. **Generate pyproject.toml** – Creates workspace config with all modules as workspace sources
5. **Run uv sync** – Dependencies resolve locally between workspace members

The generated `pyproject.toml` structure:
\`\`\`toml
[project]
dependencies = [
    "argcomplete>=3.0",
    "mcp>=1.0",
    "logger-util",     # From installed modules
    "config-manager",
]

[tool.uv.workspace]
members = [
    "modules/foundation/*",
    "modules/runtime/*",
    "modules/dev/*",
]

[tool.uv.sources]
logger-util = { workspace = true }
config-manager = { workspace = true }
\`\`\`

## Quickstart

Programmatic creation:

\`\`\`python
from project_creator_core import ProjectCreator, ProjectParams
from creator_common_core import RepoCreationOptions

params = ProjectParams(
    repo_path="./demo_service",
    module_urls=[
        "https://github.com/AI-Driven-Highspeed-Development/Logger-Util.git",
        "https://github.com/AI-Driven-Highspeed-Development/Config-Manager.git",
    ],
    project_name="demo_service",
    description="A demo ADHD Framework project",
    repo_options=RepoCreationOptions(owner="my-org", visibility="private"),
)

creator = ProjectCreator(params)
project_dir = creator.create()  # Creates project with workspace-based modules
print(f"Project ready at {project_dir}")
\`\`\`

Interactive wizard:

\`\`\`python
from project_creator_core.project_creation_wizard import run_project_creation_wizard
from creator_common_core import QuestionaryCore
from logger_util import Logger

run_project_creation_wizard(
    prompter=QuestionaryCore(),
    logger=Logger("ProjectWizard"),
)
\`\`\`

## API

\`\`\`python
@dataclass
class ModuleMetadata:
    package_name: str  # e.g., "logger-util"
    module_type: str   # e.g., "util", "manager", "core"
    folder_name: str   # e.g., "logger_util"
    url: str           # Original git URL

@dataclass
class ProjectParams:
    repo_path: str
    module_urls: list[str]  # Git URLs for modules to install
    project_name: str
    description: str = ""
    repo_options: RepoCreationOptions | None = None

class ProjectCreator:
    def __init__(self, params: ProjectParams) -> None: ...
    def create(self) -> pathlib.Path: ...

def run_project_creation_wizard(*, prompter: QuestionaryCore, logger: Logger) -> None: ...

@dataclass
class PreloadSet:
    name: str
    description: str
    urls: list[str]

def parse_preload_sets(yaml: YamlFile) -> tuple[list[str], list[PreloadSet]]: ...
\`\`\`

## Module Layers

Modules are installed to directories based on `[tool.adhd].layer` in their `pyproject.toml`:

| Layer       | Target Directory      |
|-------------|----------------------|
| `foundation`| `modules/foundation/` |
| `runtime`   | `modules/runtime/`    |
| `dev`       | `modules/dev/`        |

## Notes
- Modules must have `[tool.adhd].layer` in their `pyproject.toml` for correct placement
- Unknown layers default to `modules/runtime/`
- The `.git` folder is removed from cloned modules (no nested git repos)

## Requirements & prerequisites
- GitHub CLI (\`gh\`) installed and authenticated
- \`git\` available on PATH
- \`uv\` package manager installed

## Troubleshooting
- **Module clone fails** – run \`gh auth status\` to confirm GitHub CLI auth
- **Wrong module directory** – check module's `[tool.adhd].layer` in `pyproject.toml`
- **uv sync fails** – ensure all modules have valid \`pyproject.toml\` with package names
- **Missing dependencies** – modules may need PyPI dependencies in their \`requirements.txt\`

## Module structure

\`\`\`
cores/project_creator_core/
├─ __init__.py                    # package marker / exports
├─ project_creator.py             # ProjectCreator + params
├─ project_creation_wizard.py     # interactive flow
├─ preload_sets.py                # parse preload definitions
├─ templates.py                   # legacy template listing helpers
├─ data/
│  ├─ templates/                  # embedded project templates
│  │  ├─ pyproject.toml.template
│  │  ├─ gitignore.template
│  │  └─ ...
│  └─ module_preload_sets.yaml    # default preload module sets
├─ init.yaml                      # module metadata
└─ README.md                      # this file
\`\`\`

## See also
- Creator Common Core – shared clone/repo helpers used by this module
- GitHub API Core – low-level gh wrapper
- Module Creator Core – complementary scaffolder for modules
- Questionary Core – provides the prompt UX used in the wizard
