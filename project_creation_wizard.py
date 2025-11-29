from __future__ import annotations

import re
from pathlib import Path
from typing import Callable, Iterable, Optional, TypeVar

from managers.config_manager import ConfigManager
from cores.github_api_core.api import GithubApi
from cores.creator_common_core.creator_common_core import (
    RepoCreationOptions,
    TemplateInfo,
    list_templates,
)
from cores.project_creator_core.project_creator import (
    ProjectCreator,
    ProjectParams,
)
from cores.exceptions_core.adhd_exceptions import ADHDError
from cores.project_creator_core.preload_sets import PreloadSet, parse_preload_sets
from cores.questionary_core.questionary_core import QuestionaryCore
from cores.yaml_reading_core.yaml_reading import YamlReadingCore as yaml_reading
from utils.logger_util.logger import Logger

T = TypeVar("T")


def run_project_creation_wizard(
    *,
    prompter: QuestionaryCore,
    logger: Logger,
) -> None:
    """Guide the user through the interactive project scaffolding workflow."""

    cm = ConfigManager()
    config = cm.config.project_creator_core
    proj_tmpls = yaml_reading.read_yaml(config.path.project_templates)
    mod_preload_sets = yaml_reading.read_yaml(config.path.module_preload_sets)

    if proj_tmpls is None:
        logger.error("No project templates configuration found.")
        return
    if mod_preload_sets is None:
        logger.error("No module preload sets configuration found.")
        return

    try:
        raw_project_name = prompter.autocomplete_input(
            "Project name",
            choices=[],
            default="my_project",
        )
        project_name = _to_snake_case(raw_project_name)
        if project_name != raw_project_name:
            logger.info(f"Project name normalized to '{project_name}'")
        
        parent_dir = prompter.path_input(
            "Destination parent directory",
            default=".",
            only_directories=True,
        )
        dest_path = str(Path(parent_dir) / project_name)
    except KeyboardInterrupt:
        logger.info("Input cancelled. Exiting.")
        return

    templates: list[TemplateInfo] = list_templates(proj_tmpls.to_dict())
    if not templates:
        logger.error("No project templates found in configuration.")
        return

    if len(templates) == 1:
        # If there's only one template, select it automatically without prompting.
        only_template = templates[0]
        logger.info(
            f"Single project template detected; using {only_template.name} ({only_template.url}) automatically.")
        template_url = only_template.url
    else:
        template_lookup = _choices_map(
            templates,
            formatter=lambda tmpl: f"{tmpl.name} — {tmpl.description or tmpl.url}",
        )
        try:
            selected_template_label = prompter.multiple_choice(
                "Select a project template",
                list(template_lookup.keys()),
                default=next(iter(template_lookup)),
            )
        except KeyboardInterrupt:
            logger.info("Template selection cancelled. Exiting.")
            return
        template_url = template_lookup[selected_template_label].url

    always_urls, sets = parse_preload_sets(mod_preload_sets)
    preload_lookup = _choices_map(
        ["None", *sets],
        formatter=lambda item: "None"
        if isinstance(item, str)
        else f"{item.name} — {item.description}",
    )
    try:
        selected_set_label = prompter.multiple_choice(
            "Select a module preload set",
            list(preload_lookup.keys()),
            default=next(iter(preload_lookup)),
        )
    except KeyboardInterrupt:
        logger.info("Preload selection cancelled. Exiting.")
        return

    selected_urls: list[str] = []
    preload_value = preload_lookup[selected_set_label]
    if isinstance(preload_value, PreloadSet):
        selected_urls = preload_value.urls

    module_urls = list(dict.fromkeys(always_urls + selected_urls))

    try:
        repo_options = _prompt_repo_creation(prompter, logger)
    except KeyboardInterrupt:
        logger.info("Repository creation cancelled. Exiting.")
        return

    params = ProjectParams(
        repo_path=dest_path,
        module_urls=module_urls,
        project_name=project_name,
        repo_options=repo_options,
    )
    creator = ProjectCreator(params)
    try:
        dest = creator.create(template_url)
    except ADHDError as exc:  # pragma: no cover - CLI flow
        logger.error(f"❌ Failed to create project: {exc}")
        return

    logger.info(f"✅ Project created at: {dest}")


def _choices_map(items: Iterable[T], *, formatter: Callable[[T], str]) -> dict[str, T]:
    """Return an ordered mapping of menu labels to original items."""

    lookup: dict[str, T] = {}
    for item in items:
        label = formatter(item)
        if label in lookup:
            raise ValueError("Duplicate option label generated for choices")
        lookup[label] = item
    return lookup


def _prompt_repo_creation(prompter: QuestionaryCore, logger: Logger) -> Optional[RepoCreationOptions]:
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


__all__ = ["run_project_creation_wizard"]


def _to_snake_case(value: str) -> str:
    cleaned = re.sub(r"[^0-9a-zA-Z]+", "_", value.strip())
    cleaned = re.sub(r"_+", "_", cleaned).strip("_")
    result = cleaned.lower()
    return result or "project"
