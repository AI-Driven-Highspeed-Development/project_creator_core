from __future__ import annotations
import os
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional
import subprocess

try:
    import tomllib  # Python 3.11+
except ImportError:
    import tomli as tomllib  # Fallback for older Python

from exceptions_core import ADHDError
from creator_common_core import (
    RepoCreationOptions,
    create_remote_repo,
)
from logger_util import Logger


# Module type to workspace directory mapping
MODULE_TYPE_TO_DIR = {
    "core": "cores",
    "manager": "managers",
    "util": "utils",
    "mcp": "mcps",
    "plugin": "plugins",
}



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
class ModuleInfo:
    """Metadata extracted from a cloned module."""
    package_name: str  # From [project] name in pyproject.toml
    module_type: str   # From [tool.adhd] type in pyproject.toml
    folder_name: str   # The directory name (e.g., 'config_manager')
    git_url: str       # Original git URL


@dataclass
class ProjectParams:
    repo_path: str
    module_urls: List[str]  # Git URLs for modules to install (from preload sets)
    project_name: str
    description: str = ""  # Optional project description
    repo_options: Optional[RepoCreationOptions] = None


class ProjectCreator:
    """Create a new ADHD Framework project from embedded templates.
    
    Uses uv to install ADHD modules directly from git URLs. Each module's
    pyproject.toml includes [tool.uv.sources] with git URLs for its dependencies,
    enabling transitive dependency resolution without PyPI.
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
        self._write_gitignore(dest_path)
        self._write_readme(dest_path)
        self._write_app_entry(dest_path)
        self._write_tests_init(dest_path)
        self._write_project_init(dest_path)
        self._copy_adhd_framework(dest_path)
        
        # Install preloaded modules by cloning to workspace folders
        installed_modules: List[ModuleInfo] = []
        if self.params.module_urls:
            installed_modules = self._install_modules_to_workspace(dest_path)
        
        # Write pyproject.toml with workspace members and sources
        self._write_pyproject_toml(dest_path, installed_modules)
        
        # Sync to ensure all dependencies are resolved
        self._run_uv_sync(dest_path)

        # Create remote repo if requested
        if self.params.repo_options:
            create_remote_repo(
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

    def _write_pyproject_toml(
        self, project_path: Path, installed_modules: Optional[List[ModuleInfo]] = None
    ) -> None:
        """Generate pyproject.toml for new project with workspace configuration.
        
        Args:
            project_path: Path to the project directory
            installed_modules: List of ModuleInfo for installed modules.
                               Used to generate dependencies and uv.sources.
        """
        template = _load_template("pyproject.toml.template")
        
        # Build dependencies list from installed modules
        dependencies_lines = ""
        uv_sources_lines = ""
        
        if installed_modules:
            # Add each installed module as a dependency with workspace source
            dep_list = []
            source_list = []
            for mod in installed_modules:
                dep_list.append(f'    "{mod.package_name}",')
                source_list.append(f'{mod.package_name} = {{ workspace = true }}')
            
            dependencies_lines = "\n".join(dep_list)
            uv_sources_lines = "[tool.uv.sources]\n" + "\n".join(source_list)
        
        content = template.format(
            project_name=self.params.project_name,
            description=self.params.description or "",
            dependencies=dependencies_lines,
            uv_sources=uv_sources_lines,
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

    def _install_modules_to_workspace(self, project_path: Path) -> List[ModuleInfo]:
        """Install modules by cloning to correct workspace folders based on type.
        
        Flow for each module URL:
        1. Clone to temp directory
        2. Read pyproject.toml to get package name and type
        3. Move to appropriate workspace folder (cores/, managers/, etc.)
        4. Track for pyproject.toml generation
        
        Args:
            project_path: Path to the project directory
            
        Returns:
            List of ModuleInfo for successfully installed modules.
        """
        self.logger.info(f"Installing {len(self.params.module_urls)} modules to workspace...")
        
        installed_modules: List[ModuleInfo] = []
        install_failures: List[tuple[str, str]] = []
        
        # Create temp directory for cloning
        temp_base = Path(tempfile.mkdtemp(prefix="adhd_project_"))
        
        try:
            for url in self.params.module_urls:
                folder_name = self._extract_folder_name_from_url(url)
                self.logger.info(f"Installing: {folder_name} from {url}")
                
                try:
                    module_info = self._clone_and_place_module(
                        url, folder_name, temp_base, project_path
                    )
                    installed_modules.append(module_info)
                    self.logger.info(f"  ✓ Installed {module_info.package_name} to {MODULE_TYPE_TO_DIR.get(module_info.module_type, 'unknown')}/")
                except Exception as e:
                    error_msg = str(e)
                    self.logger.error(f"  ✗ Failed to install {folder_name}: {error_msg}")
                    install_failures.append((url, error_msg))
        finally:
            # Cleanup temp directory
            shutil.rmtree(temp_base, ignore_errors=True)
        
        # Report summary
        self._report_installation_summary(installed_modules, install_failures)
        
        return installed_modules

    def _clone_and_place_module(
        self,
        git_url: str,
        folder_name: str,
        temp_base: Path,
        project_path: Path,
    ) -> ModuleInfo:
        """Clone a module to temp, read metadata, and move to correct workspace folder.
        
        Args:
            git_url: Git URL of the module
            folder_name: Directory name for the module
            temp_base: Temporary directory for cloning
            project_path: Target project path
            
        Returns:
            ModuleInfo with extracted metadata
            
        Raises:
            ADHDError: If cloning or metadata extraction fails
        """
        temp_clone_path = temp_base / folder_name
        
        # Clone to temp directory
        result = subprocess.run(
            ["git", "clone", "--depth", "1", git_url, str(temp_clone_path)],
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode != 0:
            raise ADHDError(f"git clone failed: {result.stderr}") from None
        
        # Read pyproject.toml to get package name and type
        pyproject_path = temp_clone_path / "pyproject.toml"
        if not pyproject_path.exists():
            raise ADHDError(f"Module missing pyproject.toml: {folder_name}") from None
        
        package_name, module_type = self._extract_module_metadata(pyproject_path)
        
        # Determine target directory based on module type
        type_dir = MODULE_TYPE_TO_DIR.get(module_type)
        if not type_dir:
            raise ADHDError(
                f"Unknown module type '{module_type}' for {folder_name}. "
                f"Expected one of: {list(MODULE_TYPE_TO_DIR.keys())}"
            ) from None
        
        # Move to correct workspace folder
        target_dir = project_path / type_dir / folder_name
        if target_dir.exists():
            self.logger.warning(f"Module already exists at {target_dir}, skipping...")
            raise ADHDError(f"Module already exists: {target_dir}") from None
        
        shutil.move(str(temp_clone_path), str(target_dir))
        
        return ModuleInfo(
            package_name=package_name,
            module_type=module_type,
            folder_name=folder_name,
            git_url=git_url,
        )

    def _extract_module_metadata(self, pyproject_path: Path) -> tuple[str, str]:
        """Extract package name and module type from pyproject.toml.
        
        Args:
            pyproject_path: Path to the module's pyproject.toml
            
        Returns:
            Tuple of (package_name, module_type)
            
        Raises:
            ADHDError: If required fields are missing
        """
        with open(pyproject_path, "rb") as f:
            data = tomllib.load(f)
        
        # Get package name from [project] name
        project_section = data.get("project", {})
        package_name = project_section.get("name")
        if not package_name:
            raise ADHDError(
                f"pyproject.toml missing [project] name: {pyproject_path}"
            ) from None
        
        # Get module type from [tool.adhd] type
        tool_adhd = data.get("tool", {}).get("adhd", {})
        module_type = tool_adhd.get("type")
        if not module_type:
            raise ADHDError(
                f"pyproject.toml missing [tool.adhd] type: {pyproject_path}"
            ) from None
        
        return package_name, module_type

    def _extract_folder_name_from_url(self, url: str) -> str:
        """Extract the folder name (repo name) from a git URL.
        
        Examples:
            https://github.com/org/Config-Manager.git -> Config-Manager
            https://github.com/org/logger_util.git -> logger_util
        """
        # Remove .git suffix and get the repo name
        return url.rstrip("/").removesuffix(".git").split("/")[-1]

    def _report_installation_summary(
        self,
        installed_modules: List[ModuleInfo],
        install_failures: List[tuple[str, str]],
    ) -> None:
        """Report summary of module installation."""
        total = len(installed_modules) + len(install_failures)
        
        self.logger.info("=" * 60)
        self.logger.info("MODULE INSTALLATION SUMMARY")
        self.logger.info("=" * 60)
        self.logger.info(f"  Installed: {len(installed_modules)}/{total}")
        if install_failures:
            self.logger.info(f"  Failed: {len(install_failures)}/{total}")
        
        if installed_modules:
            self.logger.info("  Installed modules:")
            for mod in installed_modules:
                type_dir = MODULE_TYPE_TO_DIR.get(mod.module_type, "unknown")
                self.logger.info(f"    ✓ {mod.package_name} -> {type_dir}/{mod.folder_name}/")
        
        if install_failures:
            self.logger.warning("  Failed to install:")
            for url, error in install_failures:
                folder_name = self._extract_folder_name_from_url(url)
                self.logger.warning(f"    ✗ {folder_name}")
                self.logger.warning(f"      Reason: {error[:200]}")
        
        self.logger.info("=" * 60)
        
        if install_failures:
            self.logger.warning(
                f"WARNING: {len(install_failures)} module(s) failed to install. "
                "The project was created but may be missing modules. "
                "Check the errors above."
            )


__all__ = ["ProjectCreator", "ProjectParams", "ModuleInfo", "RepoCreationOptions"]
