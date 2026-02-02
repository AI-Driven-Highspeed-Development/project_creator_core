from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from creator_common_core import (
    RepoCreationOptions,
    to_snake_case,
)
from .project_creator import ProjectCreator, ProjectParams
from exceptions_core import ADHDError
from questionary_core import QuestionaryCore
from logger_util import Logger


@dataclass
class ProjectWizardArgs:
    """Pre-filled arguments for project creation wizard."""
    name: Optional[str] = None
    parent_dir: Optional[str] = None
    description: Optional[str] = None  # Project description
    # DEPRECATED_P3: template and preload_sets no longer used - embedded templates only
    create_repo: Optional[bool] = None  # None = ask, True = yes, False = no
    owner: Optional[str] = None
    visibility: Optional[str] = None  # "public" or "private"


def run_project_creation_wizard(
    *,
    prompter: QuestionaryCore,
    logger: Logger,
    prefilled: Optional[ProjectWizardArgs] = None,
) -> None:
    """Guide the user through the interactive project scaffolding workflow.
    
    Creates a new project using embedded templates (no external cloning).
    
    Args:
        prompter: QuestionaryCore instance for interactive prompts
        logger: Logger instance
        prefilled: Pre-filled arguments to skip corresponding prompts
    """
    if prefilled is None:
        prefilled = ProjectWizardArgs()

    try:
        # Project name
        if prefilled.name:
            project_name = to_snake_case(prefilled.name)
            if project_name != prefilled.name:
                logger.info(f"Project name normalized to '{project_name}'")
        else:
            raw_project_name = prompter.autocomplete_input(
                "Project name",
                choices=[],
                default="my_project",
            )
            project_name = to_snake_case(raw_project_name)
            if project_name != raw_project_name:
                logger.info(f"Project name normalized to '{project_name}'")
        
        # Parent directory
        if prefilled.parent_dir:
            parent_dir = prefilled.parent_dir
        else:
            parent_dir = prompter.path_input(
                "Destination parent directory",
                default=".",
                only_directories=True,
            )
        dest_path = str(Path(parent_dir) / project_name)
        
        # Optional description
        description = prefilled.description or ""

    except KeyboardInterrupt:
        logger.info("Input cancelled. Exiting.")
        return

    # GitHub repository creation
    try:
        repo_options = _prompt_repo_creation(prompter, logger, prefilled)
    except KeyboardInterrupt:
        logger.info("Repository creation cancelled. Exiting.")
        return

    # Create the project using embedded templates
    params = ProjectParams(
        repo_path=dest_path,
        module_urls=[],  # DEPRECATED_P3: module_urls no longer used
        project_name=project_name,
        description=description,
        repo_options=repo_options,
    )
    creator = ProjectCreator(params)
    try:
        dest = creator.create()
    except ADHDError as exc:  # pragma: no cover - CLI flow
        logger.error(f"❌ Failed to create project: {exc}")
        return

    logger.info(f"✅ Project created at: {dest}")
    logger.info("Next steps:")
    logger.info(f"  cd {dest}")
    logger.info("  uv run adhd --help")
    logger.info("  uv run adhd new-module  # to add modules")


def _prompt_repo_creation(
    prompter: QuestionaryCore,
    logger: Logger,
    prefilled: ProjectWizardArgs,
) -> Optional[RepoCreationOptions]:
    from github_api_core import GithubApi
    
    # Check if repo creation is pre-determined
    if prefilled.create_repo is False:
        return None
    
    if prefilled.create_repo is None:
        try:
            create_choice = prompter.multiple_choice(
                "Create a GitHub repository for this project?",
                ["Yes", "No"],
                default="Yes",
            )
        except KeyboardInterrupt:
            logger.info("Repository creation choice cancelled. Exiting.")
            raise

        if create_choice != "Yes":
            return None

    try:
        api = GithubApi()
        user_login = api.get_authenticated_user_login()
    except ADHDError as exc:
        logger.error(f"Failed to initialize GitHub CLI: {exc}")
        return None

    try:
        orgs = api.get_user_orgs()
    except ADHDError as exc:
        logger.error(f"Failed to fetch organizations: {exc}")
        orgs = []

    owner_lookup: dict[str, str] = {}
    if user_login:
        owner_lookup[f"{user_login} (personal)"] = user_login

    for org in orgs:
        login = org.get("login")
        if login and login not in owner_lookup.values():
            owner_lookup[f"{login} (org)"] = login

    if not owner_lookup:
        logger.error("No eligible GitHub owners found; skipping repository creation.")
        return None

    # Owner selection
    if prefilled.owner:
        # Validate the prefilled owner
        if prefilled.owner in owner_lookup.values():
            owner = prefilled.owner
        else:
            logger.error(f"Owner '{prefilled.owner}' not found. Available: {', '.join(owner_lookup.values())}")
            return None
    else:
        owner_labels = list(owner_lookup.keys())
        options_preview = "\n".join(f" - {label}" for label in owner_labels)
        logger.info(f"Available repository owners:\n{options_preview}")

        try:
            owner_label = prompter.multiple_choice(
                "Select repository owner",
                owner_labels
            )
        except KeyboardInterrupt:
            logger.info("Repository owner selection cancelled. Exiting.")
            raise
        owner = owner_lookup[owner_label]

    # Visibility selection
    if prefilled.visibility:
        if prefilled.visibility not in ["public", "private"]:
            logger.error(f"Invalid visibility '{prefilled.visibility}'. Must be 'public' or 'private'.")
            return None
        visibility = prefilled.visibility
    else:
        try:
            visibility_choice = prompter.multiple_choice(
                "Repository visibility",
                ["Public", "Private"],
                default="Private",
            )
        except KeyboardInterrupt:
            logger.info("Repository visibility selection cancelled. Exiting.")
            raise
        visibility = "private" if visibility_choice == "Private" else "public"
    
    return RepoCreationOptions(owner=owner, visibility=visibility)


__all__ = ["run_project_creation_wizard", "ProjectWizardArgs"]
