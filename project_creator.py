from __future__ import annotations
import os
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

import yaml

from github_api_core import GithubApi
import subprocess

from exceptions_core import ADHDError
from creator_common_core import (
    RepoCreationOptions,
    create_remote_repo,
)
from logger_util import Logger


# ============================================================================
# TEMPLATE LOADING
# Templates are loaded from data/templates/ directory
# ============================================================================

TEMPLATES_DIR = Path(__file__).parent / "data" / "templates"

# Path to the framework's adhd_framework.py - used for direct copy to new projects
# This resolves to the actual framework root, not a template
FRAMEWORK_ROOT = Path(__file__).parent.parent.parent
ADHD_FRAMEWORK_FILE = FRAMEWORK_ROOT / "adhd_framework.py"


def _load_template(name: str) -> str:
    """Load a template file from the templates directory."""
    template_path = TEMPLATES_DIR / name
    if not template_path.exists():
        raise ADHDError(f"Template not found: {template_path}")
    return template_path.read_text(encoding="utf-8")


# Standard project directories to create
PROJECT_DIRECTORIES = [
    "cores",
    "managers",
    "utils",
    "plugins",
    "mcps",
    "project/data",
    "tests",
]


@dataclass
class ProjectParams:
    repo_path: str
    module_urls: List[str]  # Git URLs for modules to install (from preload sets)
    project_name: str
    description: str = ""  # Optional project description
    repo_options: Optional[RepoCreationOptions] = None


