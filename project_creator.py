from __future__ import annotations
import os
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional
import subprocess
import tomllib

from github_api_core import GithubApi

from exceptions_core import ADHDError
from creator_common_core import (
    RepoCreationOptions,
    create_remote_repo,
    remove_git_dir,
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

# Mapping of module types to their workspace directories
MODULE_TYPE_TO_DIR = {
    "core": "cores",
    "manager": "managers",
    "util": "utils",
    "plugin": "plugins",
    "mcp": "mcps",
}


def _load_template(name: str) -> str:
    """Load a template file from the templates directory."""
    template_path = TEMPLATES_DIR / name
    if not template_path.exists():
        raise ADHDError(f"Template not found: {template_path}")
    return template_path.read_text(encoding="utf-8")


@dataclass
class ModuleMetadata:
    """Metadata extracted from a module's pyproject.toml."""
    package_name: str  # e.g., "logger-util"
    module_type: str   # e.g., "util", "manager", "core"
    folder_name: str   # e.g., "logger_util" (the directory name)
    url: str           # Original git URL


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
    
    Uses uv workspace approach where modules are cloned as local workspace
    members rather than installed via git+<url>. This enables local dependency
    resolution without requiring PyPI.
    """

    def __init__(self, params: ProjectParams) -> None:
        self.params = params
        self.logger = Logger(name=__class__.__name__)
        self._installed_modules: List[ModuleMetadata] = []

    def create(self) -> Path:
        """Create a new project with embedded templates.
        
        Returns:
            Path to the created project directory.
        """
        dest_path = self._prepare_target_path()
        
        # Create project structure from embedded templates
        self._create_directories(dest_path)
        self._write_gitignore(dest_path)
        self._write_readme(dest_path)
        self._write_app_entry(dest_path)
        self._write_tests_init(dest_path)
        self._write_project_init(dest_path)
        self._copy_adhd_framework(dest_path)
        
        # Install preloaded modules as workspace members (cloning into folders)
        if self.params.module_urls:
            self._install_preload_modules(dest_path)
        
        # Write pyproject.toml AFTER modules are installed so we can include
        # workspace sources for all installed modules
        self._write_pyproject_toml(dest_path)
        
        # Initialize with UV - now that workspace is configured
        self._run_uv_sync(dest_path)

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
        """Generate pyproject.toml for new project with workspace configuration.
        
        Includes:
        - Standard project metadata
        - [tool.uv.workspace] members for all module directories
        - [tool.uv.sources] for all installed ADHD modules as workspace = true
        - Dependencies list referencing all installed modules
        """
        template = _load_template("pyproject.toml.template")
        
        # Build dependencies list from installed modules
        dependencies_lines = []
        for mod in self._installed_modules:
            dependencies_lines.append(f'    "{mod.package_name}",')
        dependencies_str = "\n".join(dependencies_lines)
        
        # Build [tool.uv.sources] section
        uv_sources_lines = []
        if self._installed_modules:
            uv_sources_lines.append("[tool.uv.sources]")
            uv_sources_lines.append("# ADHD module dependencies - resolved as workspace members")
            for mod in sorted(self._installed_modules, key=lambda m: m.package_name):
                uv_sources_lines.append(f'{mod.package_name} = {{ workspace = true }}')
        uv_sources_str = "\n".join(uv_sources_lines)
        
        content = template.format(
            project_name=self.params.project_name,
            description=self.params.description or "",
            dependencies=dependencies_str,
            uv_sources=uv_sources_str,
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
        # Create clean environment - remove VIRTUAL_ENV to prevent conflicts
        # with parent shell's venv
        clean_env = os.environ.copy()
        clean_env.pop("VIRTUAL_ENV", None)
        result = subprocess.run(
            ["uv", "sync"],
            cwd=project_path,
            capture_output=True,
            text=True,
            timeout=60,
            env=clean_env
        )
        if result.returncode != 0:
            raise ADHDError(f"uv sync failed: {result.stderr}") from None
        self.logger.info("uv sync completed successfully")

    def _install_preload_modules(self, project_path: Path) -> None:
        """Install preloaded modules as workspace members by cloning into appropriate folders.
        
        Uses uv workspace approach:
        1. Clone each module into its type-specific folder (cores/, managers/, utils/, etc.)
        2. Extract module metadata (package name, type) from the cloned pyproject.toml
        3. Module metadata is stored for later pyproject.toml generation
        
        This enables local dependency resolution without PyPI lookups for ADHD modules.
        """
        self.logger.info(f"Installing {len(self.params.module_urls)} modules as workspace members...")
        
        api = GithubApi()
        clone_successes: List[ModuleMetadata] = []
        clone_failures: List[tuple[str, str]] = []  # (url, error_message)
        
        for url in self.params.module_urls:
            self.logger.info(f"Cloning module: {url}")
            try:
                metadata = self._clone_module_to_workspace(api, url, project_path)
                if metadata:
                    clone_successes.append(metadata)
                    self.logger.info(f"  ✓ Installed {metadata.package_name} to {MODULE_TYPE_TO_DIR.get(metadata.module_type, 'unknown')}/{metadata.folder_name}")
                else:
                    clone_failures.append((url, "Failed to extract module metadata"))
            except Exception as e:
                error_msg = str(e)
                self.logger.error(f"  ✗ Failed to clone: {error_msg}")
                clone_failures.append((url, error_msg))
        
        # Store installed modules for pyproject.toml generation
        self._installed_modules = clone_successes
        
        # Report summary
        self.logger.info("=" * 60)
        self.logger.info("WORKSPACE MODULES INSTALLATION SUMMARY")
        self.logger.info("=" * 60)
        self.logger.info(f"  Installed: {len(clone_successes)}/{len(self.params.module_urls)}")
        if clone_failures:
            self.logger.info(f"  Failed: {len(clone_failures)}/{len(self.params.module_urls)}")
        
        if clone_successes:
            self.logger.info("  Installed modules:")
            for mod in clone_successes:
                target_dir = MODULE_TYPE_TO_DIR.get(mod.module_type, "unknown")
                self.logger.info(f"    ✓ {mod.package_name} → {target_dir}/{mod.folder_name}")
        
        if clone_failures:
            self.logger.warning("  Failed to install:")
            for url, error in clone_failures:
                self.logger.warning(f"    ✗ {url}")
                self.logger.warning(f"      Reason: {error[:200]}")
        
        self.logger.info("=" * 60)
        
        if clone_failures:
            self.logger.warning(
                f"WARNING: {len(clone_failures)} module(s) failed to install. "
                "The project was created but may be missing modules. "
                "Check the errors above."
            )

    def _clone_module_to_workspace(
        self, api: GithubApi, url: str, project_path: Path
    ) -> Optional[ModuleMetadata]:
        """Clone a module from git URL into the appropriate workspace folder.
        
        Args:
            api: GithubApi instance for cloning
            url: Git URL of the module
            project_path: Root path of the new project
            
        Returns:
            ModuleMetadata if successful, None if metadata extraction failed
        """
        # Clone to a temporary location first to read metadata
        repo = api.repo(url)
        temp_dest = api.temp_mgr.make_dir(prefix="mod_clone")
        
        try:
            clone_result = repo.clone_repo(temp_dest, clone_args=["--depth=1"])
            if not clone_result:
                raise ADHDError(f"Failed to clone {url}")
            
            temp_path = Path(temp_dest)
            
            # Extract metadata from pyproject.toml
            metadata = self._extract_module_metadata(temp_path, url)
            if not metadata:
                return None
            
            # Determine target directory based on module type
            target_dir_name = MODULE_TYPE_TO_DIR.get(metadata.module_type)
            if not target_dir_name:
                self.logger.warning(
                    f"Unknown module type '{metadata.module_type}' for {url}, "
                    f"defaulting to 'plugins'"
                )
                target_dir_name = "plugins"
            
            # Move module to the appropriate workspace folder
            target_path = project_path / target_dir_name / metadata.folder_name
            if target_path.exists():
                self.logger.warning(f"Module folder already exists, removing: {target_path}")
                shutil.rmtree(target_path)
            
            # Remove .git directory before moving (we don't want nested git repos)
            remove_git_dir(temp_path)
            
            # Move the cloned module to its final location
            shutil.move(str(temp_path), str(target_path))
            
            return metadata
            
        finally:
            # Cleanup temp directory if it still exists
            if Path(temp_dest).exists():
                api.temp_mgr.cleanup(temp_dest)

    def _extract_module_metadata(self, module_path: Path, url: str) -> Optional[ModuleMetadata]:
        """Extract metadata from a module's pyproject.toml.
        
        Args:
            module_path: Path to the cloned module
            url: Original git URL (for reference)
            
        Returns:
            ModuleMetadata or None if extraction failed
        """
        pyproject_path = module_path / "pyproject.toml"
        if not pyproject_path.exists():
            self.logger.error(f"No pyproject.toml found in {module_path}")
            return None
        
        try:
            with open(pyproject_path, "rb") as f:
                data = tomllib.load(f)
            
            # Extract package name from [project].name
            project_section = data.get("project", {})
            package_name = project_section.get("name")
            if not package_name:
                self.logger.error(f"No project.name found in {pyproject_path}")
                return None
            
            # Extract module type from [tool.adhd].type
            adhd_section = data.get("tool", {}).get("adhd", {})
            module_type = adhd_section.get("type", "plugin")  # Default to plugin if not specified
            
            # Determine folder name - use the directory name from the cloned repo
            # Typically this is the module name in snake_case
            folder_name = module_path.name
            
            # If folder_name is a temp directory name, try to derive from package name
            if folder_name.startswith("mod_clone") or folder_name.startswith("tmp"):
                # Convert package-name to folder_name (package_name format)
                folder_name = package_name.replace("-", "_")
            
            return ModuleMetadata(
                package_name=package_name,
                module_type=module_type,
                folder_name=folder_name,
                url=url,
            )
            
        except Exception as e:
            self.logger.error(f"Failed to parse {pyproject_path}: {e}")
            return None


__all__ = ["ProjectCreator", "ProjectParams", "RepoCreationOptions", "ModuleMetadata"]