class ProjectCreator:
    """Create a new ADHD Framework project from embedded templates.
    
    No longer clones external templates - all content is generated from
    embedded Python string constants.
    """

    def __init__(self, params: ProjectParams) -> None:
        self.params = params
        self.logger = Logger(name=__class__.__name__)

    def create(self) -> Path:
        """Create a new project with embedded templates.
        
        Returns:
            Path to the created project directory.
        """
        dest_path = self._prepare_target_path()
        
        # Create project structure from embedded templates
        self._create_directories(dest_path)
        self._write_pyproject_toml(dest_path)
        self._write_gitignore(dest_path)
        self._write_readme(dest_path)
        self._write_app_entry(dest_path)
        self._write_tests_init(dest_path)
        self._write_project_init(dest_path)
        self._copy_adhd_framework(dest_path)
        
        # Initialize with UV
        self._run_uv_sync(dest_path)
        
        # Install preloaded modules from git URLs
        if self.params.module_urls:
            self._install_preload_modules(dest_path)

        # Create remote repo if requested
        if self.params.repo_options:
            api = GithubApi()
            create_remote_repo(
                api=api,
                repo_name=self.params.project_name,
                local_path=dest_path,
                options=self.params.repo_options,
                logger=self.logger,
            )
        
        return dest_path

    # DEPRECATED_P3: Old template-based creation - use create() instead
    def create_from_template(self, template_url: str) -> Path:
        """DEPRECATED: Create project by cloning external template.
        
        This method is deprecated. Use create() instead which uses embedded templates.
        """
        from creator_common_core import clone_template
        target = self._prepare_target_path()
        api = GithubApi()
        dest_path = clone_template(api, template_url, target)
        self._write_pyproject_toml(dest_path)
        self._run_uv_sync(dest_path)

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
        target.mkdir(parents=True, exist_ok=True)
        return target

    # ---------------- File Generation ----------------

    def _create_directories(self, project_path: Path) -> None:
        """Create standard project directory structure."""
        for dir_name in PROJECT_DIRECTORIES:
            dir_path = project_path / dir_name
            dir_path.mkdir(parents=True, exist_ok=True)
        self.logger.info(f"Created project directories in {project_path}")

    def _write_pyproject_toml(self, project_path: Path) -> None:
        """Generate pyproject.toml for new project."""
        template = _load_template("pyproject.toml.template")
        content = template.format(
            project_name=self.params.project_name,
            description=self.params.description or ""
        )
        (project_path / "pyproject.toml").write_text(content, encoding="utf-8")
        self.logger.info(f"Wrote pyproject.toml at {project_path / 'pyproject.toml'}")

    def _write_gitignore(self, project_path: Path) -> None:
        """Generate .gitignore for new project."""
        template = _load_template("gitignore.template")
        (project_path / ".gitignore").write_text(template, encoding="utf-8")
        self.logger.info(f"Wrote .gitignore at {project_path / '.gitignore'}")

    def _write_readme(self, project_path: Path) -> None:
        """Generate README.md for new project."""
        template = _load_template("readme.md.template")
        content = template.format(project_name=self.params.project_name)
        (project_path / "README.md").write_text(content, encoding="utf-8")
        self.logger.info(f"Wrote README.md at {project_path / 'README.md'}")

    def _write_app_entry(self, project_path: Path) -> None:
        """Generate application entry point file."""
        template = _load_template("app.py.template")
        content = template.format(project_name=self.params.project_name)
        (project_path / "app.py").write_text(content, encoding="utf-8")
        self.logger.info(f"Wrote app.py at {project_path / 'app.py'}")

    def _write_tests_init(self, project_path: Path) -> None:
        """Generate tests/__init__.py."""
        tests_init = project_path / "tests" / "__init__.py"
        tests_init.write_text('"""Test suite for the project."""\n', encoding="utf-8")
        self.logger.info(f"Wrote tests/__init__.py")

    def _write_project_init(self, project_path: Path) -> None:
        """Generate project/__init__.py."""
        project_init = project_path / "project" / "__init__.py"
        project_init.write_text('"""Project-specific data and configuration."""\n', encoding="utf-8")
        self.logger.info(f"Wrote project/__init__.py")

    def _copy_adhd_framework(self, project_path: Path) -> None:
        """Copy the actual adhd_framework.py from the framework to the new project.
        
        This copies the real framework CLI file (not a template) to enable
        the 'adhd' command in the new project.
        """
        if not ADHD_FRAMEWORK_FILE.exists():
            raise ADHDError(
                f"Framework file not found: {ADHD_FRAMEWORK_FILE}. "
                "Cannot copy adhd_framework.py to new project."
            )
        
        dest_file = project_path / "adhd_framework.py"
        shutil.copy2(ADHD_FRAMEWORK_FILE, dest_file)
        self.logger.info(f"Copied adhd_framework.py to {dest_file}")

    def _run_uv_sync(self, project_path: Path) -> None:
        """Run uv sync to initialize project dependencies."""
        self.logger.info("Running uv sync to initialize project")
        result = subprocess.run(
            ["uv", "sync"],
            cwd=project_path,
            capture_output=True,
            text=True,
            timeout=60
        )
        if result.returncode != 0:
            raise ADHDError(f"uv sync failed: {result.stderr}") from None
        self.logger.info("uv sync completed successfully")

    def _install_preload_modules(self, project_path: Path) -> None:
        """Install preloaded modules from git URLs using uv add.
        
        Each module URL is a git repository that gets added as a dependency.
        Reports a summary of successes and failures at the end.
        """
        self.logger.info(f"Installing {len(self.params.module_urls)} preloaded modules...")
        
        successes: List[str] = []
        failures: List[tuple[str, str]] = []  # (url, error_message)
        
        for url in self.params.module_urls:
            self.logger.info(f"Adding module: {url}")
            result = subprocess.run(
                ["uv", "add", f"git+{url}"],
                cwd=project_path,
                capture_output=True,
                text=True,
                timeout=120  # Longer timeout for git clones
            )
            if result.returncode != 0:
                # Log full stderr for visibility - don't swallow the error details
                error_msg = result.stderr.strip() if result.stderr else "Unknown error"
                self.logger.error(f"FAILED to add module: {url}")
                self.logger.error(f"  Error details: {error_msg}")
                if result.stdout:
                    self.logger.error(f"  stdout: {result.stdout.strip()}")
                failures.append((url, error_msg))
                # Continue with other modules instead of failing completely
            else:
                self.logger.info(f"Successfully added module: {url}")
                successes.append(url)
        
        # Report summary
        self.logger.info("=" * 60)
        self.logger.info("PRELOAD MODULES INSTALLATION SUMMARY")
        self.logger.info("=" * 60)
        self.logger.info(f"  Successes: {len(successes)}/{len(self.params.module_urls)}")
        self.logger.info(f"  Failures:  {len(failures)}/{len(self.params.module_urls)}")
        
        if successes:
            self.logger.info("  Installed successfully:")
            for url in successes:
                self.logger.info(f"    ✓ {url}")
        
        if failures:
            self.logger.warning("  FAILED to install:")
            for url, error in failures:
                self.logger.warning(f"    ✗ {url}")
                self.logger.warning(f"      Reason: {error[:200]}...")  # Truncate long errors
        
        self.logger.info("=" * 60)
        
        if failures:
            self.logger.warning(
                f"WARNING: {len(failures)} module(s) failed to install. "
                "The project was created but may be missing dependencies. "
                "You may need to manually run 'uv add git+<url>' for failed modules."
            )


__all__ = ["ProjectCreator", "ProjectParams", "RepoCreationOptions"]